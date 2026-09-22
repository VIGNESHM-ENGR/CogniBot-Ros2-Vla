import numpy as np
import pytest

pytest.importorskip("cv2")
from lerobot_robot_cognibot.look import blur  # noqa: E402


def _frame() -> np.ndarray:
    return np.random.default_rng(0).integers(0, 256, (48, 64, 3), dtype=np.uint8)


def _roughness(image: np.ndarray) -> float:
    return float(np.abs(np.diff(image[..., 0].astype(int), axis=1)).mean())


def test_blur_smooths_and_keeps_shape():
    frame = _frame()
    out = blur(frame, 1.0)
    assert out.shape == frame.shape and out.dtype == np.uint8
    assert _roughness(out) < _roughness(frame)


def test_zero_sigma_is_identity():
    frame = _frame()
    assert blur(frame, 0.0) is frame
