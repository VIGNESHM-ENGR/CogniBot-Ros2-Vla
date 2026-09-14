"""Grounding math against a known pinhole setup (no ROS graph)."""

import numpy as np
import pytest
from cognibot_vlm.grounding import (
    Box,
    GroundingError,
    deproject,
    ground,
    median_depth,
    parse_boxes,
    to_pixels,
    transform_point,
)

K = np.array([[500.0, 0.0, 320.0], [0.0, 500.0, 240.0], [0.0, 0.0, 1.0]])


def test_parse_plain_and_fenced_json():
    plain = parse_boxes('[{"bbox_2d": [100, 200, 300, 400], "label": "red cube"}]')
    assert plain == [Box("red cube", (100.0, 200.0, 300.0, 400.0))]
    fenced = parse_boxes('Sure:\n```json\n{"bbox_2d": [300, 400, 100, 200], "label": "x"}\n```')
    assert fenced[0].xyxy == (100.0, 200.0, 300.0, 400.0)  # corners re-ordered


def test_parse_rejects_garbage():
    with pytest.raises(GroundingError):
        parse_boxes("I cannot see any cube.")
    with pytest.raises(GroundingError):
        parse_boxes('[{"bbox_2d": [1, 2, 3], "label": "short"}]')


def test_to_pixels_scales_and_clips():
    assert to_pixels((0, 0, 1000, 1000), 640, 480) == (0, 0, 639, 479)
    assert to_pixels((500, 500, 600, 600), 640, 480) == (320, 240, 384, 288)
    assert to_pixels((-10, 0, 2000, 10), 640, 480) == (0, 0, 639, 5)


def test_median_depth_ignores_invalid_values():
    depth = np.full((480, 640), 0.8)
    depth[240:245, 320:325] = np.nan
    depth[250:255, 330:335] = 0.0
    depth[260:262, 340:342] = np.inf
    assert median_depth(depth, (300, 220, 360, 280)) == pytest.approx(0.8)
    with pytest.raises(GroundingError):
        median_depth(np.zeros((480, 640)), (300, 220, 360, 280))


def test_median_depth_uses_inner_half_of_the_box():
    depth = np.full((100, 100), 5.0)  # background
    depth[40:60, 40:60] = 1.0  # object in the middle of a 40×40 box
    assert median_depth(depth, (30, 30, 69, 69)) == pytest.approx(1.0)


def test_deproject_and_transform_round_trip():
    point_cam = np.array([0.1, -0.05, 0.7])
    u = K[0, 0] * point_cam[0] / point_cam[2] + K[0, 2]
    v = K[1, 1] * point_cam[1] / point_cam[2] + K[1, 2]
    assert np.allclose(deproject(u, v, point_cam[2], K), point_cam, atol=1e-9)
    t = np.eye(4)
    t[:3, :3] = [[0, 0, 1], [-1, 0, 0], [0, -1, 0]]  # optical → ROS body convention
    t[:3, 3] = [0.5, 0.0, 0.3]
    assert np.allclose(transform_point(point_cam, t), [1.2, -0.1, 0.35])


def test_ground_recovers_a_known_cube_within_a_millimetre():
    depth = np.full((480, 640), 1.2)
    cube_cam = np.array([0.06, 0.03, 0.9])
    u = K[0, 0] * cube_cam[0] / cube_cam[2] + K[0, 2]
    v = K[1, 1] * cube_cam[1] / cube_cam[2] + K[1, 2]
    depth[int(v) - 10 : int(v) + 11, int(u) - 10 : int(u) + 11] = cube_cam[2]
    box = Box("cube", ((u - 10) / 0.64, (v - 10) / 0.48, (u + 10) / 0.64, (v + 10) / 0.48))
    point, bbox_px = ground(box, depth, K, np.eye(4))
    assert np.linalg.norm(point - cube_cam) < 1e-3
    assert bbox_px == tuple(round(c) for c in (u - 10, v - 10, u + 10, v + 10))
