import numpy as np
import pytest
from lerobot_robot_cognibot.config_cognibot import CognibotSO101Config
from lerobot_robot_cognibot.ros_bridge import image_to_numpy


def test_so101_config_registered():
    cfg = CognibotSO101Config()
    assert cfg.type == "cognibot_so101"
    assert cfg.arm_joints[0] == "shoulder_pan" and cfg.gripper_joint == "gripper"
    assert set(cfg.camera_topics) == {"front", "wrist"}


def test_features_follow_config():
    from lerobot_robot_cognibot.cognibot import CognibotSO101

    robot = CognibotSO101(CognibotSO101Config())
    assert list(robot.action_features) == [
        "shoulder_pan.pos",
        "shoulder_lift.pos",
        "elbow_flex.pos",
        "wrist_flex.pos",
        "wrist_roll.pos",
        "gripper.pos",
    ]
    assert robot.observation_features["front"] == (480, 640, 3)


def test_image_to_numpy_handles_rgb_and_bgr():
    sensor_msgs = pytest.importorskip("sensor_msgs.msg")
    msg = sensor_msgs.Image()
    msg.height, msg.width, msg.step = 2, 3, 9
    msg.encoding = "bgr8"
    msg.data = bytes(range(18))
    rgb = image_to_numpy(msg)
    assert rgb.shape == (2, 3, 3)
    assert rgb[0, 0].tolist() == [2, 1, 0]
    msg.encoding = "rgb8"
    assert image_to_numpy(msg)[0, 0].tolist() == [0, 1, 2]
    assert np.asarray(image_to_numpy(msg)).flags["C_CONTIGUOUS"]


def test_unit_flags_scale_state_and_action_independently():
    import math

    from lerobot_robot_cognibot.cognibot import CognibotSO101

    class FakeBridge:
        published = None

        def joints(self, names):
            return [math.pi / 2] * len(names)

        def image(self, key):
            return np.zeros((480, 640, 3), np.uint8)

        def publish_command(self, names, positions):
            self.published = positions

    robot = CognibotSO101(CognibotSO101Config(action_degrees=True))
    robot._bridge = FakeBridge()
    assert robot.get_observation()["shoulder_pan.pos"] == pytest.approx(math.pi / 2)
    robot.send_action({f"{j}.pos": 90.0 for j in robot.joints})
    assert robot._bridge.published[0] == pytest.approx(math.pi / 2)


def test_gripper_units_follow_the_arena_dataset():
    import math

    from lerobot_robot_cognibot.cognibot import gripper_from_policy, gripper_to_policy

    cfg = CognibotSO101Config(
        state_degrees=True,
        action_degrees=True,
        gripper_deg_per_unit=0.6169,
        gripper_deg_offset=15.4,
    )
    # the dataset's open (42.85 units) and pinch (1.53 units) positions, in joint degrees
    assert math.isclose(gripper_from_policy(42.85, cfg), 41.83, abs_tol=0.01)
    assert math.isclose(gripper_from_policy(1.53, cfg), 16.34, abs_tol=0.01)
    # and back: our joint at 41.83 deg reads as the dataset's open value
    assert math.isclose(gripper_to_policy(41.83, cfg), 42.85, abs_tol=0.01)
    # radians on the ROS side when the degree flags are off
    cfg_rad = CognibotSO101Config(gripper_deg_per_unit=0.6169, gripper_deg_offset=15.4)
    assert math.isclose(gripper_from_policy(42.85, cfg_rad), math.radians(41.83), abs_tol=1e-3)


def test_gripper_units_are_off_by_default():
    from lerobot_robot_cognibot.cognibot import gripper_from_policy, gripper_to_policy

    cfg = CognibotSO101Config()
    assert gripper_to_policy(0.7, cfg) == 0.7 and gripper_from_policy(0.7, cfg) == 0.7
