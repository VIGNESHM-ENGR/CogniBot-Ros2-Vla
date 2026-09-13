import numpy as np
import pytest
from cognibot_motion.joint_limiter import JointLimiter


@pytest.fixture
def limiter():
    return JointLimiter(["a", "b"], np.array([-1.0, -2.0]), np.array([1.0, 2.0]), max_velocity=2.0)


def test_reorders_by_name(limiter):
    assert limiter.reorder(["b", "a"], [0.5, 0.1]).tolist() == [0.1, 0.5]
    assert limiter.reorder(["a"], [0.1]) is None


def test_clamps_to_range_with_margin(limiter):
    r = limiter.apply(np.array([5.0, 0.0]), np.array([0.99, 0.0]), dt=1.0)
    assert r.positions[0] == pytest.approx(0.995)
    assert r.clamped_joints == ("a",)
    assert not r.rate_limited


def test_rate_limits_the_largest_step(limiter):
    r = limiter.apply(np.array([0.5, -1.0]), np.array([0.0, 0.0]), dt=0.01)
    assert r.rate_limited
    assert np.abs(r.positions).max() == pytest.approx(0.02)
    assert r.positions[0] / r.positions[1] == pytest.approx(-0.5)  # direction preserved


def test_small_step_passes_untouched(limiter):
    r = limiter.apply(np.array([0.01, 0.0]), np.array([0.0, 0.0]), dt=0.01)
    assert r.positions.tolist() == [0.01, 0.0]
    assert not r.rate_limited and r.clamped_joints == ()
