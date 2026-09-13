"""Browser bridge: rosbridge WebSocket (:9090) and web_video_server MJPEG (:8080), loopback only.

rosbridge has no authentication, so both servers bind to 127.0.0.1 (docs/NETWORKING.md).
"""

from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import AnyLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    address = LaunchConfiguration("address")
    rosbridge_launch = (
        Path(get_package_share_directory("rosbridge_server"))
        / "launch"
        / "rosbridge_websocket_launch.xml"
    )
    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "address", default_value="127.0.0.1", description="Bind address for both servers"
            ),
            DeclareLaunchArgument(
                "rosbridge_port", default_value="9090", description="rosbridge WebSocket port"
            ),
            DeclareLaunchArgument(
                "video_port", default_value="8080", description="web_video_server HTTP port"
            ),
            IncludeLaunchDescription(
                AnyLaunchDescriptionSource(str(rosbridge_launch)),
                launch_arguments={
                    "address": address,
                    "port": LaunchConfiguration("rosbridge_port"),
                }.items(),
            ),
            Node(
                package="web_video_server",
                executable="web_video_server",
                name="web_video_server",
                output="screen",
                parameters=[
                    {"address": address, "port": LaunchConfiguration("video_port")},
                ],
            ),
        ]
    )
