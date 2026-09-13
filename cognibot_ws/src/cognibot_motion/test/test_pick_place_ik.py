"""Pick-and-place geometry against the real SO-101 scene (no ROS graph)."""

import mujoco
import numpy as np
import pytest
from cognibot_common.robot_registry import load_robot
from cognibot_motion.pick_place_ik import (
    GRASP_OFFSET,
    fetch_waypoints,
    place_waypoints,
    solve_top_down_ik,
    toward_base,
)


@pytest.fixture(scope="module")
def scene():
    cfg = load_robot("so101")
    return cfg, mujoco.MjModel.from_xml_path(str(cfg.mjcf.scene))


def test_toward_base_shifts_radially():
    shifted = toward_base(np.array([0.3, 0.4, 0.1]), 0.05)
    assert np.linalg.norm(shifted[:2]) == pytest.approx(0.45)
    assert shifted[2] == pytest.approx(0.1)


def test_waypoint_stages_follow_the_action_contracts():
    fetch = {w.stage for w in fetch_waypoints(np.array([0.27, -0.02, 0.012]))}
    place = {w.stage for w in place_waypoints(np.array([0.3, 0.2, 0.001]))}
    assert fetch <= {"plan_approach", "approach", "grasp", "lift"}
    assert place <= {"plan_approach", "approach", "release", "retreat"}


def test_grasp_and_drop_points_are_reachable(scene):
    cfg, model = scene
    cube = model.body("green_cube").pos.copy()
    target = model.body("target").pos.copy()
    q = np.array(cfg.home_pose)
    joints = list(cfg.arm_joints)
    for plan, low_limit in ((fetch_waypoints(cube), 0.001), (place_waypoints(target), 0.01)):
        arm = [w for w in plan if w.kind == "arm"]
        low = min(w.xyz[2] for w in arm)
        for waypoint in arm:
            q, err = solve_top_down_ik(model, joints, cfg.ee_site, np.array(waypoint.xyz), q)
            # The grasp must be exact; hover points may tilt away near the workspace edge.
            limit = low_limit if waypoint.xyz[2] == low else 0.03
            assert err < limit, (waypoint, err)
    assert pytest.approx(0.02) == GRASP_OFFSET


def test_scripted_grasp_lifts_the_cube(scene):
    """Replay fetch in pure MuJoCo with position actuators and check the cube leaves the floor."""
    cfg, model = scene
    data = mujoco.MjData(model)
    joints = list(cfg.arm_joints) + [cfg.gripper.joint]
    act = [model.actuator(j).id for j in joints]
    qadr = [model.jnt_qposadr[model.joint(j).id] for j in joints]
    cube_id = model.body("green_cube").id

    def drive(target, seconds):
        start = data.ctrl[act].copy()
        steps = int(seconds / model.opt.timestep)
        for i in range(steps):
            data.ctrl[act] = start + (np.asarray(target) - start) * min(1.0, i / (0.8 * steps))
            mujoco.mj_step(model, data)

    home = list(cfg.home_pose)
    data.qpos[qadr] = home + [1.2]
    data.ctrl[act] = home + [1.2]
    mujoco.mj_forward(model, data)
    q, gripper = np.array(home), 1.2
    for w in fetch_waypoints(model.body("green_cube").pos.copy()):
        if w.kind == "arm":
            q, _ = solve_top_down_ik(model, list(cfg.arm_joints), cfg.ee_site, np.array(w.xyz), q)
            drive(list(q) + [gripper], w.seconds)
        else:
            gripper = w.gripper
            drive(list(q) + [gripper], 0.8)
    assert data.xpos[cube_id][2] > 0.05
