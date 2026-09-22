"""Blur a simulator frame to the sharpness of the frames a checkpoint was trained on.

MuJoCo renders perfectly sharp frames. The SmolVLA arena dataset ran every frame through a camera
model whose Gaussian blur was never below 0.5 px (side median 0.99, wrist median 0.42 px, from
meta/generation.json); its exposure, contrast and colour were randomised per episode, so those are
left as rendered.
"""

from __future__ import annotations

import cv2
import numpy as np


def blur(rgb: np.ndarray, sigma: float) -> np.ndarray:
    """Return `rgb` with a Gaussian blur of `sigma` pixels (unchanged when sigma <= 0)."""
    if sigma <= 0:
        return rgb
    return cv2.GaussianBlur(rgb, (0, 0), sigmaX=sigma)
