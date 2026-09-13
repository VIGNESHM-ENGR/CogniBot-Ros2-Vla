"""Scripted top-down pick-and-place geometry on the MuJoCo scene (no planner).

Damped least squares on the gripper site position plus a soft "approach axis points down" term:
5 DOF covers 3 position + 2 pointing directions, and the soft weight lets the solver tilt near the
edge of the workspace where an exact top-down pose is unreachable.
"""

from __future__ import annotations

from dataclasses import dataclass

import mujoco
import numpy as np

GRIPPER_OPEN = 1.2
GRIPPER_CLOSED = -0.1  # below the cube width so the jaws squeeze (the controller allows stalling)
HOVER = 0.06  # m above grasp and drop heights
ORIENTATION_WEIGHT = 0.1
# The gripperframe site sits 2 cm outboard of the jaw centre (MODIFICATIONS.md aligned it to the
# URDF gripper_frame_link), so grasp targets are shifted 2 cm towards the base.
GRASP_OFFSET = 0.02
DROP_CLEARANCE = 0.012  # object centre above the surface when released


@dataclass(frozen=True)
class Waypoint:
    stage: str
    kind: str  # "arm" or "gripper"
    xyz: tuple[float, float, float] | None
    gripper: float | None
    seconds: float


def solve_top_down_ik(
    model: mujoco.MjModel,
    joints: list[str],
    site: str,
    target: np.ndarray,
    seed: np.ndarray,
    iters: int = 300,
) -> tuple[np.ndarray, float]:
    """Return (joint positions, position error in m) for the site reaching `target`."""
    data = mujoco.MjData(model)
    qadr = [model.jnt_qposadr[model.joint(j).id] for j in joints]
    dadr = [model.jnt_dofadr[model.joint(j).id] for j in joints]
    lo = np.array([model.jnt_range[model.joint(j).id][0] for j in joints])
    hi = np.array([model.jnt_range[model.joint(j).id][1] for j in joints])
    sid = model.site(site).id
    q = np.array(seed, dtype=float)
    jacp, jacr = np.zeros((3, model.nv)), np.zeros((3, model.nv))
    down = np.array([0.0, 0.0, -1.0])
    for _ in range(iters):
        data.qpos[qadr] = q
        mujoco.mj_kinematics(model, data)
        mujoco.mj_comPos(model, data)
        z_axis = data.site_xmat[sid].reshape(3, 3)[:, 2]
        err = np.concatenate(
            [target - data.site_xpos[sid], ORIENTATION_WEIGHT * np.cross(z_axis, down)]
        )
        if np.linalg.norm(err[:3]) < 1e-4 and np.linalg.norm(err[3:]) < 1e-3:
            break
        mujoco.mj_jacSite(model, data, jacp, jacr, sid)
        jac = np.vstack([jacp[:, dadr], ORIENTATION_WEIGHT * jacr[:, dadr]])
        dq = jac.T @ np.linalg.solve(jac @ jac.T + 1e-4 * np.eye(6), err)
        q = np.clip(q + dq, lo, hi)
    data.qpos[qadr] = q
    mujoco.mj_kinematics(model, data)
    return q, float(np.linalg.norm(target - data.site_xpos[sid]))


def toward_base(point: np.ndarray, distance: float) -> np.ndarray:
    """Shift a point horizontally towards the robot base (origin) by `distance`."""
    shifted = np.array(point, dtype=float)
    radial = np.linalg.norm(shifted[:2])
    if radial > 1e-6:
        shifted[:2] -= distance * shifted[:2] / radial
    return shifted


def fetch_waypoints(object_xyz: np.ndarray, hover: float = HOVER) -> list[Waypoint]:
    grasp = toward_base(object_xyz, GRASP_OFFSET)
    above = grasp + np.array([0.0, 0.0, hover])
    return [
        Waypoint("plan_approach", "gripper", None, GRIPPER_OPEN, 0.0),
        Waypoint("approach", "arm", tuple(above), None, 2.5),
        Waypoint("approach", "arm", tuple(grasp), None, 1.5),
        Waypoint("grasp", "gripper", None, GRIPPER_CLOSED, 0.0),
        Waypoint("lift", "arm", tuple(above), None, 1.5),
    ]


def place_waypoints(surface_xyz: np.ndarray, hover: float = HOVER) -> list[Waypoint]:
    drop = toward_base(surface_xyz, GRASP_OFFSET)
    drop[2] = surface_xyz[2] + DROP_CLEARANCE
    above = drop + np.array([0.0, 0.0, hover + DROP_CLEARANCE])
    return [
        Waypoint("plan_approach", "arm", tuple(above), None, 2.5),
        Waypoint("approach", "arm", tuple(drop), None, 1.5),
        Waypoint("release", "gripper", None, GRIPPER_OPEN, 0.0),
        Waypoint("retreat", "arm", tuple(above), None, 1.5),
    ]
