"""Wraps the laya model, runs the main menu and logs every request."""

import json
import time
from datetime import datetime
from pathlib import Path

from core.plugin import Plugin

NONE_OPTION = "none"

# checkpoint name -> subfolder in the convaiinnovations/laya repo
CHECKPOINTS = {"english": None, "multilingual": "multilingual", "typed-decisions": "typed-decisions"}


class Context:
    """Handed to plugins so they can ask the model follow-up questions."""

    def __init__(self, engine: "Engine", prompt: str, record: dict):
        self.engine = engine
        self.prompt = prompt
        self.record = record

    def ask(self, questions: dict) -> dict:
        """Run the model on the original prompt with new questions, returns the answers dict."""
        return self.engine.predict(self.prompt, questions, self.record)

    def note(self, **fields) -> None:
        """Add what the plugin ended up doing to the request log, e.g. the HA service it called."""
        self.record.setdefault("outcome", {}).update(fields)

    def debug(self, *args) -> None:
        self.engine.debug(*args)


class Engine:
    def __init__(self, plugins: list[Plugin], model: str = "multilingual",
                 min_confidence: float = 0.5, verbose: bool = True, log_path: Path | None = None):
        import laya  # imported here so --help etc. stays fast

        self.plugins = {p.name: p for p in plugins}
        self.model_name = model
        self.min_confidence = min_confidence
        self.verbose = verbose
        self.log_path = log_path
        self.model = laya.load("convaiinnovations/laya", subfolder=CHECKPOINTS[model])

    def debug(self, *args) -> None:
        if self.verbose:
            print("[debug]", *args)

    def predict(self, prompt: str, questions: dict, record: dict | None = None) -> dict:
        start = time.perf_counter()
        result = self.model.predict(prompt, questions, min_confidence=self.min_confidence)
        ms = (time.perf_counter() - start) * 1000
        self.debug(f"took {ms:.0f} ms")
        for qid, answer in result["answers"].items():
            self.debug(f"  {qid}: {_summarize(answer)}")
        if record is not None:
            # questions are logged in full so a step can be turned into a training example later
            record["steps"].append({
                "questions": questions,
                "answers": result["answers"],
                "ms": round(ms),
                "truncated": result.get("usage", {}).get("truncated", False),
            })
        return result["answers"]

    def main_menu_questions(self) -> dict:
        criteria = {name: p.description for name, p in self.plugins.items()}
        criteria[NONE_OPTION] = "the request does not match any of the other options"
        return {
            "tool": {
                "type": "choice",
                "instructions": "Which tool should handle this request?",
                "criteria": criteria,
            }
        }

    def handle(self, prompt: str, meta: dict | None = None) -> tuple[bool, str]:
        """Returns whether a plugin handled the prompt, and the reply to show or speak.

        `meta` is extra info about where the request came from (language, HA context) for the log.
        """
        record = {
            "time": datetime.now().astimezone().isoformat(timespec="seconds"),
            "prompt": prompt,
            "model": self.model_name,
            **(meta or {}),
            "steps": [],
        }
        try:
            handled, reply = self._handle(prompt, record)
            record.update(handled=handled, reply=reply)
            return handled, reply
        except Exception as e:
            record["error"] = repr(e)
            raise
        finally:
            self._log(record)

    def _handle(self, prompt: str, record: dict) -> tuple[bool, str]:
        answer = self.predict(prompt, self.main_menu_questions(), record)["tool"]
        choice = answer["choice"]
        if choice == NONE_OPTION or answer.get("low_confidence"):
            self.debug(f"giving up, best guess {choice!r} at {answer['answer_confidence']:.2f}")
            return False, "Sorry, I don't know how to help with that."
        record["plugin"] = choice
        reply = self.plugins[choice].run(prompt, Context(self, prompt, record))
        return True, reply or "Done."

    def _log(self, record: dict) -> None:
        if self.log_path is None:
            return
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _summarize(answer: dict) -> str:
    conf = f"conf={answer.get('answer_confidence', 0):.2f}"
    if answer.get("low_confidence"):
        conf += " LOW"
    if "choice" in answer:
        probs = sorted(answer["probabilities"].items(), key=lambda kv: -kv[1])
        probs = ", ".join(f"{k}={v:.2f}" for k, v in probs)
        return f"choice={answer['choice']!r} {conf} [{probs}]"
    if "score" in answer:
        return f"score={answer['score']:.2f} {conf}"
    if "noul" in answer:
        return f"noul={answer['noul']:.2f} {conf}"
    return repr(answer)
