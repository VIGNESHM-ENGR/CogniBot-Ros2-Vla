#!/usr/bin/env python3
"""Export so101-nexus PickAndPlace scene to self-contained MJCF.

This script:
1. Instantiates `MuJoCoPickAndPlace-v1` from so101-nexus with a fixed seed (42).
2. Exports the compiled scene XML via `mujoco.mj_saveLastXML`.
3. Standardizes mesh paths to reference `../robots/so101/mjcf/assets/`.
4. Names the cube `green_cube` (recolored green so red is reserved for the robot) and the
   target disc `blue_target`.
5. Aligns robot joint limits (wrist_roll) and site poses with Menagerie / URDF.
6. Adds a front RGB-D camera (`front_rgbd`) with optimal workspace framing.
7. Renders and saves `cognibot_sim/scenes/preview.png`.
8. Verifies determinism and model compilation in MuJoCo.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

try:
    import gymnasium as gym
    import mujoco
    import so101_nexus.mujoco  # noqa: F401  (registers MuJoCoPickAndPlace-v1)
    from PIL import Image
except ImportError as e:
    raise SystemExit(f"Required package missing: {e}. Run inside cognibot/tools container.") from e


def export_scene(output_xml_path: Path, preview_png_path: Path, seed: int = 42) -> None:
    output_xml_path.parent.mkdir(parents=True, exist_ok=True)
    temp_raw_xml = output_xml_path.parent / "_temp_raw.xml"

    # Fix permission issue when running as non-root: copy so101 assets to writable tempdir
    import shutil
    import tempfile

    import so101_nexus.mujoco.pick_and_place as pap

    writable_so101_dir = Path(tempfile.mkdtemp(prefix="so101_nexus_assets_"))
    shutil.copytree(pap._SO101_DIR, writable_so101_dir, dirs_exist_ok=True)
    pap._SO101_DIR = writable_so101_dir
    pap._SO101_XML = writable_so101_dir / "so101.xml"

    # 1. Instantiate environment with fixed seed
    env = gym.make("MuJoCoPickAndPlace-v1")
    obs, info = env.reset(seed=seed)

    # Extract sampled positions from the environment
    unwrapped = env.unwrapped
    target_pos = unwrapped.model.body_pos[unwrapped._target_body_id].copy()

    # Find the active target slot (cube)
    target_slot = unwrapped._slots[unwrapped._target_slot_idx]
    cube_qpos = unwrapped.data.qpos[target_slot.qpos_addr : target_slot.qpos_addr + 7].copy()
    cube_pos = cube_qpos[:3]

    # Save raw compiled XML from MuJoCo
    mujoco.mj_saveLastXML(str(temp_raw_xml), unwrapped.model)
    env.close()

    # 2. Parse and customize XML
    tree = ET.parse(temp_raw_xml)
    root = tree.getroot()

    # Remove temporary raw XML
    if temp_raw_xml.exists():
        temp_raw_xml.unlink()

    root.attrib["model"] = "so101_pick_and_place"

    # Ensure compiler has meshdir
    compiler = root.find("compiler")
    if compiler is None:
        compiler = ET.Element("compiler")
        root.insert(0, compiler)
    compiler.attrib["angle"] = "radian"
    compiler.attrib["meshdir"] = "../robots/so101/mjcf/assets"

    # Rewrite mesh assets to plain file basenames
    asset = root.find("asset")
    if asset is not None:
        for mesh in asset.findall("mesh"):
            file_attr = mesh.attrib.get("file", "")
            if file_attr:
                mesh.attrib["file"] = Path(file_attr).name

    # Rename bodies, joints, and geoms for cube and target
    worldbody = root.find("worldbody")
    if worldbody is None:
        raise ValueError("worldbody not found in generated XML")

    # Align wrist_roll joint range and gripperframe site with P1-T03 alignment
    for joint in root.iter("joint"):
        if joint.attrib.get("name") == "wrist_roll":
            joint.attrib["range"] = "-2.74385 2.84121"

    for site in root.iter("site"):
        if site.attrib.get("name") == "gripperframe":
            site.attrib["pos"] = "-0.0079 -0.000218 -0.098127"

    # Ensure headlight provides good illumination
    visual = root.find("visual")
    if visual is not None:
        headlight = visual.find("headlight")
        if headlight is not None:
            headlight.attrib["diffuse"] = "0.6 0.6 0.6"
            headlight.attrib["ambient"] = "0.4 0.4 0.4"

    # Floor coloring
    floor = worldbody.find("./geom[@name='floor']")
    if floor is not None and "rgba" not in floor.attrib:
        floor.attrib["rgba"] = "0.8 0.8 0.8 1"

    for body in worldbody.findall("body"):
        name = body.attrib.get("name", "")
        # Pick slot cube body -> green_cube
        if name.startswith("pick_slot_"):
            body.attrib["name"] = "green_cube"
            body.attrib["pos"] = f"{cube_pos[0]:.6f} {cube_pos[1]:.6f} {cube_pos[2]:.6f}"
            for joint in body.findall("joint"):
                joint.attrib["name"] = "green_cube_joint"
            for freejoint in body.findall("freejoint"):
                freejoint.attrib["name"] = "green_cube_joint"
            for geom in body.findall("geom"):
                geom.attrib["name"] = "green_cube"
                geom.attrib["rgba"] = "0 1 0 1"

        # Target disc body -> blue_target
        elif name == "target":
            body.attrib["name"] = "blue_target"
            body.attrib["pos"] = f"{target_pos[0]:.6f} {target_pos[1]:.6f} {target_pos[2]:.6f}"
            for geom in body.findall("geom"):
                geom.attrib["name"] = "blue_target"

    # 3. Add front_rgbd camera with tabletop view
    # Position: (0.56, 0.08, 0.36) looking at (0.22, 0.08, 0.04)
    # Forward vector: [-0.718, 0, -0.696]
    # Right in image: +Y in world -> [0, 1, 0]
    # Up in image: [-0.696, 0, 0.718]
    front_cam = worldbody.find("./camera[@name='front_rgbd']")
    if front_cam is None:
        front_cam = ET.SubElement(worldbody, "camera")
    front_cam.attrib["name"] = "front_rgbd"
    front_cam.attrib["mode"] = "fixed"
    front_cam.attrib["pos"] = "0.56 0.08 0.36"
    front_cam.attrib["xyaxes"] = "0 1 0 -0.696 0 0.718"
    front_cam.attrib["fovy"] = "48"
    front_cam.attrib["resolution"] = "640 480"

    # Format XML nicely
    ET.indent(tree, space="  ")
    xml_str = ET.tostring(root, encoding="unicode")

    with open(output_xml_path, "w", encoding="utf-8") as f:
        f.write(xml_str)
        if not xml_str.endswith("\n"):
            f.write("\n")

    print(f"Exported scene to: {output_xml_path}")

    # 4. Verify compilation and render preview image
    model = mujoco.MjModel.from_xml_path(str(output_xml_path))
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)

    # Render from front_rgbd camera
    renderer = mujoco.Renderer(model, height=480, width=640)
    renderer.update_scene(data, camera="front_rgbd")
    rgb = renderer.render()
    img = Image.fromarray(rgb)
    img.save(str(preview_png_path))
    print(f"Rendered preview image to: {preview_png_path}")

    # Sanity checks
    body_names = [mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, i) for i in range(model.nbody)]
    assert "green_cube" in body_names, f"green_cube not in bodies: {body_names}"
    assert "blue_target" in body_names, f"blue_target not in bodies: {body_names}"
    cam_names = [mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_CAMERA, i) for i in range(model.ncam)]
    assert "front_rgbd" in cam_names, f"front_rgbd not in cameras: {cam_names}"
    assert "wrist_cam" in cam_names, f"wrist_cam not in cameras: {cam_names}"
    print("All scene assertions passed successfully.")


if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parents[4]
    output_xml = repo_root / "cognibot_ws/src/cognibot_sim/scenes/so101_pick_and_place.xml"
    preview_png = repo_root / "cognibot_ws/src/cognibot_sim/scenes/preview.png"
    export_scene(output_xml, preview_png, seed=42)
