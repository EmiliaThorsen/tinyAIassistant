"""Placeholder weather report. Uses a yes/no question as its follow-up."""

from core.plugin import Plugin


class Weather(Plugin):
    name = "weather"
    description = "weather forecast, temperature, rain, wind, whether to bring an umbrella or jacket"

    def run(self, prompt, ctx):
        answers = ctx.ask({
            "tomorrow": {
                "type": "noul",
                "instructions": "Is the user asking about tomorrow or later rather than today?",
            },
        })
        when = "tomorrow" if answers["tomorrow"]["noul"] > 0.5 else "today"
        print(f"[weather] would report the weather for {when}")
        return f"I don't know the weather {when} yet."
