"""Start move_group (and optionally RViz with the MotionPlanning panel) against the simulation."""

from pathlib import Path

from cognibot_motion.moveit_config import build_moveit_config
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def launch_setup(context, *args, **kwargs):
    robot = LaunchConfiguration("robot").perform(context)
    use_sim_time = LaunchConfiguration("use_sim_time").perform(context) == "true"
    moveit_config = build_moveit_config(robot)

    move_group = Node(
        package="moveit_ros_move_group",
        executable="move_group",
        output="screen",
        # MoveIt 2.12 can segfault on a goal arriving mid-execution; come back, not stay dead.
        respawn=True,
        respawn_delay=1.0,
        parameters=[
            moveit_config.to_dict(),
            # The operator console reads named poses from the SRDF topic.
            {"use_sim_time": use_sim_time, "publish_robot_description_semantic": True},
        ],
    )

    rviz_config = Path(moveit_config.package_path) / "config" / "moveit.rviz"
    rviz = Node(
        package="rviz2",
        executable="rviz2",
        output="log",
        arguments=["-d", str(rviz_config)],
        parameters=[
            moveit_config.robot_description,
            moveit_config.robot_description_semantic,
            moveit_config.robot_description_kinematics,
            moveit_config.planning_pipelines,
            moveit_config.joint_limits,
            {"use_sim_time": use_sim_time},
        ],
        condition=IfCondition(LaunchConfiguration("rviz")),
    )
    return [move_group, rviz]


def generate_launch_description():
    return LaunchDescription(
        [
            DeclareLaunchArgument("robot", default_value="so101", description="Robot identifier"),
            DeclareLaunchArgument(
                "use_sim_time", default_value="true", description="Use simulation clock"
            ),
            DeclareLaunchArgument(
                "rviz",
                default_value="false",
                description="Open RViz with the MotionPlanning panel (drag goal, plan, execute)",
            ),
            OpaqueFunction(function=launch_setup),
        ]
    )
