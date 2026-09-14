"""Ground a VLM bounding box to a 3D point: parse → pixels → depth → deproject → base frame.

Pure numpy so it is testable without ROS. Qwen3-VL answers grounding queries with JSON like
`[{"bbox_2d": [x1, y1, x2, y2], "label": "red cube"}]`; the box scale is a parameter because the
Qwen family has used both absolute pixels (Qwen2.5-VL) and 0–1000 normalized coordinates
(Qwen3-VL cookbook). `BOX_SCALE` records what was verified against the simulator (P4-T03).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

import numpy as np

# Qwen3-VL-4B-Instruct (GGUF, llama.cpp): boxes normalized to 0–1000 on both axes.
BOX_SCALE = 1000.0


@dataclass(frozen=True)
class Box:
    label: str
    xyxy: tuple[float, float, float, float]
    confidence: float = -1.0


class GroundingError(ValueError):
    """The model answer or the depth image cannot yield a 3D point."""


def parse_boxes(text: str) -> list[Box]:
    """Extract `bbox_2d` entries from a model answer (plain JSON or inside a ```json fence)."""
    match = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    payload = match.group(1) if match else text
    # Outermost structure first: a lone object holds its own "[x1, y1, x2, y2]" list.
    candidates = [(payload.find(o), payload.rfind(c)) for o, c in ("[]", "{}")]
    candidates = [(s, e) for s, e in candidates if s >= 0 and e > s]
    if not candidates:
        raise GroundingError(f"no JSON in model answer: {text[:120]!r}")
    start, end = min(candidates)
    try:
        data = json.loads(payload[start : end + 1])
    except json.JSONDecodeError as exc:
        raise GroundingError(f"invalid JSON in model answer: {exc}") from exc
    entries = data if isinstance(data, list) else [data]
    boxes = []
    for entry in entries:
        if not isinstance(entry, dict) or "bbox_2d" not in entry:
            continue
        xyxy = entry["bbox_2d"]
        if not (isinstance(xyxy, list) and len(xyxy) == 4):
            raise GroundingError(f"bbox_2d must have four numbers: {xyxy!r}")
        x1, y1, x2, y2 = (float(v) for v in xyxy)
        confidence = entry.get("confidence", entry.get("score", -1.0))
        boxes.append(
            Box(
                label=str(entry.get("label", "")),
                xyxy=(min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)),
                confidence=float(confidence),
            )
        )
    if not boxes:
        raise GroundingError("model answer contains no bbox_2d")
    return boxes


def to_pixels(
    xyxy: tuple[float, float, float, float], width: int, height: int, scale: float = BOX_SCALE
) -> tuple[int, int, int, int]:
    """Scale a box from `scale`-normalized coordinates to integer pixels, clipped to the image."""
    sx, sy = width / scale, height / scale
    x1 = int(np.clip(round(xyxy[0] * sx), 0, width - 1))
    y1 = int(np.clip(round(xyxy[1] * sy), 0, height - 1))
    x2 = int(np.clip(round(xyxy[2] * sx), x1, width - 1))
    y2 = int(np.clip(round(xyxy[3] * sy), y1, height - 1))
    return x1, y1, x2, y2


def median_depth(
    depth: np.ndarray, bbox_px: tuple[int, int, int, int], inner: float = 0.5
) -> float:
    """Median depth (m) over the central `inner` fraction of the box, ignoring NaN, inf and <= 0."""
    x1, y1, x2, y2 = bbox_px
    w, h = x2 - x1 + 1, y2 - y1 + 1
    mx, my = int((w - w * inner) / 2), int((h - h * inner) / 2)
    patch = np.asarray(depth, dtype=float)[y1 + my : y2 - my + 1, x1 + mx : x2 - mx + 1]
    valid = patch[np.isfinite(patch) & (patch > 0)]
    if valid.size == 0:
        raise GroundingError("no valid depth inside the box")
    return float(np.median(valid))


def deproject(u: float, v: float, z: float, k: np.ndarray) -> np.ndarray:
    """Pixel (u, v) at depth z (m along the optical axis) → point in the camera optical frame."""
    k = np.asarray(k, dtype=float).reshape(3, 3)
    fx, fy, cx, cy = k[0, 0], k[1, 1], k[0, 2], k[1, 2]
    return np.array([(u - cx) * z / fx, (v - cy) * z / fy, z])


def transform_point(point: np.ndarray, t_target_camera: np.ndarray) -> np.ndarray:
    """Apply a 4×4 homogeneous transform (target ← camera) to a point."""
    p = np.append(np.asarray(point, dtype=float), 1.0)
    return (np.asarray(t_target_camera, dtype=float) @ p)[:3]


def ground(
    box: Box,
    depth: np.ndarray,
    k: np.ndarray,
    t_target_camera: np.ndarray,
    scale: float = BOX_SCALE,
) -> tuple[np.ndarray, tuple[int, int, int, int]]:
    """Box → (point in the target frame, pixel box). Depth is (H, W) metres in the optical frame."""
    height, width = depth.shape[:2]
    bbox_px = to_pixels(box.xyxy, width, height, scale)
    z = median_depth(depth, bbox_px)
    u = (bbox_px[0] + bbox_px[2]) / 2.0
    v = (bbox_px[1] + bbox_px[3]) / 2.0
    return transform_point(deproject(u, v, z, k), t_target_camera), bbox_px


TOP_SLAB_M = 0.004


def ground_top_face(
    box: Box,
    depth: np.ndarray,
    k: np.ndarray,
    t_target_camera: np.ndarray,
    scale: float = BOX_SCALE,
    inner: float = 1.0,
) -> tuple[np.ndarray, tuple[int, int, int, int]]:
    """Box → (centre of the object's highest visible surface, pixel box).

    An oblique camera sees the top and a side of a small object, so the 2D box centre and the
    median depth land on the near side of the top face (measured 9 mm on a 25 mm cube). Here
    every valid pixel of the box is deprojected into the target frame and the centroid of those
    within `TOP_SLAB_M` of the highest point is returned (a per-axis median, so the thin strip of
    side face inside the slab does not pull it); z is that surface's height. The whole box is
    used because the slab, not a crop, isolates the surface: cropping would trim the far edge of
    the top face and bias the centre toward the camera.
    """
    height, width = depth.shape[:2]
    bbox_px = to_pixels(box.xyxy, width, height, scale)
    x1, y1, x2, y2 = bbox_px
    w, h = x2 - x1 + 1, y2 - y1 + 1
    mx, my = int((w - w * inner) / 2), int((h - h * inner) / 2)
    us, vs = np.meshgrid(np.arange(x1 + mx, x2 - mx + 1), np.arange(y1 + my, y2 - my + 1))
    zs = np.asarray(depth, dtype=float)[vs, us]
    valid = np.isfinite(zs) & (zs > 0)
    if not valid.any():
        raise GroundingError("no valid depth inside the box")
    kk = np.asarray(k, dtype=float).reshape(3, 3)
    u, v, z = us[valid].astype(float), vs[valid].astype(float), zs[valid]
    cam = np.stack([(u - kk[0, 2]) * z / kk[0, 0], (v - kk[1, 2]) * z / kk[1, 1], z], axis=1)
    t = np.asarray(t_target_camera, dtype=float)
    pts = cam @ t[:3, :3].T + t[:3, 3]
    top = pts[pts[:, 2] >= pts[:, 2].max() - TOP_SLAB_M]
    return np.median(top, axis=0), bbox_px
