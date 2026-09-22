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


def primitive_state(
    task: str,
    gripper: Pose,
    target: SceneObject,
    joints_deg: dict[str, float],
    gripper_open: bool = True,
    held: str | None = None,
    tolerance_m: float = 0.02,
) -> dict:
    """Track B state: where the gripper is, where the target is, and the gap between them.

    The delta is given explicitly because asking a text encoder to subtract two coordinate triples
    is asking for the failure mode the benchmark already predicts.
    """
    dx, dy, dz = target.x - gripper.x, target.y - gripper.y, target.z - gripper.z
    return {
        "task": task,
        "gripper_position": gripper.as_dict(),
        "target": target.as_dict(),
        "gap_cm": {
            "forward": round(dx * 100, 1),
            "left": round(dy * 100, 1),
            "up": round(dz * 100, 1),
        },
        "distance_cm": round(math.dist((0, 0, 0), (dx, dy, dz)) * 100, 1),
        "within_tolerance": math.dist((0, 0, 0), (dx, dy, dz)) <= tolerance_m,
        "gripper": "open" if gripper_open else "closed",
        "holding": held or "nothing",
        "joints_deg": {name: round(value, 1) for name, value in joints_deg.items()},
    }


def guard_state(task: str, mode: str, objects: list[SceneObject]) -> dict:
    """State for the guard questions: the request and what the robot can actually see."""
    return {
        "request": task,
        "control_mode": mode,
        "objects_visible": [o.label for o in objects] or ["none"],
    }
