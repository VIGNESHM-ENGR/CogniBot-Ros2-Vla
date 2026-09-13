"""rclpy plumbing shared by the CogniBot LeRobot robots: one node on a background executor."""

from __future__ import annotations

import threading
import time
from typing import Any

import numpy as np
import rclpy
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, qos_profile_sensor_data
from rclpy.signals import SignalHandlerOptions
from sensor_msgs.msg import Image, JointState

RELIABLE_COMMAND = QoSProfile(reliability=ReliabilityPolicy.RELIABLE, depth=1)


def image_to_numpy(msg: Image) -> np.ndarray:
    """sensor_msgs/Image (rgb8 or bgr8) -> (H, W, 3) uint8 RGB without cv_bridge."""
    array = np.frombuffer(msg.data, dtype=np.uint8).reshape(msg.height, msg.step // 3, 3)
    array = array[:, : msg.width]
    if msg.encoding == "bgr8":
        array = array[:, :, ::-1]
    elif msg.encoding != "rgb8":
        raise ValueError(f"unsupported image encoding '{msg.encoding}'")
    return np.ascontiguousarray(array)


class RosBridge:
    def __init__(
        self, node_name: str, joint_states_topic: str, command_topic: str, cameras: dict[str, str]
    ):
        if not rclpy.ok():
            # Leave SIGINT/SIGTERM to the client: rclpy's handler would tear the context down
            # under the control loop and every later publish would raise.
            rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
        self.node: Node = rclpy.create_node(node_name)
        self._lock = threading.Lock()
        self._joints: dict[str, float] = {}
        self._images: dict[str, np.ndarray] = {}
        self._image_stamps: dict[str, float] = {}
        self.node.create_subscription(
            JointState, joint_states_topic, self._on_joints, qos_profile_sensor_data
        )
        for key, topic in cameras.items():
            self.node.create_subscription(
                Image, topic, lambda m, k=key: self._on_image(k, m), qos_profile_sensor_data
            )
        self._cmd = self.node.create_publisher(JointState, command_topic, RELIABLE_COMMAND)
        self._executor = SingleThreadedExecutor()
        self._executor.add_node(self.node)
        self._thread = threading.Thread(target=self._executor.spin, daemon=True)
        self._thread.start()

    def _on_joints(self, msg: JointState) -> None:
        with self._lock:
            self._joints.update(zip(msg.name, msg.position, strict=False))

    def _on_image(self, key: str, msg: Image) -> None:
        image = image_to_numpy(msg)
        with self._lock:
            self._images[key] = image
            self._image_stamps[key] = time.monotonic()

    def wait_ready(self, camera_keys: list[str], joint_names: list[str], timeout_s: float) -> bool:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            with self._lock:
                have_joints = all(j in self._joints for j in joint_names)
                have_images = all(k in self._images for k in camera_keys)
            if have_joints and have_images:
                return True
            time.sleep(0.05)
        return False

    def joints(self, names: list[str]) -> list[float]:
        with self._lock:
            return [self._joints.get(n, 0.0) for n in names]

    def image(self, key: str) -> np.ndarray:
        with self._lock:
            return self._images[key]

    def publish_command(self, names: list[str], positions: list[float]) -> None:
        msg = JointState()
        msg.header.stamp = self.node.get_clock().now().to_msg()
        msg.name = names
        msg.position = [float(p) for p in positions]
        self._cmd.publish(msg)

    def call_service(
        self, srv_type: Any, name: str, request: Any, timeout_s: float = 3.0
    ) -> Any | None:
        client = self.node.create_client(srv_type, name)
        try:
            if not client.wait_for_service(timeout_sec=timeout_s):
                return None
            future = client.call_async(request)
            deadline = time.monotonic() + timeout_s
            while not future.done() and time.monotonic() < deadline:
                time.sleep(0.02)
            return future.result() if future.done() else None
        finally:
            self.node.destroy_client(client)

    def close(self) -> None:
        self._executor.shutdown(timeout_sec=1.0)
        self._thread.join(timeout=2.0)
        if rclpy.ok():
            self.node.destroy_node()
