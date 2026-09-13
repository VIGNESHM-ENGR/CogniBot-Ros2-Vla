from dataclasses import dataclass, field

from lerobot.robots import RobotConfig


@dataclass
class CognibotConfig(RobotConfig):
    """A simulated (or twinned) CogniBot arm reached over ROS 2 topics.

    Observations: joint positions from `joint_states_topic` (radians) and RGB images from ROS
    image topics. Actions: joint positions published as `sensor_msgs/JointState` on
    `command_topic`, which only the safety filter forwards to the controller.
    """

    arm_joints: list[str] = field(default_factory=list)
    gripper_joint: str = "gripper"
    # policy camera key -> ROS image topic (rgb8). Keys must match the checkpoint's
    # observation.images.<key> features. (`cameras` is reserved by RobotConfig for LeRobot
    # camera drivers.)
    camera_topics: dict[str, str] = field(default_factory=dict)
    image_height: int = 480
    image_width: int = 640
    joint_states_topic: str = "/joint_states"
    command_topic: str = "/cognibot/joint_command"
    # Units the checkpoint was trained with. ROS joints are radians; LeRobot real-arm datasets
    # use degrees (use_degrees) and some MuJoCo datasets mix them, e.g.
    # bendca61/vla-mujoco-so101-cube_on_tray-leader-v1: state in radians, action in degrees.
    state_degrees: bool = False
    action_degrees: bool = False
    # Ask mode_manager for VLA on connect and IDLE on disconnect.
    request_mode: bool = True
    set_mode_service: str = "/cognibot/set_mode"
    node_name: str = "lerobot_robot_cognibot"
    connect_timeout_s: float = 10.0


@RobotConfig.register_subclass("cognibot_so101")
@dataclass
class CognibotSO101Config(CognibotConfig):
    arm_joints: list[str] = field(
        default_factory=lambda: [
            "shoulder_pan",
            "shoulder_lift",
            "elbow_flex",
            "wrist_flex",
            "wrist_roll",
        ]
    )
    camera_topics: dict[str, str] = field(
        default_factory=lambda: {
            "front": "/mujoco_camera_plugin/front_rgbd/color",
            "wrist": "/mujoco_camera_plugin/wrist_cam/color",
        }
    )


@RobotConfig.register_subclass("cognibot_panda")
@dataclass
class CognibotPandaConfig(CognibotConfig):
    arm_joints: list[str] = field(default_factory=lambda: [f"panda_joint{i}" for i in range(1, 8)])
    gripper_joint: str = "panda_finger_joint1"
    camera_topics: dict[str, str] = field(
        default_factory=lambda: {
            "front": "/mujoco_camera_plugin/front_rgbd/color",
            "wrist": "/mujoco_camera_plugin/wrist_cam/color",
        }
    )
