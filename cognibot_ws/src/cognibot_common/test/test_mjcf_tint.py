"""Tests for mjcf_tint."""

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from cognibot_common.mjcf_tint import ROBOT_COLORS, tint_scene

SCENE = """<mujoco>
  <compiler angle="radian" meshdir="../assets"/>
  <asset>
    <material name="arm" rgba="1 0.82 0.12 1"/>
    <material name="motor" rgba="0.1 0.1 0.1 1"/>
  </asset>
</mujoco>
"""


@pytest.fixture
def scene(tmp_path: Path) -> Path:
    scenes = tmp_path / "scenes"
    scenes.mkdir()
    path = scenes / "scene.xml"
    path.write_text(SCENE)
    return path


def _materials(path: Path) -> dict[str, str]:
    return {m.get("name"): m.get("rgba") for m in ET.parse(path).getroot().iter("material")}


def test_tints_only_listed_materials(scene: Path, tmp_path: Path) -> None:
    out = tint_scene(scene, ["arm"], ROBOT_COLORS["red"], tmp_path / "out")
    mats = _materials(out)
    assert mats["arm"] == "0.72 0.07 0.07 1"
    assert mats["motor"] == "0.1 0.1 0.1 1"
    assert _materials(scene)["arm"] == "1 0.82 0.12 1"


def test_meshdir_made_absolute(scene: Path, tmp_path: Path) -> None:
    out = tint_scene(scene, ["arm"], ROBOT_COLORS["red"], tmp_path / "out")
    meshdir = ET.parse(out).getroot().find("compiler").get("meshdir")
    assert Path(meshdir) == (tmp_path / "assets").resolve()


def test_unknown_material_raises(scene: Path, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="missing"):
        tint_scene(scene, ["arm", "missing"], ROBOT_COLORS["red"], tmp_path / "out")


@pytest.mark.parametrize("robot", ["so101", "panda"])
def test_real_scenes_compile_tinted(robot: str, tmp_path: Path) -> None:
    mujoco = pytest.importorskip("mujoco")
    from cognibot_common.robot_registry import load_robot

    cfg = load_robot(robot)
    out = tint_scene(cfg.mjcf.scene, cfg.mjcf.tint_materials, ROBOT_COLORS["red"], tmp_path)
    model = mujoco.MjModel.from_xml_path(str(out))
    for name in cfg.mjcf.tint_materials:
        rgba = model.mat_rgba[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_MATERIAL, name)]
        assert rgba == pytest.approx(ROBOT_COLORS["red"], abs=1e-6)
