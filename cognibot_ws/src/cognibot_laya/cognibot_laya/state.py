"""The symbolic scene state the decision model reads (ADR-0008).

Laya sees one string, not an image: `laya.common.serialize_state` flattens whatever dict it is
given. These builders decide what goes into that dict, in what units, and how much of it fits —
the English checkpoint has 512 tokens for state *and* options, so the object list is trimmed by
distance from the gripper rather than by an arbitrary cut.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

# Rough token budget for the state half of the sequence; the option markers need the rest.
MAX_STATE_TOKENS = 320
# Serialised state is JSON-ish text; ~4 characters per token is the usual conservative estimate.
CHARS_PER_TOKEN = 4


@dataclass(frozen=True)
class SceneObject:
    """One grounded object: metres in the robot base frame, as `locate` returns them."""

    label: str
    x: float
    y: float
    z: float
    top: float
    reachable: bool = True
    # False for fixed scene features (the black rectangle): a destination, never fetched.
    movable: bool = True

    def as_dict(self) -> dict:
        return {
            "label": self.label,
            "x": round(self.x, 3),
            "y": round(self.y, 3),
            "z": round(self.z, 3),
            "top": round(self.top, 3),
            "reachable": self.reachable,
        }


@dataclass(frozen=True)
class Pose:
    x: float
    y: float
    z: float

    def as_dict(self) -> dict:
        return {"x": round(self.x, 3), "y": round(self.y, 3), "z": round(self.z, 3)}

    def distance_to(self, other: Pose) -> float:
        return math.dist((self.x, self.y, self.z), (other.x, other.y, other.z))


def _trim(objects: list[SceneObject], gripper: Pose | None, max_objects: int) -> list[SceneObject]:
    """Keep the `max_objects` closest to the gripper, in that order (nearest first)."""
    if len(objects) <= max_objects:
        return list(objects)
    if gripper is None:
        return list(objects[:max_objects])
    ranked = sorted(objects, key=lambda o: gripper.distance_to(Pose(o.x, o.y, o.z)))
    return ranked[:max_objects]


def estimate_tokens(state: dict) -> int:
    """Conservative token estimate for a serialised state dict."""
    return math.ceil(len(repr(state)) / CHARS_PER_TOKEN)


def fit_budget(
    build: Callable[[list[SceneObject]], dict],
    objects: list[SceneObject],
    gripper: Pose | None,
    max_objects: int,
    max_tokens: int = MAX_STATE_TOKENS,
) -> dict:
    """Build a state and drop the farthest objects until it fits `max_tokens`.

    The task, the arm and the target always survive; only the object list shrinks, because an
    over-long sequence silently loses the option markers the answer is scored on.
    """
    kept = _trim(objects, gripper, max_objects)
    state = build(kept)
    while kept and estimate_tokens(state) > max_tokens:
        kept = kept[:-1]
        state = build(kept)
    return state


def skill_state(
    task: str,
    objects: list[SceneObject],
    gripper: Pose | None = None,
    held: str | None = None,
    gripper_open: bool = True,
    last_result: str = "",
    max_objects: int = 6,
) -> dict:
    """Track A state: what the task is, what is on the table, what the arm is holding.

    Joint angles are deliberately absent — a skill decision is about objects, and every number in
    the state is a number the model can copy into a wrong answer.
    """

    def build(kept: list[SceneObject]) -> dict:
        return {
            "task": task,
            "gripper": "open" if gripper_open else "closed",
            "holding": held or "nothing",
            "objects": [o.as_dict() for o in kept],
            "last_result": last_result or "none",
        }

    return fit_budget(build, objects, gripper, max_objects)


def worded_gap(gripper: Pose, target: SceneObject | Pose, min_m: float = 0.005) -> str:
    """Where the target is from the gripper, in words, largest distance first.

    Measured on the shipped checkpoints: given signed centimetres (`"left": 17.0`) the model chose
    `release` or `forward` whatever the numbers were (0–1 of 6 correct); given this sentence it
    chose the right motion 5 of 6 times. The model reads words, not arithmetic.
    """
    parts = []
    for positive, negative, delta in (
        ("forward", "back", target.x - gripper.x),
        ("left", "right", target.y - gripper.y),
        ("up", "down", target.z - gripper.z),
    ):
        cm = round(abs(delta) * 100)
        # A part that rounds to "0 cm back" reads as an instruction to move back: drop it.
        if abs(delta) >= min_m and cm > 0:
            direction = positive if delta > 0 else negative
            parts.append((abs(delta), f"{cm} cm {direction}"))
    parts.sort(reverse=True)
    return ", ".join(text for _, text in parts) or "at the gripper"


def primitive_state(
    task: str,
    gripper: Pose,
    target: SceneObject,
    gripper_open: bool = True,
    held: str | None = None,
    tolerance_m: float = 0.02,
) -> dict:
    """Track B state: the target and where it is from the gripper, as words.

    No coordinates and no joint angles: every number in the state measurably pulled the answer
    away from the gap (see `worded_gap`).
    """
    return {
        "task": task,
        "target": target.label,
        "target_is": worded_gap(gripper, target),
        "within_reach": gripper.distance_to(Pose(target.x, target.y, target.z)) <= tolerance_m,
        "gripper": "open" if gripper_open else "closed",
        "holding": held or "nothing",
    }


def grasp_point(obj: SceneObject, offset_m: float) -> SceneObject:
    """Where the gripper frame goes to grasp `obj`: its centre, shifted `offset_m` toward the base.

    The gripper frame sits outboard of the jaw centre; the scripted fetch applies the same shift
    (`cognibot_motion.pick_place_ik.GRASP_OFFSET`), so Track B aims where a grasp actually closes.
    """
    radial = math.hypot(obj.x, obj.y)
    scale = max(radial - offset_m, 0.0) / radial if radial > 1e-6 else 1.0
    return SceneObject(
        obj.label, obj.x * scale, obj.y * scale, obj.z, obj.top, obj.reachable, obj.movable
    )


def labels_in_task(task: str, labels: list[str]) -> list[str]:
    """Scene labels the task names verbatim, in the order the sentence names them.

    Object binding is done here, not by the model: asked which object a sentence names, the shipped
    checkpoints picked the right one 0–3 times in 7 across four phrasings (choice over labels, a
    lexical choice, yes/no per object). A label that appears in the task needs no model.
    """
    text = task.lower()
    found = [(text.find(label.lower()), label) for label in labels if label.lower() in text]
    return [label for _, label in sorted(found)]


def guard_state(task: str, mode: str, objects: list[SceneObject]) -> dict:
    """State for the guard questions: the request and what the robot can actually see."""
    return {
        "request": task,
        "control_mode": mode,
        "objects_visible": [o.label for o in objects] or ["none"],
    }
