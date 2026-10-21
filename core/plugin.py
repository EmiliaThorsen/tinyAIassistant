"""Plugin base class and discovery.

A plugin is any subclass of `Plugin` defined in a module inside the plugins
folder. Its `name` and `description` become one option in the main menu; if the
model picks it, `run` is called and can ask the model further questions through
the context to work its way down its own "adventure".
"""

import importlib.util
import inspect
from pathlib import Path


class Plugin:
    # Menu label the model picks between. Keep it short and unique.
    name: str = ""
    # Shown to the model next to the name, so describe what requests it handles.
    description: str = ""

    def setup(self, config: dict) -> None:
        """Called once at startup with the whole parsed config.toml."""

    def run(self, prompt: str, ctx) -> str | None:
        """Do the thing, returns the reply to say back to the user (None for a generic "Done.")."""
        raise NotImplementedError


def load_plugins(folder: Path, config: dict) -> list[Plugin]:
    plugins = []
    for path in sorted(folder.glob("*.py")):
        if path.name.startswith("_"):
            continue
        spec = importlib.util.spec_from_file_location(f"plugins.{path.stem}", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for _, cls in inspect.getmembers(module, inspect.isclass):
            if issubclass(cls, Plugin) and cls is not Plugin and cls.__module__ == module.__name__:
                plugin = cls()
                if not plugin.name or not plugin.description:
                    raise ValueError(f"{path.name}: {cls.__name__} needs a name and description")
                plugin.setup(config)
                plugins.append(plugin)
    names = [p.name for p in plugins]
    dupes = {n for n in names if names.count(n) > 1}
    if dupes:
        raise ValueError(f"duplicate plugin names: {dupes}")
    return plugins
