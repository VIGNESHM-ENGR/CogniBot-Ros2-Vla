"""Motion stack for the compose `motion` service: move_group (headless) and pick_place_server."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    return LaunchDescription(
        [
            DeclareLaunchArgument("robot", default_value="so101", description="Robot identifier"),
            DeclareLaunchArgument(
                "use_sim_time", default_value="true", description="Use simulation clock"
            ),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    PathJoinSubstitution(
                        [FindPackageShare("cognibot_motion"), "launch", "move_group.launch.py"]
                    )
                ),
                launch_arguments={
                    "robot": LaunchConfiguration("robot"),
                    "use_sim_time": LaunchConfiguration("use_sim_time"),
                    "rviz": "false",
                }.items(),
            ),
            Node(
                package="cognibot_motion",
                executable="mode_manager",
                name="mode_manager",
                output="screen",
            ),
            Node(
                package="cognibot_motion",
                executable="pick_place_server",
                name="pick_place_server",
                output="screen",
                parameters=[{"robot": LaunchConfiguration("robot")}],
            ),
        ]
    )
