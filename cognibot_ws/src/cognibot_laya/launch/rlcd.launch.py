"""Launch the RLCD decision node with its parameter file."""

from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    share = Path(get_package_share_directory("cognibot_laya"))
    return LaunchDescription(
        [
            DeclareLaunchArgument("robot", default_value="so101"),
            DeclareLaunchArgument("use_sim_time", default_value="true"),
            DeclareLaunchArgument("registry_dir", default_value=""),
            DeclareLaunchArgument("device", default_value="cuda"),
            Node(
                package="cognibot_laya",
                executable="laya_decision",
                name="laya_decision",
                output="screen",
                parameters=[
                    str(share / "config" / "rlcd.yaml"),
                    {
                        "robot": LaunchConfiguration("robot"),
                        "use_sim_time": LaunchConfiguration("use_sim_time"),
                        "registry_dir": LaunchConfiguration("registry_dir"),
                        "device": LaunchConfiguration("device"),
                    },
                ],
            ),
        ]
    )
