"""LeRobot `Robot` over ROS 2: joint states + image topics in, joint commands out."""

from __future__ import annotations

import logging
import math
from functools import cached_property
from typing import Any

from lerobot.robots import Robot
from lerobot.utils.errors import DeviceAlreadyConnectedError, DeviceNotConnectedError

from .config_cognibot import CognibotConfig, CognibotPandaConfig, CognibotSO101Config
from .ros_bridge import RosBridge

logger = logging.getLogger(__name__)


class CognibotRobot(Robot):
    config_class = CognibotConfig
    name = "cognibot"

    def __init__(self, config: CognibotConfig):
        super().__init__(config)
        self.config = config
        self.joints = list(config.arm_joints) + [config.gripper_joint]
        self._bridge: RosBridge | None = None

    # ── features ──

    @cached_property
    def observation_features(self) -> dict[str, type | tuple]:
        state = {f"{j}.pos": float for j in self.joints}
        images = {
            key: (self.config.image_height, self.config.image_width, 3)
            for key in self.config.camera_topics
        }
        return {**state, **images}

    @cached_property
    def action_features(self) -> dict[str, type]:
        return {f"{j}.pos": float for j in self.joints}

    # ── lifecycle ──

    @property
    def is_connected(self) -> bool:
        return self._bridge is not None

    def connect(self, calibrate: bool = True) -> None:
        if self._bridge is not None:
            raise DeviceAlreadyConnectedError(f"{self} already connected")
        bridge = RosBridge(
            self.config.node_name,
            self.config.joint_states_topic,
            self.config.command_topic,
            self.config.camera_topics,
        )
        if not bridge.wait_ready(
            list(self.config.camera_topics), self.joints, self.config.connect_timeout_s
        ):
            bridge.close()
            raise DeviceNotConnectedError(
                f"no joint states / images within {self.config.connect_timeout_s}s "
                f"(joints {self.config.joint_states_topic}, cameras {self.config.camera_topics})"
            )
        self._bridge = bridge
        if self.config.request_mode:
            self._set_mode("VLA", "robot_client connected")
        logger.info(
            "%s connected: %d joints, cameras %s",
            self,
            len(self.joints),
            list(self.config.camera_topics),
        )

    @property
    def is_calibrated(self) -> bool:
        return True

    def calibrate(self) -> None:
        pass

    def configure(self) -> None:
        pass

    def disconnect(self) -> None:
        if self._bridge is None:
            raise DeviceNotConnectedError(f"{self} is not connected")
        if self.config.request_mode:
            self._set_mode("IDLE", "robot_client disconnected")
        self._bridge.close()
        self._bridge = None

    # ── I/O ──

    def get_observation(self) -> dict[str, Any]:
        if self._bridge is None:
            raise DeviceNotConnectedError(f"{self} is not connected")
        scale = 180.0 / math.pi if self.config.state_degrees else 1.0
        obs: dict[str, Any] = {
            f"{j}.pos": v * scale
            for j, v in zip(self.joints, self._bridge.joints(self.joints), strict=True)
        }
        for key in self.config.camera_topics:
            obs[key] = self._bridge.image(key)
        return obs

    def send_action(self, action: dict[str, float]) -> dict[str, float]:
        if self._bridge is None:
            raise DeviceNotConnectedError(f"{self} is not connected")
        scale = math.pi / 180.0 if self.config.action_degrees else 1.0
        positions = [float(action[f"{j}.pos"]) * scale for j in self.joints]
        self._bridge.publish_command(self.joints, positions)
        return action

    def _set_mode(self, mode: str, reason: str) -> None:
        assert self._bridge is not None
        try:
            from cognibot_interfaces.msg import ControlMode
            from cognibot_interfaces.srv import SetControlMode
        except ImportError:
            logger.warning("cognibot_interfaces not available; not requesting %s", mode)
            return
        request = SetControlMode.Request()
        request.mode = getattr(ControlMode, mode)
        request.requester = self.config.node_name
        request.reason = reason
        result = self._bridge.call_service(SetControlMode, self.config.set_mode_service, request)
        if result is None:
            logger.warning("mode_manager unreachable; %s not requested", mode)
        elif not result.success:
            logger.warning("mode %s refused: %s", mode, result.message)


class CognibotSO101(CognibotRobot):
    config_class = CognibotSO101Config
    name = "cognibot_so101"


class CognibotPanda(CognibotRobot):
    config_class = CognibotPandaConfig
    name = "cognibot_panda"
