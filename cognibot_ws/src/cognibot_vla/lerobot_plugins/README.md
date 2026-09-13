# LeRobot plugins

These are pip-installable packages discovered by LeRobot's third-party plugin mechanism (packages prefixed `lerobot_robot_*` / `lerobot_camera_*`). They are **not** colcon packages (see `COLCON_IGNORE`) and get installed into the `vla` image venv.

| Package | Task | Purpose |
|---|---|---|
| `lerobot_camera_ros2` | P5-T03 | LeRobot camera backed by a ROS 2 image topic |
| `lerobot_robot_cognibot` | P5-T04 | CogniBot robot configs on top of `lerobot_robot_ros` |
