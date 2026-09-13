"""Recolor robot materials in an MJCF scene without editing the committed file.

The tinted copy is written to another directory, so relative compiler asset
directories are rewritten to absolute paths.
"""

from __future__ import annotations

import tempfile
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from pathlib import Path

ROBOT_COLORS: dict[str, tuple[float, float, float, float] | None] = {
    "stock": None,
    "red": (0.72, 0.07, 0.07, 1.0),
}

_ASSET_DIR_ATTRS = ("meshdir", "texturedir", "assetdir")


def tint_scene(
    scene: Path,
    materials: Sequence[str],
    rgba: tuple[float, float, float, float],
    out_dir: Path | None = None,
) -> Path:
    """Write a copy of `scene` with `materials` set to `rgba` and return its path.

    Raises ValueError if a listed material is not defined in the scene.
    """
    scene = Path(scene).resolve()
    tree = ET.parse(scene)
    root = tree.getroot()

    for compiler in root.iter("compiler"):
        for attr in _ASSET_DIR_ATTRS:
            value = compiler.get(attr)
            if value is not None and not Path(value).is_absolute():
                compiler.set(attr, str((scene.parent / value).resolve()))

    wanted = set(materials)
    rgba_str = " ".join(f"{c:g}" for c in rgba)
    for material in root.iter("material"):
        if material.get("name") in wanted:
            material.set("rgba", rgba_str)
            wanted.discard(material.get("name"))
    if wanted:
        raise ValueError(f"Materials not found in {scene.name}: {sorted(wanted)}")

    if out_dir is None:
        out_dir = Path(tempfile.mkdtemp(prefix="cognibot_scene_"))
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / scene.name
    tree.write(out_path, encoding="unicode")
    return out_path
