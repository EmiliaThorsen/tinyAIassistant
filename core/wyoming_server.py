"""Wyoming protocol server so Home Assistant can use the assistant as a conversation agent.

HA connects, sends `describe`, sees we offer a `handle` service and lists us as a
conversation agent. Each spoken/typed request then arrives as a `transcript`
event and we answer with `handled` or `not-handled`, whose text HA speaks back.
"""

import asyncio
import threading
from functools import partial

from wyoming.asr import Transcript
from wyoming.event import Event
from wyoming.handle import Handled, NotHandled
from wyoming.info import Attribution, Describe, HandleModel, HandleProgram, Info
from wyoming.server import AsyncEventHandler, AsyncServer

from core.engine import Engine

ATTRIBUTION = Attribution(name="tinyAIassistant", url="https://github.com/EmiliaThorsen/tinyAIassistant")

INFO = Info(handle=[HandleProgram(
    name="tinyAIassistant",
    description="Plugin based assistant using the laya decision model",
    attribution=ATTRIBUTION,
    installed=True,
    version="0.1.0",
    models=[HandleModel(
        name="laya",
        description="laya",
        attribution=Attribution(name="convaiinnovations", url="https://huggingface.co/convaiinnovations/laya"),
        installed=True,
        version=None,
        # empty means HA treats us as supporting every language
        languages=[],
    )],
    supports_home_control=True,
)])


class AssistantHandler(AsyncEventHandler):
    def __init__(self, engine: Engine, lock: threading.Lock, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.engine = engine
        self.lock = lock

    async def handle_event(self, event: Event) -> bool:
        if Describe.is_type(event.type):
            await self.write_event(INFO.event())
            return True

        if Transcript.is_type(event.type):
            transcript = Transcript.from_event(event)
            print(f"> {transcript.text}  (lang={transcript.language})", flush=True)
            # the model blocks for a while, keep it off the event loop and one request at a time
            meta = {"source": "wyoming", "language": transcript.language, "context": transcript.context}
            handled, reply = await asyncio.to_thread(self._handle, transcript.text, meta)
            print(f"< {reply}", flush=True)
            context = transcript.context
            if handled:
                await self.write_event(Handled(text=reply, context=context).event())
            else:
                await self.write_event(NotHandled(text=reply, context=context).event())
            return True

        self.engine.debug(f"ignoring wyoming event {event.type!r}")
        return True

    def _handle(self, text: str, meta: dict) -> tuple[bool, str]:
        with self.lock:
            try:
                return self.engine.handle(text, meta)
            except Exception as e:
                # an exception would just drop the connection, tell HA instead
                self.engine.debug(f"error handling {text!r}: {e!r}")
                return False, "Something went wrong."


async def serve(engine: Engine, uri: str) -> None:
    print("loading model...", flush=True)
    # the first prediction loads the checkpoint, don't make the first voice request wait on that.
    # only predict, running a plugin here would actually do things in the house
    await asyncio.to_thread(engine.predict, "hello", engine.main_menu_questions())
    server = AsyncServer.from_uri(uri)
    print(f"starting server on {uri}", flush=True)
    await server.run(partial(AssistantHandler, engine, threading.Lock()))
