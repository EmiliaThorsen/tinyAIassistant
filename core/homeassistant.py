"""Minimal Home Assistant REST API client.

Run `python -m core.homeassistant` to list the lights HA knows about, handy for
filling in the [lights] section of config.toml.
"""

import json
import urllib.request


class HomeAssistant:
    def __init__(self, url: str, token: str):
        self.url = url.rstrip("/")
        self.token = token

    def _request(self, method: str, path: str, data: dict | None = None):
        body = json.dumps(data).encode() if data is not None else None
        req = urllib.request.Request(f"{self.url}/api/{path}", data=body, method=method, headers={
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.load(resp)

    def call_service(self, domain: str, service: str, data: dict) -> None:
        self._request("POST", f"services/{domain}/{service}", data)

    def states(self) -> list[dict]:
        return self._request("GET", "states")


def from_config(config: dict) -> HomeAssistant | None:
    """Returns None when HA isn't configured, so plugins can fall back to a dry run."""
    ha = config.get("homeassistant", {})
    if not ha.get("url") or not ha.get("token"):
        return None
    return HomeAssistant(ha["url"], ha["token"])


if __name__ == "__main__":
    from core.config import load_config

    config = load_config()
    ha = from_config(config)
    if ha is None:
        raise SystemExit("set url and token under [homeassistant] in config.toml first")
    configured = config.get("lights", {})
    for state in ha.states():
        if state["entity_id"].startswith("light."):
            name = state["attributes"].get("friendly_name", "")
            mark = "configured" if state["entity_id"] in configured else ""
            print(f"{state['entity_id']:40} {state['state']:5} {name:30} {mark}")
