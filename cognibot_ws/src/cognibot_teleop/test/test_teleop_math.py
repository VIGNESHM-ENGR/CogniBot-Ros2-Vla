import numpy as np
import pytest
from cognibot_teleop.teleop_math import Workspace, clamp_to_workspace, integrate_target

WS = Workspace(center=np.array([0.0, 0.0, 0.12]), r_min=0.08, r_max=0.38, z_min=0.01)


def test_inside_is_unchanged():
    p = np.array([0.2, 0.05, 0.15])
    assert clamp_to_workspace(p, WS).tolist() == p.tolist()


def test_outer_shell_and_floor():
    far = clamp_to_workspace(np.array([1.0, 0.0, 0.12]), WS)
    assert np.linalg.norm(far - WS.center) == pytest.approx(0.38)
    low = clamp_to_workspace(np.array([0.2, 0.0, -0.3]), WS)
    assert low[2] >= 0.01


def test_inner_shell():
    near = clamp_to_workspace(np.array([0.01, 0.0, 0.12]), WS)
    assert np.linalg.norm(near - WS.center) == pytest.approx(0.08)


def test_integrate_scales_and_clips_command():
    t = integrate_target(np.array([0.2, 0.0, 0.15]), np.array([2.0, 0.0, -1.0]), 0.1, 0.5, WS)
    assert t.tolist() == pytest.approx([0.25, 0.0, 0.10])
