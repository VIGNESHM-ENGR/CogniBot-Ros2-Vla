#!/usr/bin/env python3
"""Launch simulation from cognibot_bringup."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    robot_arg = DeclareLaunchArgument(
        "robot",
        default_value="so101",
        description="Robot identifier (so101 or panda)",
    )
    headless_arg = DeclareLaunchArgument(
        "headless",
        default_value="true",
        description="Run simulation headless without a graphical window",
    )
    use_sim_time_arg = DeclareLaunchArgument(
        "use_sim_time",
        default_value="true",
        description="Use simulation clock",
    )
    robot_color_arg = DeclareLaunchArgument(
        "robot_color",
        default_value="red",
        description="Robot shell color: red, or stock (as sim policies were trained)",
    )

    sim_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution(
                [
                    FindPackageShare("cognibot_sim"),
                    "launch",
                    "sim.launch.py",
                ]
            )
        ),
        launch_arguments={
            "robot": LaunchConfiguration("robot"),
            "headless": LaunchConfiguration("headless"),
            "use_sim_time": LaunchConfiguration("use_sim_time"),
            "robot_color": LaunchConfiguration("robot_color"),
        }.items(),
    )

    return LaunchDescription(
        [
            robot_arg,
            headless_arg,
            use_sim_time_arg,
            robot_color_arg,
            sim_launch,
        ]
    )
