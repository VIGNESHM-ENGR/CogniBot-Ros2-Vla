"""Pure joint-space limiting for streamed commands (position + velocity bounds).

The collision-sphere check (P2-T03/T05) plugs in next to this; until then the filter enforces
what the robot registry and the scene's joint ranges define.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class LimitResult:
    positions: np.ndarray
    clamped_joints: tuple[str, ...]
    rate_limited: bool


class JointLimiter:
    def __init__(
        self,
        names: list[str],
        lower: np.ndarray,
        upper: np.ndarray,
        max_velocity: float,
        margin: float = 0.005,
    ) -> None:
        if len(names) != len(lower) or len(names) != len(upper):
            raise ValueError("names, lower and upper must have the same length")
        self.names = list(names)
        self.lower = np.asarray(lower, dtype=float) + margin
        self.upper = np.asarray(upper, dtype=float) - margin
        self.max_velocity = float(max_velocity)

    def reorder(self, names: list[str], positions: list[float]) -> np.ndarray | None:
        """Positions in this limiter's joint order; None if any joint is missing."""
        lookup = dict(zip(names, positions, strict=False))
        try:
            return np.array([lookup[n] for n in self.names], dtype=float)
        except KeyError:
            return None

    def apply(self, target: np.ndarray, current: np.ndarray, dt: float) -> LimitResult:
        """Clamp `target` to the joint ranges and to `max_velocity * dt` away from `current`."""
        clamped = np.clip(target, self.lower, self.upper)
        clamped_joints = tuple(
            n for n, a, b in zip(self.names, target, clamped, strict=True) if a != b
        )
        step = clamped - current
        limit = self.max_velocity * max(dt, 1e-3)
        scale = np.max(np.abs(step)) / limit if limit > 0 else 0.0
        rate_limited = scale > 1.0
        if rate_limited:
            clamped = current + step / scale
        return LimitResult(clamped, clamped_joints, rate_limited)
