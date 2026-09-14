"""OpenAI tool schemas for the agent and a small validator (no jsonschema dependency).

Units are metres in the robot base frame. The schemas are deliberately flat: a 4B model fills
`{"x": .., "y": .., "z": ..}` reliably, nested objects much less so.
"""

from __future__ import annotations

from typing import Any

POINT = {
    "x": {"type": "number", "description": "metres, base frame, forward"},
    "y": {"type": "number", "description": "metres, base frame, left"},
    "z": {"type": "number", "description": "metres, base frame, up"},
}


def _tool(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False,
            },
        },
    }


TOOLS: list[dict] = [
    _tool(
        "get_object_coordinates",
        "Find an object in the front camera image and return the 3D position of its centre in "
        "the robot base frame (metres; objects are assumed to rest on the table) and `top`, "
        "the height of its top surface. Only for answering questions about where things are; "
        "fetch_object and place_object look for their object themselves.",
        {"label": {"type": "string", "description": "object description, e.g. 'red cube'"}},
        ["label"],
    ),
    _tool(
        "check_reachability",
        "Tell whether the arm can reach a point (metres, base frame).",
        POINT,
        ["x", "y", "z"],
    ),
    _tool(
        "fetch_object",
        "Look for the object in the camera, then pick it up: approach from above, grasp, lift.",
        {"label": {"type": "string", "description": "object description, e.g. 'red cube'"}},
        ["label"],
    ),
    _tool(
        "place_object",
        "Look for the destination in the camera, then lower the held object onto it and "
        "release: onto the top of another object (stacking) or the centre of a marked area.",
        {
            "label": {
                "type": "string",
                "description": "destination, e.g. 'blue cube' or 'black rectangle'",
            }
        },
        ["label"],
    ),
    _tool("move_home", "Move the arm to its home pose.", {}, []),
    _tool(
        "set_gripper",
        "Open or close the gripper.",
        {"state": {"type": "string", "enum": ["open", "closed"]}},
        ["state"],
    ),
    _tool(
        "run_vla_skill",
        "Run a learned visuomotor policy for a natural-language instruction for up to "
        "max_duration_s seconds. Use only when scripted fetch/place cannot do the task.",
        {
            "instruction": {"type": "string"},
            "max_duration_s": {"type": "number", "description": "seconds, default 60"},
        },
        ["instruction"],
    ),
]

TOOL_NAMES = {t["function"]["name"] for t in TOOLS}


class ToolError(ValueError):
    """Unknown tool or arguments that do not fit its schema."""


def validate_arguments(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Return `arguments` checked against the tool's schema (types, enum, required, no extras)."""
    schema = next((t["function"] for t in TOOLS if t["function"]["name"] == name), None)
    if schema is None:
        raise ToolError(f"unknown tool '{name}'; available: {sorted(TOOL_NAMES)}")
    params = schema["parameters"]
    if not isinstance(arguments, dict):
        raise ToolError(f"{name}: arguments must be a JSON object")
    missing = [k for k in params["required"] if k not in arguments]
    if missing:
        raise ToolError(f"{name}: missing required argument(s) {missing}")
    extra = [k for k in arguments if k not in params["properties"]]
    if extra:
        raise ToolError(f"{name}: unexpected argument(s) {extra}")
    checked: dict[str, Any] = {}
    for key, value in arguments.items():
        spec = params["properties"][key]
        if spec["type"] == "number":
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ToolError(f"{name}: '{key}' must be a number, got {value!r}")
            checked[key] = float(value)
        elif spec["type"] == "string":
            if not isinstance(value, str):
                raise ToolError(f"{name}: '{key}' must be a string, got {value!r}")
            if "enum" in spec and value not in spec["enum"]:
                raise ToolError(f"{name}: '{key}' must be one of {spec['enum']}, got {value!r}")
            checked[key] = value
        else:  # pragma: no cover - schemas above only use number/string
            checked[key] = value
    return checked
