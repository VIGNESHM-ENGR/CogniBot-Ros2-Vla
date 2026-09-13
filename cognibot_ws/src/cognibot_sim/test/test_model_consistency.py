"""Model consistency test: compares SO-101 URDF and MuJoCo Menagerie MJCF.

Asserts:
- Same 6 joint names
- Joint limits match within 1e-3 rad
- Gripper-frame forward kinematics match within 5 mm at 50 random configurations
"""

import xml.etree.ElementTree as ET
from pathlib import Path

import mujoco
import numpy as np
import pytest
import xacro

try:
    from ament_index_python.packages import get_package_share_directory
except ImportError:
    import sys
    from types import ModuleType

    def get_package_share_directory(pkg: str) -> str:
        return str(find_package_root(pkg))

    _ament_mod = ModuleType("ament_index_python")
    _pkg_mod = ModuleType("ament_index_python.packages")
    _pkg_mod.get_package_share_directory = get_package_share_directory
    _ament_mod.packages = _pkg_mod
    sys.modules["ament_index_python"] = _ament_mod
    sys.modules["ament_index_python.packages"] = _pkg_mod


def find_package_root(pkg_name: str) -> Path:
    """Find a package directory (installed share or source tree)."""
    if get_package_share_directory is not None:
        try:
            share = Path(get_package_share_directory(pkg_name))
            if share.is_dir():
                return share
        except Exception:
            pass

    curr = Path(__file__).resolve()
    for p in curr.parents:
        cand = p / pkg_name
        if cand.is_dir():
            return cand
        cand_src = p / "src" / pkg_name
        if cand_src.is_dir():
            return cand_src
        cand_tp = p / "src" / "third_party"
        if cand_tp.is_dir():
            for sub in cand_tp.glob(f"**/{pkg_name}"):
                if sub.is_dir():
                    return sub
    raise FileNotFoundError(f"Package '{pkg_name}' not found")


@pytest.fixture(scope="module")
def so101_models():
    """Load both URDF and MJCF models in MuJoCo."""
    sim_dir = find_package_root("cognibot_sim")
    desc_dir = find_package_root("so101_description")

    xacro_file = sim_dir / "robots" / "so101" / "urdf" / "so101_mujoco.urdf.xacro"
    mjcf_file = sim_dir / "robots" / "so101" / "mjcf" / "so101.xml"

    assert xacro_file.is_file(), f"Missing xacro file: {xacro_file}"
    assert mjcf_file.is_file(), f"Missing MJCF file: {mjcf_file}"

    # Process xacro
    doc = xacro.process_file(
        str(xacro_file),
        mappings={"variant": "follower"},
    )
    urdf_str = doc.toxml()

    # Rewrite package:// so101_description/meshes to absolute path for MuJoCo
    mesh_path = (desc_dir / "meshes").resolve()
    urdf_str = urdf_str.replace("package://so101_description/meshes", str(mesh_path))

    # Strip inertia from dummy links if mass < 1e-6 (MuJoCo doesn't like 0-mass bodies)
    root = ET.fromstring(urdf_str)
    for link in root.findall("link"):
        inertial = link.find("inertial")
        if inertial is not None:
            mass = inertial.find("mass")
            if mass is not None:
                val = float(mass.attrib.get("value", 1.0))
                if val < 1e-6:
                    mass.set("value", "1e-4")
    urdf_cleaned = ET.tostring(root, encoding="unicode")

    m_urdf = mujoco.MjModel.from_xml_string(urdf_cleaned)
    m_mjcf = mujoco.MjModel.from_xml_path(str(mjcf_file))

    return m_urdf, m_mjcf


def test_joint_names(so101_models):
    """Verify all 6 joints exist with exact same names in both models."""
    m_urdf, m_mjcf = so101_models
    expected_joints = [
        "shoulder_pan",
        "shoulder_lift",
        "elbow_flex",
        "wrist_flex",
        "wrist_roll",
        "gripper",
    ]
    for j_name in expected_joints:
        id_urdf = mujoco.mj_name2id(m_urdf, mujoco.mjtObj.mjOBJ_JOINT, j_name)
        id_mjcf = mujoco.mj_name2id(m_mjcf, mujoco.mjtObj.mjOBJ_JOINT, j_name)
        assert id_urdf != -1, f"Joint '{j_name}' not found in URDF"
        assert id_mjcf != -1, f"Joint '{j_name}' not found in MJCF"


def test_joint_limits(so101_models):
    """Verify joint limits match within 1e-3 rad."""
    m_urdf, m_mjcf = so101_models
    expected_joints = [
        "shoulder_pan",
        "shoulder_lift",
        "elbow_flex",
        "wrist_flex",
        "wrist_roll",
        "gripper",
    ]
    for j_name in expected_joints:
        id_urdf = mujoco.mj_name2id(m_urdf, mujoco.mjtObj.mjOBJ_JOINT, j_name)
        id_mjcf = mujoco.mj_name2id(m_mjcf, mujoco.mjtObj.mjOBJ_JOINT, j_name)

        range_urdf = m_urdf.jnt_range[id_urdf]
        range_mjcf = m_mjcf.jnt_range[id_mjcf]

        np.testing.assert_allclose(
            range_urdf,
            range_mjcf,
            atol=1e-3,
            err_msg=f"Joint limits mismatch for '{j_name}': URDF={range_urdf}, MJCF={range_mjcf}",
        )


def test_forward_kinematics_consistency(so101_models):
    """Verify gripper-frame FK matches within 5 mm at 50 random configurations."""
    m_urdf, m_mjcf = so101_models
    d_urdf = mujoco.MjData(m_urdf)
    d_mjcf = mujoco.MjData(m_mjcf)

    joint_names = [
        "shoulder_pan",
        "shoulder_lift",
        "elbow_flex",
        "wrist_flex",
        "wrist_roll",
        "gripper",
    ]

    urdf_qpos_idx = [
        m_urdf.jnt_qposadr[mujoco.mj_name2id(m_urdf, mujoco.mjtObj.mjOBJ_JOINT, name)]
        for name in joint_names
    ]
    mjcf_qpos_idx = [
        m_mjcf.jnt_qposadr[mujoco.mj_name2id(m_mjcf, mujoco.mjtObj.mjOBJ_JOINT, name)]
        for name in joint_names
    ]

    ranges = np.array(
        [
            m_mjcf.jnt_range[mujoco.mj_name2id(m_mjcf, mujoco.mjtObj.mjOBJ_JOINT, name)]
            for name in joint_names
        ]
    )

    # Gripper target site or frame in each model
    site_mjcf = mujoco.mj_name2id(m_mjcf, mujoco.mjtObj.mjOBJ_SITE, "gripperframe")
    body_urdf = mujoco.mj_name2id(m_urdf, mujoco.mjtObj.mjOBJ_BODY, "gripper_link")
    pos_ee_local = np.array([-0.0079, -0.000218121, -0.0981274])

    rng = np.random.default_rng(42)
    max_err = 0.0

    for i in range(50):
        # Sample random valid joint configuration
        q = rng.uniform(ranges[:, 0], ranges[:, 1])

        # Assign to URDF
        d_urdf.qpos[urdf_qpos_idx] = q
        mujoco.mj_forward(m_urdf, d_urdf)

        # Assign to MJCF
        d_mjcf.qpos[mjcf_qpos_idx] = q
        mujoco.mj_forward(m_mjcf, d_mjcf)

        pos_urdf = d_urdf.xpos[body_urdf] + d_urdf.xmat[body_urdf].reshape(3, 3) @ pos_ee_local
        pos_mjcf = d_mjcf.site_xpos[site_mjcf]

        err = np.linalg.norm(pos_urdf - pos_mjcf)
        max_err = max(max_err, err)

        assert err <= 0.005, (
            f"Config {i}: FK error {err * 1000:.2f} mm exceeds 5 mm tolerance. "
            f"URDF={pos_urdf}, MJCF={pos_mjcf}"
        )

    print(f"\nFK consistency verified across 50 configs. Max error: {max_err * 1000:.4f} mm")


def test_exported_scene_compilation():
    """Verify that so101_pick_and_place.xml loads cleanly in MuJoCo."""
    sim_pkg = find_package_root("cognibot_sim")
    scene_path = sim_pkg / "scenes/so101_pick_and_place.xml"
    assert scene_path.exists(), f"Scene file not found: {scene_path}"

    model = mujoco.MjModel.from_xml_path(str(scene_path))
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)

    body_names = [mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, i) for i in range(model.nbody)]
    assert "green_cube" in body_names
    assert "blue_target" in body_names

    cam_names = [mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_CAMERA, i) for i in range(model.ncam)]
    assert "wrist_cam" in cam_names
    assert "front_rgbd" in cam_names

    act_names = [mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_ACTUATOR, i) for i in range(model.nu)]
    assert len(act_names) == 6
