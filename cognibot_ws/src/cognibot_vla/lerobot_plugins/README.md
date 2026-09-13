# LeRobot plugins

These are pip-installable packages discovered by LeRobot's third-party plugin mechanism (packages prefixed `lerobot_robot_*` / `lerobot_camera_*`). They are **not** colcon packages (see `COLCON_IGNORE`) and get installed into the `vla` image venv.

| Package | Task | Purpose |
|---|---|---|
| `lerobot_robot_cognibot` | P5-T03/T04 | `cognibot_so101` / `cognibot_panda` LeRobot robots over ROS 2: joint states and image topics in, `JointState` commands to `/cognibot/joint_command` (safety filter) out, VLA/IDLE mode requests; camera keys and degree/radian flags per checkpoint |
