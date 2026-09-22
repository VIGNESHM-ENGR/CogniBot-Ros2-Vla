"""Launch test for camera topic publication and reprojection accuracy.

Verifies:
1. /mujoco_camera_plugin/front_rgbd/color and depth are published at >= 15 Hz.
2. The known green cube in so101_pick_and_place.xml (pos: 0.274100, -0.019501, 0.012445)
   reprojects into front_rgbd camera frame within 10 px of the visual green-pixel centroid.
"""

import time
import unittest
from pathlib import Path

import launch
import launch_testing
import launch_testing.actions
import numpy as np
import pytest
import rclpy
from ament_index_python.packages import get_package_share_directory
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from rclpy.qos import QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import CameraInfo, Image


@pytest.mark.launch_test
def generate_test_description():
    sim_launch_path = Path(get_package_share_directory("cognibot_sim")) / "launch/sim.launch.py"

    sim_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(str(sim_launch_path)),
        launch_arguments={
            "robot": "so101",
            "headless": "true",
            "use_sim_time": "true",
        }.items(),
    )

    return (
        launch.LaunchDescription(
            [
                sim_launch,
                launch_testing.actions.ReadyToTest(),
            ]
        ),
        {"sim_launch": sim_launch},
    )


class TestCameraReprojection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rclpy.init()

    @classmethod
    def tearDownClass(cls):
        rclpy.shutdown()

    def setUp(self):
        self.node = rclpy.create_node("test_camera_reprojection_client")

    def tearDown(self):
        self.node.destroy_node()

    def test_camera_topics_and_reprojection(self):
        qos_best_effort = QoSProfile(depth=10)
        qos_best_effort.reliability = ReliabilityPolicy.BEST_EFFORT

        color_msgs = []
        depth_msgs = []
        camera_info_msgs = []

        def color_cb(msg):
            color_msgs.append((time.time(), msg))

        def depth_cb(msg):
            depth_msgs.append((time.time(), msg))

        def info_cb(msg):
            camera_info_msgs.append(msg)

        _sub_color = self.node.create_subscription(
            Image,
            "/mujoco_camera_plugin/front_rgbd/color",
            color_cb,
            qos_best_effort,
        )
        _sub_depth = self.node.create_subscription(
            Image,
            "/mujoco_camera_plugin/front_rgbd/depth",
            depth_cb,
            qos_best_effort,
        )
        _sub_info = self.node.create_subscription(
            CameraInfo,
            "/mujoco_camera_plugin/front_rgbd/camera_info",
            info_cb,
            qos_best_effort,
        )

        # Collect frames for up to 10 seconds
        start_wait = time.time()
        while time.time() - start_wait < 10.0:
            rclpy.spin_once(self.node, timeout_sec=0.1)
            if len(color_msgs) >= 20 and len(depth_msgs) >= 20 and len(camera_info_msgs) >= 1:
                break

        self.assertGreaterEqual(
            len(color_msgs), 15, f"Expected >= 15 color frames, got {len(color_msgs)}"
        )
        self.assertGreaterEqual(
            len(depth_msgs), 15, f"Expected >= 15 depth frames, got {len(depth_msgs)}"
        )
        self.assertGreaterEqual(len(camera_info_msgs), 1, "Did not receive CameraInfo message")

        # 1. Check publish rate >= 15 Hz
        t_color = [t for t, _ in color_msgs]
        duration_color = t_color[-1] - t_color[0]
        if duration_color > 0:
            rate_color = (len(t_color) - 1) / duration_color
            self.assertGreaterEqual(
                rate_color,
                14.0,  # 14-15 Hz tolerance
                f"Color frame rate {rate_color:.1f} Hz < 14.0 Hz",
            )

        t_depth = [t for t, _ in depth_msgs]
        duration_depth = t_depth[-1] - t_depth[0]
        if duration_depth > 0:
            rate_depth = (len(t_depth) - 1) / duration_depth
            self.assertGreaterEqual(
                rate_depth,
                14.0,
                f"Depth frame rate {rate_depth:.1f} Hz < 14.0 Hz",
            )

        # 2. Check reprojection
        last_color_msg = color_msgs[-1][1]
        self.assertEqual(last_color_msg.encoding, "rgb8")
        h, w = last_color_msg.height, last_color_msg.width
        self.assertEqual((w, h), (640, 480))

        img = np.frombuffer(last_color_msg.data, dtype=np.uint8).reshape((h, w, 3))

        # Find green cube centroid
        green_mask = (img[:, :, 1] > 150) & (img[:, :, 0] < 80) & (img[:, :, 2] < 80)
        self.assertTrue(np.any(green_mask), "No green pixels found in camera image for green_cube")

        y_idx, x_idx = np.where(green_mask)
        u_centroid = float(np.mean(x_idx))
        v_centroid = float(np.mean(y_idx))

        # Known spawn of green cube in world frame: (0.274100, -0.019501, 0.012445)
        # Camera in world frame: pos=(0.56, 0.08, 0.36),
        # quat=[0.651157, 0.651157, -0.275672, -0.275672]
        from scipy.spatial.transform import Rotation as R

        p_world = np.array([0.274100, -0.019501, 0.012445])
        t_cam = np.array([0.56, 0.08, 0.36])
        cam_quat = [0.651157, 0.651157, -0.275672, -0.275672]

        rot = R.from_quat(cam_quat)
        p_cam = rot.inv().apply(p_world - t_cam)

        info = camera_info_msgs[0]
        K = np.array(info.k).reshape(3, 3)
        fx, fy = K[0, 0], K[1, 1]
        cx, cy = K[0, 2], K[1, 2]

        u_proj = fx * (p_cam[0] / p_cam[2]) + cx
        v_proj = fy * (p_cam[1] / p_cam[2]) + cy

        error_u = abs(u_proj - u_centroid)
        error_v = abs(v_proj - v_centroid)

        self.assertLessEqual(
            error_u,
            10.0,
            f"Reprojection u error {error_u:.2f} px exceeds 10 px "
            f"(proj: {u_proj:.2f}, detected: {u_centroid:.2f})",
        )
        self.assertLessEqual(
            error_v,
            10.0,
            f"Reprojection v error {error_v:.2f} px exceeds 10 px "
            f"(proj: {v_proj:.2f}, detected: {v_centroid:.2f})",
        )
