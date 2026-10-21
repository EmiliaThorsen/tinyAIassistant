import tomllib
from pathlib import Path

CONFIG_PATH = Path(__file__).parent.parent / "config.toml"


def load_config(path: Path = CONFIG_PATH) -> dict:
    if not path.exists():
        return {}
    with path.open("rb") as f:
        return tomllib.load(f)
