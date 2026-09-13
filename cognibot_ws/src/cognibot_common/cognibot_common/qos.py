"""QoS presets shared by CogniBot nodes (AGENTS.md §5)."""

from rclpy.qos import (
    DurabilityPolicy,
    HistoryPolicy,
    QoSProfile,
    ReliabilityPolicy,
    qos_profile_sensor_data,
)

# Cameras and joint states: best effort, latest sample wins.
SENSOR_DATA = qos_profile_sensor_data

# Commands: every message matters, but never queue stale ones.
RELIABLE_COMMAND = QoSProfile(
    reliability=ReliabilityPolicy.RELIABLE,
    history=HistoryPolicy.KEEP_LAST,
    depth=1,
)

# Mode and markers: late joiners receive the current value.
TRANSIENT_LOCAL = QoSProfile(
    reliability=ReliabilityPolicy.RELIABLE,
    durability=DurabilityPolicy.TRANSIENT_LOCAL,
    history=HistoryPolicy.KEEP_LAST,
    depth=1,
)
