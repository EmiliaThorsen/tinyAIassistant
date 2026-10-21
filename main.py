"""Runs the assistant, either on prompts from stdin (one per line) or as a Wyoming server for Home Assistant."""

import argparse
import asyncio
import sys
from pathlib import Path

from core.config import CONFIG_PATH, load_config
from core.engine import CHECKPOINTS, Engine
from core.plugin import load_plugins

PLUGIN_DIR = Path(__file__).parent / "plugins"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=list(CHECKPOINTS), default="multilingual",
                        help="laya checkpoint to load (default: %(default)s)")
    parser.add_argument("--min-confidence", type=float, default=0.5,
                        help="below this the main menu gives up instead of guessing")
    parser.add_argument("--uri", help="serve the Wyoming protocol on this uri for Home Assistant, "
                                      "e.g. tcp://0.0.0.0:10500, instead of reading stdin")
    parser.add_argument("--config", type=Path, default=CONFIG_PATH, help="config file to use")
    parser.add_argument("--log", type=Path, default=Path(__file__).parent / "logs" / "requests.jsonl",
                        help="jsonl file every request and the model's answers get appended to, "
                             "for building training data (default: %(default)s)")
    parser.add_argument("--no-log", action="store_true", help="don't log requests")
    parser.add_argument("-q", "--quiet", action="store_true", help="hide debug output")
    args = parser.parse_args()

    plugins = load_plugins(PLUGIN_DIR, load_config(args.config))
    print(f"loaded plugins: {', '.join(p.name for p in plugins)}", file=sys.stderr)
    engine = Engine(plugins, model=args.model, min_confidence=args.min_confidence,
                    verbose=not args.quiet, log_path=None if args.no_log else args.log)

    if args.uri:
        from core.wyoming_server import serve
        asyncio.run(serve(engine, args.uri))
        return

    interactive = sys.stdin.isatty()
    while True:
        if interactive:
            print("> ", end="", flush=True)
        line = sys.stdin.readline()
        if not line:
            break
        prompt = line.strip()
        if not prompt:
            continue
        if not interactive:
            print(f"> {prompt}")
        _, reply = engine.handle(prompt, {"source": "stdin"})
        print(reply)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
