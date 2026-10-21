"""Placeholder time teller. The simplest kind of plugin, no follow-up questions."""

from datetime import datetime

from core.plugin import Plugin


class Clock(Plugin):
    name = "time"
    description = "what time it is right now, the clock, todays date or day of the week"

    def run(self, prompt, ctx):
        reply = f"It is {datetime.now():%H:%M on %A}."
        print(f"[time] {reply}")
        return reply
