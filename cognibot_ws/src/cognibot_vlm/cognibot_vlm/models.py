"""llama-swap's `GET /running` -> a ModelStatus state for the dashboard's GPU gauge."""

from __future__ import annotations

from typing import Any

# ModelStatus constants (kept here so this module has no ROS dependency)
UNLOADED, LOADING, LOADED, UNLOADING = 0, 1, 2, 3

_STATES = {"starting": LOADING, "ready": LOADED, "stopping": UNLOADING, "shutdown": UNLOADING}


def vlm_state(running: dict[str, Any]) -> tuple[int, str]:
    """(state, model name) from llama-swap's `/running` payload.

    Verified against the pinned llama-swap: `{"running": []}` when nothing is loaded, then one entry
    per model moving `"starting"` -> `"ready"`; the entry's `name` is the profile's display name.
    """
    entries = running.get("running") or []
    if not entries:
        return UNLOADED, ""
    entry = entries[0]
    return _STATES.get(str(entry.get("state", "")), LOADING), str(
        entry.get("name") or entry.get("model", "")
    )
