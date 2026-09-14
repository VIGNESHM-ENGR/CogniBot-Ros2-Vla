"""Launch the VLM agent node with its parameter file."""

from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    share = Path(get_package_share_directory("cognibot_vlm"))
    return LaunchDescription(
        [
            DeclareLaunchArgument("robot", default_value="so101"),
            DeclareLaunchArgument("use_sim_time", default_value="true"),
            DeclareLaunchArgument("registry_dir", default_value=""),
            Node(
                package="cognibot_vlm",
                executable="vlm_agent",
                name="vlm_agent",
                output="screen",
                parameters=[
                    str(share / "config" / "agent.yaml"),
                    {
                        "robot": LaunchConfiguration("robot"),
                        "use_sim_time": LaunchConfiguration("use_sim_time"),
                        "prompt_dir": str(share / "prompts"),
                        "registry_dir": LaunchConfiguration("registry_dir"),
                    },
                ],
            ),
        ]
    )
