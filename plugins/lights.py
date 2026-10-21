"""Turns Home Assistant lights on and off, sets brightness, color and white temperature.

Lights, and the levels/colors/temperatures the model picks between, are set in config.toml.
"""

import re
import urllib.error

from core import homeassistant
from core.plugin import Plugin

ALL = "all"
ON = "on"
OFF = "off"

# The model picks between these when asked to change brightness without saying a number.
# It matches on shared words a lot, so keep words that appear in other requests ("bright",
# "light") out of the names, "full brightness" went to a level named "bright" over "max".
DEFAULT_LEVELS = {
    "low, dim, night light, barely on": 10,
    "medium, half, moody, cozy": 50,
    "high, normal": 80,
    "max, full brightness, as bright as possible": 100,
}

# name -> rgb. The Swedish word next to the English one helped here ("gör köket rött", "rosa"),
# unlike for light names where mixing languages made things worse.
DEFAULT_COLORS = {
    "red, röd": [255, 0, 0],
    "orange": [255, 120, 0],
    "yellow, gul": [255, 220, 0],
    "green, grön": [0, 255, 0],
    "blue, blå": [0, 0, 255],
    "purple, lila": [150, 0, 255],
    "pink, rosa": [255, 60, 150],
    "white, vit": [255, 255, 255],
}

# name -> kelvin
DEFAULT_TEMPERATURES = {
    "warm white, candle, yellowish": 2700,
    "neutral white": 4000,
    "cold white, daylight, bluish": 6500,
}

# The model can't turn "five percent" into a level, so spoken numbers are parsed here.
UNITS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "noll": 0, "en": 1, "ett": 1, "två": 2, "tre": 3, "fyra": 4, "fem": 5, "sex": 6, "sju": 7, "åtta": 8, "nio": 9,
}
TEENS = {
    "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
    "tio": 10, "elva": 11, "tolv": 12, "tretton": 13, "fjorton": 14, "femton": 15,
    "sexton": 16, "sjutton": 17, "arton": 18, "nitton": 19,
}
TENS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
    "tjugo": 20, "trettio": 30, "fyrtio": 40, "femtio": 50, "sextio": 60, "sjuttio": 70, "åttio": 80, "nittio": 90,
}
HUNDRED = {"hundred": 100, "a hundred": 100, "one hundred": 100, "hundra": 100, "etthundra": 100}


def _alt(words) -> str:
    return "|".join(sorted(map(re.escape, words), key=len, reverse=True))


# "seventy five" and "sjuttiofem" are tens followed by a unit, with or without a space or dash
WORD_NUMBER = (rf"(?:{_alt(HUNDRED)})|(?:{_alt(TEENS)})|(?:(?:{_alt(TENS)})(?:[\s-]?(?:{_alt(UNITS)}))?)"
               rf"|(?:{_alt(UNITS)})")
PERCENT = r"\s*(?:%|percent|per cent|procent)"
# digits are taken with or without "percent" ("lights to 30"), words only with it, so
# "turn on the one by the door" isn't read as 1%
NUMBER = re.compile(rf"\b(?:(\d{{1,3}})(?:{PERCENT})?|({WORD_NUMBER}){PERCENT})(?!\w)", re.IGNORECASE)


class Lights(Plugin):
    name = "lights"
    description = "turn lamps and lights on or off, dim them, change their brightness or color"

    def setup(self, config):
        self.ha = homeassistant.from_config(config)
        # descriptive name -> entity id
        self.lights = {name: entity for entity, name in config.get("lights", {}).items()}
        self.levels = config.get("light_levels", DEFAULT_LEVELS)
        self.colors = config.get("light_colors", DEFAULT_COLORS)
        self.temperatures = config.get("light_temperatures", DEFAULT_TEMPERATURES)
        # they all end up as options of one question, so the names have to be unique
        names = [*self.levels, *self.colors, *self.temperatures, ON, OFF]
        dupes = {n for n in names if names.count(n) > 1}
        if dupes:
            raise ValueError(f"lights: level/color/temperature names used twice: {dupes}")
        # naming the lights lets the main menu link "set the kitchen to 50" to this plugin
        if self.lights:
            self.description += ", the lights are: " + "; ".join(self.lights)

    def run(self, prompt, ctx):
        if not self.lights:
            return "No lights are configured."
        criteria = {name: name for name in self.lights}
        criteria[ALL] = "all the lights, every lamp in the house, alla lampor, allt ljus"
        answers = ctx.ask({
            "light": {
                "type": "choice",
                "instructions": "Which light is the request about?",
                "criteria": criteria,
            },
            # one big question for everything. asking on/off/set and the level apart made it say
            # "off" for "make the lights moody", and a "what kind of change" question first
            # called nearly every color and temperature request "brightness"
            "action": {
                "type": "choice",
                "instructions": "What should be done to the light?",
                "criteria": {
                    OFF: "turn off, switch off, shut off",
                    ON: "turn on, switch on, light up, no specific brightness given",
                } | {name: name for name in [*self.levels, *self.colors, *self.temperatures]},
            },
        })
        light, action = answers["light"], answers["action"]["choice"]
        if light.get("low_confidence"):
            # a wrong guess here can be "all", rather do nothing than turn off the whole house.
            # no conversation history yet, so a question back would be pointless
            ctx.note(skipped="unsure which light")
            return "Sorry, I'm not sure which light you meant."
        light = light["choice"]
        entities = list(self.lights.values()) if light == ALL else [self.lights[light]]
        label = "all lights" if light == ALL else light

        brightness = self.levels.get(action)
        number = _explicit_percent(prompt)
        if action != OFF and number is not None:
            # spoken numbers beat the model, it can't tell "five percent" from max.
            # also works next to a color, "make the kitchen red at 30 percent"
            brightness = number

        data, said = {}, []
        if action in self.colors:
            data["rgb_color"] = self.colors[action]
            said.append(_first_word(action))
        elif action in self.temperatures:
            data["color_temp_kelvin"] = self.temperatures[action]
            said.append(_first_word(action))
        if brightness is not None:
            data["brightness_pct"] = brightness
            said.append(f"{brightness} percent")

        if action == OFF or brightness == 0:
            service, data, reply = "turn_off", {}, f"Turning off {label}."
        elif said:
            service, reply = "turn_on", f"Setting {label} to {' at '.join(said)}."
        else:
            service, reply = "turn_on", f"Turning on {label}."
        data["entity_id"] = entities
        ctx.note(service=f"light.{service}", data=data, number_from_text=number)

        if self.ha is None:
            print(f"[lights] dry run: light.{service} {data}")
            return reply
        print(f"[lights] light.{service} {data}")
        try:
            self.ha.call_service("light", service, data)
        except urllib.error.HTTPError as e:
            # e.g. asking a white only light for a color
            body = e.read().decode(errors="replace")
            print(f"[lights] HA refused: {e.code} {body}")
            ctx.note(ha_error=f"{e.code} {body}")
            return f"Home Assistant refused that, maybe {label} can't do it."
        return reply


def _first_word(name: str) -> str:
    return name.split(",")[0]


def _explicit_percent(prompt: str) -> int | None:
    for match in NUMBER.finditer(prompt):
        value = int(match.group(1)) if match.group(1) else _word_value(match.group(2))
        if value <= 100:
            return value
    return None


def _word_value(text: str) -> int:
    text = text.lower()
    for table in (HUNDRED, TEENS, UNITS):
        if text in table:
            return table[text]
    tens = next(t for t in sorted(TENS, key=len, reverse=True) if text.startswith(t))
    rest = text[len(tens):].strip(" -")
    return TENS[tens] + UNITS.get(rest, 0)
