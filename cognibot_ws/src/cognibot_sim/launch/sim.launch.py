#!/usr/bin/env python3
"""Launch headless MuJoCo simulation with ros2_control."""

from cognibot_common.mjcf_tint import ROBOT_COLORS, tint_scene
from cognibot_common.robot_registry import load_robot
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import Command, LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def launch_setup(context, *args, **kwargs):
    robot_name = LaunchConfiguration("robot").perform(context)
    headless = LaunchConfiguration("headless").perform(context)
    use_sim_time = LaunchConfiguration("use_sim_time").perform(context) == "true"

    robot_cfg = load_robot(robot_name)
    urdf_xacro_path = str(robot_cfg.urdf)
    controllers_yaml_path = str(robot_cfg.controllers)
    scene_xml_path = str(robot_cfg.mjcf.scene)

    robot_color = LaunchConfiguration("robot_color").perform(context)
    if robot_color not in ROBOT_COLORS:
        raise ValueError(f"robot_color must be one of {sorted(ROBOT_COLORS)}, got '{robot_color}'")
    rgba = ROBOT_COLORS[robot_color]
    if rgba is not None:
        scene_xml_path = str(tint_scene(robot_cfg.mjcf.scene, robot_cfg.mjcf.tint_materials, rgba))

    robot_description_content = ParameterValue(
        Command(
            [
                "xacro ",
                urdf_xacro_path,
                " mujoco_model:=",
                scene_xml_path,
                " headless:=",
                "true" if headless in ["true", "True", "1"] else "false",
            ]
        ),
        value_type=str,
    )

    robot_state_publisher_node = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        output="both",
        parameters=[
            {"robot_description": robot_description_content, "use_sim_time": use_sim_time},
        ],
    )

    ros2_control_node = Node(
        package="mujoco_ros2_control",
        executable="ros2_control_node",
        output="both",
        parameters=[
            controllers_yaml_path,
            {"robot_description": robot_description_content, "use_sim_time": use_sim_time},
        ],
    )

    joint_state_broadcaster_spawner = Node(
        package="controller_manager",
        executable="spawner",
        arguments=["joint_state_broadcaster", "--controller-manager", "/controller_manager"],
        output="both",
    )

    joint_trajectory_controller_spawner = Node(
        package="controller_manager",
        executable="spawner",
        arguments=["joint_trajectory_controller", "--controller-manager", "/controller_manager"],
        output="both",
    )

    gripper_controller_spawner = Node(
        package="controller_manager",
        executable="spawner",
        arguments=["gripper_controller", "--controller-manager", "/controller_manager"],
        output="both",
    )

    arm_position_controller_spawner = Node(
        package="controller_manager",
        executable="spawner",
        arguments=[
            "arm_position_controller",
            "--inactive",
            "--controller-manager",
            "/controller_manager",
        ],
        output="both",
    )

    # Static TF for world -> base_frame (robot base at origin)
    tf_world_to_base = Node(
        package="tf2_ros",
        executable="static_transform_publisher",
        arguments=[
            "--x",
            "0.0",
            "--y",
            "0.0",
            "--z",
            "0.0",
            "--qx",
            "0.0",
            "--qy",
            "0.0",
            "--qz",
            "0.0",
            "--qw",
            "1.0",
            "--frame-id",
            "world",
            "--child-frame-id",
            robot_cfg.base_frame,
        ],
        output="both",
    )

    # Static TF for world -> front_rgbd_frame and front_camera_optical_frame
    if robot_name == "panda":
        cam_pos = ["1.2", "0.0", "0.9"]
        cam_quat = ["0.612375", "0.612375", "-0.35355", "-0.35355"]
    else:
        cam_pos = ["0.56", "0.08", "0.36"]
        cam_quat = ["0.651157", "0.651157", "-0.275672", "-0.275672"]

    tf_world_to_front_cam = Node(
        package="tf2_ros",
        executable="static_transform_publisher",
        arguments=[
            "--x",
            cam_pos[0],
            "--y",
            cam_pos[1],
            "--z",
            cam_pos[2],
            "--qx",
            cam_quat[0],
            "--qy",
            cam_quat[1],
            "--qz",
            cam_quat[2],
            "--qw",
            cam_quat[3],
            "--frame-id",
            "world",
            "--child-frame-id",
            "front_rgbd_frame",
        ],
        output="both",
    )

    tf_front_cam_alias = Node(
        package="tf2_ros",
        executable="static_transform_publisher",
        arguments=[
            "--x",
            "0.0",
            "--y",
            "0.0",
            "--z",
            "0.0",
            "--qx",
            "0.0",
            "--qy",
            "0.0",
            "--qz",
            "0.0",
            "--qw",
            "1.0",
            "--frame-id",
            "front_rgbd_frame",
            "--child-frame-id",
            "front_camera_optical_frame",
        ],
        output="both",
    )

    return [
        robot_state_publisher_node,
        ros2_control_node,
        joint_state_broadcaster_spawner,
        joint_trajectory_controller_spawner,
        gripper_controller_spawner,
        arm_position_controller_spawner,
        tf_world_to_base,
        tf_world_to_front_cam,
        tf_front_cam_alias,
    ]


def generate_launch_description():
    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "robot",
                default_value="so101",
                description="Robot identifier (so101 or panda)",
            ),
            DeclareLaunchArgument(
                "headless",
                default_value="true",
                description="Run MuJoCo simulation headless without a graphical window",
            ),
            DeclareLaunchArgument(
                "use_sim_time",
                default_value="true",
                description="Use simulation (MuJoCo) clock",
            ),
            DeclareLaunchArgument(
                "robot_color",
                default_value="red",
                description="Robot shell color: red, or stock (as sim policies were trained)",
            ),
            OpaqueFunction(function=launch_setup),
        ]
    )
