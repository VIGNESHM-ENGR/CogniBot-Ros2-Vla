"""Pure teleop geometry: end-effector target integration and workspace clamping."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Workspace:
    center: np.ndarray
    r_min: float
    r_max: float
    z_min: float


def clamp_to_workspace(point: np.ndarray, ws: Workspace) -> np.ndarray:
    """Project `point` into the spherical shell around `ws.center` and above `ws.z_min`."""
    p = np.array(point, dtype=float)
    p[2] = max(p[2], ws.z_min)
    offset = p - ws.center
    r = float(np.linalg.norm(offset))
    if r < 1e-9:
        return ws.center + np.array([ws.r_min, 0.0, 0.0])
    r_clamped = min(max(r, ws.r_min), ws.r_max)
    if r_clamped != r:
        p = ws.center + offset * (r_clamped / r)
        p[2] = max(p[2], ws.z_min)
    return p


def integrate_target(
    target: np.ndarray, linear: np.ndarray, max_speed: float, dt: float, ws: Workspace
) -> np.ndarray:
    """Move the target by a normalized [-1, 1] velocity command for `dt`, then clamp it."""
    v = np.clip(np.asarray(linear, dtype=float), -1.0, 1.0) * max_speed
    return clamp_to_workspace(target + v * dt, ws)
