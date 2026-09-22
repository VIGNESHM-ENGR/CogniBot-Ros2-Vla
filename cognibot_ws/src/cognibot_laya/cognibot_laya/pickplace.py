"""Track B's pick-and-place structure: stages read from the physics, not chosen by the model.

The model decides every motion. What it cannot see from text — whether the jaws actually hold
the cube, whether the cube fell, which point a grasp has to reach — is measured here from the
simulator's poses each step and handed to it as the `stage`, the `cube` state and a worded
direction to the stage's aim point. A missed grasp or a dropped cube sends the run back to the
approach instead of carrying on with an empty gripper.

Geometry follows the scripted pick (`cognibot_motion.pick_place_ik`): the gripper frame sits
`grasp_offset` outboard of the jaw centre, so grasp and drop points are shifted toward the base;
the approach and retreat hover `hover` above them.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from cognibot_laya.state import Pose, SceneObject, worded_gap

# Cube states the model reads.
ON_TABLE = "on the table"
IN_GRIPPER = "in the gripper"
MISSED = "not grasped: the gripper closed on nothing"
SLIPPED = "slipped out of the gripper"
PLACED = "in the target area"


@dataclass(frozen=True)
class Geometry:
    grasp_offset: float = 0.02  # m, gripper frame outboard of the jaw centre
    hover: float = 0.06  # m above grasp and drop points
    drop_clearance: float = 0.012  # m, cube centre above the surface when released
    align: float = 0.015  # m horizontal error that starts a descent
    realign: float = 0.025  # m horizontal error that aborts one (hysteresis)
    fine_reach: float = 0.012  # m, within it a grasp or release can work
    coarse_reach: float = 0.025  # m, within it a transit aim counts as reached
    lifted: float = 0.035  # m above the table the cube must be to count as lifted
    jaw_radius: float = 0.025  # m, cube centre this close to the jaw centre is held


@dataclass(frozen=True)
class Area:
    """A marked area on the table: centre and half extents in metres (base frame)."""

    label: str
    x: float
    y: float
    z: float
    half_x: float
    half_y: float

    def contains(self, p: SceneObject | Pose, height: float = 0.03) -> bool:
        return (
            abs(p.x - self.x) <= self.half_x
            and abs(p.y - self.y) <= self.half_y
            and p.z <= self.z + height
        )


@dataclass(frozen=True)
class Stage:
    name: str  # what the arm is doing, in words the model reads
    aim: Pose  # where the gripper frame should go next
    reach: float  # m, how close counts as arrived
    action: str = ""  # the one non-motion primitive this stage allows once within reach
    cube_state: str = ON_TABLE


def toward_base(x: float, y: float, distance: float) -> tuple[float, float]:
    """Shift a point horizontally toward the base by `distance` (as pick_place_ik.toward_base)."""
    r = math.hypot(x, y)
    if r < 1e-6:
        return x, y
    return x - distance * x / r, y - distance * y / r


def jaw_centre(gripper: Pose, g: Geometry) -> Pose:
    """The jaw centre for a gripper frame pose (the frame is `grasp_offset` outboard of it)."""
    x, y = toward_base(gripper.x, gripper.y, -g.grasp_offset)
    return Pose(x, y, gripper.z)


def cube_state(
    cube: SceneObject, gripper: Pose, gripper_open: bool, was_held: bool, area: Area, g: Geometry
) -> str:
    """What happened to the cube, judged from where it is relative to the jaws."""
    jaw = jaw_centre(gripper, g)
    held = (
        not gripper_open
        and math.hypot(cube.x - jaw.x, cube.y - jaw.y) <= g.jaw_radius
        and abs(cube.z - jaw.z) <= g.jaw_radius
    )
    if held:
        return IN_GRIPPER
    if gripper_open and area.contains(cube):
        return PLACED
    if was_held:
        return SLIPPED
    if not gripper_open:
        return MISSED
    return ON_TABLE


def horizontal(a: Pose, b: Pose) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def plan_stage(
    cube: SceneObject,
    gripper: Pose,
    gripper_open: bool,
    was_held: bool,
    area: Area,
    previous: str,
    g: Geometry,
) -> Stage:
    """The current stage and its aim point, from the poses alone."""
    state = cube_state(cube, gripper, gripper_open, was_held, area, g)
    label = cube.label
    gx, gy = toward_base(cube.x, cube.y, g.grasp_offset)
    grasp = Pose(gx, gy, cube.z)
    dx, dy = toward_base(area.x, area.y, g.grasp_offset)
    drop = Pose(dx, dy, area.z + g.drop_clearance)

    if state == PLACED:
        above = Pose(gripper.x, gripper.y, cube.z + g.hover)
        return Stage(f"move up, away from the {label}", above, g.coarse_reach, "done", state)
    if state in (MISSED, SLIPPED) and not gripper_open:
        return Stage("open the gripper to try again", gripper, math.inf, "release", state)
    if state == IN_GRIPPER:
        if cube.z < area.z + g.lifted and horizontal(gripper, drop) > g.realign:
            lift = Pose(gripper.x, gripper.y, grasp.z + g.hover)
            return Stage(f"lift the {label}", lift, g.coarse_reach, "", state)
        lowering = previous.startswith("lower the")
        if horizontal(gripper, drop) > (g.realign if lowering else g.align):
            above = Pose(drop.x, drop.y, drop.z + g.hover)
            return Stage(
                f"carry the {label} above the {area.label}", above, g.coarse_reach, "", state
            )
        return Stage(
            f"lower the {label} onto the {area.label}", drop, g.fine_reach, "release", state
        )
    # On the table (or just released a missed grasp): approach from above, then descend.
    descending = previous.startswith("lower onto")
    if horizontal(gripper, grasp) > (g.realign if descending else g.align):
        above = Pose(grasp.x, grasp.y, grasp.z + g.hover)
        return Stage(f"move above the {label}", above, g.coarse_reach, "", state)
    return Stage(f"lower onto the {label}", grasp, g.fine_reach, "grasp", state)


def within(stage: Stage, gripper: Pose) -> bool:
    return gripper.distance_to(stage.aim) <= stage.reach


def cm(p: SceneObject | Pose) -> dict:
    return {"x": round(p.x * 100, 1), "y": round(p.y * 100, 1), "z": round(p.z * 100, 1)}


def stage_state(
    task: str,
    stage: Stage,
    cube: SceneObject,
    gripper: Pose,
    gripper_open: bool,
    area: Area,
    positions: bool = True,
) -> dict:
    """What the model reads: the stage, where to go in words, and (optionally) the positions."""
    state = {
        "task": task,
        "stage": stage.name,
        "go_to": worded_gap(gripper, stage.aim) if math.isfinite(stage.reach) else "stay here",
        "within_reach": within(stage, gripper),
        "cube": {"label": cube.label, "state": stage.cube_state},
        "gripper": {"state": "open" if gripper_open else "closed"},
        "target_area": {"label": area.label, "cube_inside": stage.cube_state == PLACED},
    }
    if positions:
        state["cube"]["position_cm"] = cm(cube)
        state["gripper"]["position_cm"] = cm(gripper)
        state["target_area"]["position_cm"] = cm(Pose(area.x, area.y, area.z))
        state["target_area"]["size_cm"] = {
            "x": round(area.half_x * 200, 1),
            "y": round(area.half_y * 200, 1),
        }
    return state


def jog_distance(primitive: str, gripper: Pose, aim: Pose, step: float) -> float:
    """How far a chosen motion travels: one step, but not past the aim along that axis.

    The model picks the direction; this is the servo. Without it a fixed 2.5 cm step cannot
    settle inside a 1.2 cm grasp window. A motion away from the aim still travels a full step.
    """
    axis = {"forward": (0, 1), "back": (0, -1), "left": (1, 1), "right": (1, -1)}.get(primitive)
    if primitive in ("up", "down"):
        axis = (2, 1 if primitive == "up" else -1)
    if axis is None:
        return 0.0
    index, sign = axis
    gap = (aim.x - gripper.x, aim.y - gripper.y, aim.z - gripper.z)[index] * sign
    if gap <= 0:
        return step
    return max(min(step, gap), 0.003)
