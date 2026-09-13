# ROS 2 Interfaces: CogniBot-ROS2-VLA

Related: [ARCHITECTURE.md](ARCHITECTURE.md) · [NETWORKING.md](NETWORKING.md)

This is the interface contract between packages, and the source of truth for anyone implementing a node. Change it here first, then in `cognibot_interfaces`, in the same commit.

Conventions:
- Project topics live under `/cognibot/…`. Standard controller and sensor topics keep their upstream names.
- Units are SI (m, rad, s). Frames follow REP-103/105. Camera points are in `*_optical_frame`.
- Standard message types are preferred; custom ones exist only where no standard type fits.

---

## 1. Topics

### 1.1 Simulation and sensors (owner: `sim` / upstream)

| Topic | Type | Publisher | Subscribers |
|---|---|---|---|
| `/clock` | `rosgraph_msgs/Clock` | mujoco_ros2_control | all (`use_sim_time: true`) |
| `/joint_states` | `sensor_msgs/JointState` | `joint_state_broadcaster` | robot_state_publisher, motion, teleop, vla-client, dashboard |
| `/tf`, `/tf_static` | `tf2_msgs/TFMessage` | robot_state_publisher, static publishers | all |
| `/robot_description` | `std_msgs/String` (transient local) | robot_state_publisher | move_group, dashboard |
| `/camera/front/color/image_raw` | `sensor_msgs/Image` | mujoco_ros2_control camera plugin | vlm-agent, vla-client, bridge |
| `/camera/front/color/camera_info` | `sensor_msgs/CameraInfo` | camera plugin | vlm-agent |
| `/camera/front/depth/image_raw` | `sensor_msgs/Image` (32FC1, m) | camera plugin | vlm-agent |
| `/camera/wrist/color/image_raw` | `sensor_msgs/Image` | camera plugin | vla-client, bridge |

> The exact camera topic names come from the `mujoco_ros2_control` camera configuration. P1-T05 verifies them and updates this table if the plugin forces a different layout.

### 1.2 Control (owner: `motion`)

| Topic | Type | Publisher | Subscribers |
|---|---|---|---|
| `/joint_trajectory_controller/joint_trajectory` | `trajectory_msgs/JointTrajectory` | (debug only) | `joint_trajectory_controller` |
| `/cognibot/joint_command` | `sensor_msgs/JointState` (name + position) | `mink_teleop`, LeRobot `robot_client` (via plugin), `twin_mirror` | `safety_filter` |
| `/arm_position_controller/commands` | `std_msgs/Float64MultiArray` | `safety_filter` **only** | `arm_position_controller` |
| `/cognibot/mode` | `cognibot_interfaces/ControlMode` (transient local) | `mode_manager` | safety_filter, teleop, skill_executor, dashboard |
| `/cognibot/safety/status` | `diagnostic_msgs/DiagnosticArray` | `safety_filter` | dashboard |
| `/cognibot/viz/collision_spheres` | `visualization_msgs/MarkerArray` | `safety_filter` | RViz, dashboard |
| `/cognibot/viz/workspace` | `visualization_msgs/MarkerArray` (transient local) | `reach_query` | RViz, dashboard |

### 1.3 Teleop (owner: `cognibot_teleop`)

| Topic | Type | Publisher | Subscribers |
|---|---|---|---|
| `/cognibot/teleop/cmd` | `cognibot_interfaces/TeleopCommand` | dashboard (rosbridge) | `mink_teleop` |
| `/cognibot/teleop/ee_target` | `geometry_msgs/PoseStamped` | `mink_teleop` | dashboard, RViz |

### 1.4 AI (owners: `cognibot_vlm`, `cognibot_vla`)

| Topic | Type | Publisher | Subscribers |
|---|---|---|---|
| `/cognibot/agent/events` | `cognibot_interfaces/AgentEvent` | `vlm_agent_node` | dashboard |
| `/cognibot/agent/detections` | `cognibot_interfaces/ObjectDetection` | `vlm_agent_node` | dashboard, RViz (overlay) |
| `/cognibot/vla/status` | `diagnostic_msgs/DiagnosticArray` | `skill_executor_node` | dashboard |
| `/cognibot/gpu` | `cognibot_interfaces/GpuStatus` | `gpu_monitor` | dashboard |

## 2. Services

| Service | Type | Server | Clients |
|---|---|---|---|
| `/cognibot/set_mode` | `cognibot_interfaces/srv/SetControlMode` | `mode_manager` | dashboard, pick_place_server, skill_executor, twin |
| `/cognibot/check_reachability` | `cognibot_interfaces/srv/CheckReachability` | `reach_query` | vlm-agent, dashboard |
| `/cognibot/vlm/get_object_coordinates` | `cognibot_interfaces/srv/GetObjectCoordinates` | `vlm_agent_node` | dashboard (debug), eval scripts |
| `/controller_manager/switch_controller` | `controller_manager_msgs/srv/SwitchController` | controller_manager | `mode_manager` only |

## 3. Actions

| Action | Type | Server | Clients |
|---|---|---|---|
| `/cognibot/fetch_object` | `cognibot_interfaces/action/FetchObject` | `pick_place_server` | vlm-agent, dashboard |
| `/cognibot/place_object` | `cognibot_interfaces/action/PlaceObject` | `pick_place_server` | vlm-agent, dashboard |
| `/cognibot/move_to_named_pose` | `cognibot_interfaces/action/MoveToNamedPose` | `pick_place_server` | vlm-agent, dashboard |
| `/cognibot/vla/execute_skill` | `cognibot_interfaces/action/ExecuteSkill` | `skill_executor_node` | vlm-agent, dashboard |
| `/cognibot/agent/run_task` | `cognibot_interfaces/action/RunAgentTask` | `vlm_agent_node` | dashboard |
| `/joint_trajectory_controller/follow_joint_trajectory` | `control_msgs/action/FollowJointTrajectory` | JTC | move_group |
| `/gripper_controller/gripper_cmd` | `control_msgs/action/ParallelGripperCommand` | gripper controller | move_group, pick_place_server |

> **rosbridge and actions:** recent rosbridge_suite releases proxy ROS 2 actions (`send_action_goal` / `cancel_action_goal` ops, supported by roslibjs `Action`). P3-T02 verifies this against the Jazzy binary. If it fails, the dashboard falls back to `/cognibot/agent/events` and `/cognibot/vla/status` for progress, plus a small service shim. The result is recorded here.

## 4. Custom interface definitions (`cognibot_interfaces`)

### msg/ControlMode.msg
```
uint8 IDLE=0
uint8 TELEOP=1
uint8 MOTION=2
uint8 VLA=3
uint8 TWIN=4

builtin_interfaces/Time stamp
uint8 mode
string requester        # node that requested the current mode
string reason
```

### msg/TeleopCommand.msg
```
uint8 GRIPPER_NONE=0
uint8 GRIPPER_TOGGLE=1
uint8 GRIPPER_OPEN=2
uint8 GRIPPER_CLOSE=3

std_msgs/Header header          # frame_id: robot base frame
geometry_msgs/Vector3 linear    # normalized [-1, 1] per axis; scaled by node param max_linear_speed (m/s)
float64 wrist_roll              # normalized [-1, 1]; scaled by max_angular_speed (rad/s)
uint8 gripper                   # GRIPPER_* command (edge-triggered)
```

### msg/AgentEvent.msg
```
uint8 THOUGHT=0
uint8 TOOL_CALL=1
uint8 TOOL_RESULT=2
uint8 INFO=3
uint8 ERROR=4
uint8 DONE=5

std_msgs/Header header
string task_id
uint32 step
uint8 type
string tool_name        # set for TOOL_CALL / TOOL_RESULT
string content          # free text or JSON (tool args / tool result)
float32 duration_s      # model or tool latency for this step
```

### msg/ObjectDetection.msg
```
std_msgs/Header header                  # image header (camera optical frame, stamp)
string label
float32 confidence                      # 0..1, or -1 if the model gives none
int32[4] bbox_xyxy                      # pixels in the source image
geometry_msgs/PointStamped position     # in robot base frame when has_position
bool has_position
```

### msg/GpuStatus.msg
```
std_msgs/Header header
string name
uint32 memory_total_mib
uint32 memory_used_mib
float32 utilization_pct
float32 temperature_c
string[] process_names
uint32[] process_memory_mib
```

### srv/SetControlMode.srv
```
uint8 mode              # ControlMode constant
string requester
string reason
---
bool success
string message
uint8 active_mode
```

### srv/CheckReachability.srv
```
geometry_msgs/PointStamped target
---
bool reachable
float32 score           # 0..1 REACH score (manipulability-weighted); 0 if unreachable
string source           # "reach_study" | "workspace_sphere"
string message
```

### srv/GetObjectCoordinates.srv
```
string label            # natural language, e.g. "red cube"
string camera           # registry camera key; empty = "front"
---
bool success
cognibot_interfaces/ObjectDetection detection
string message
```

### action/FetchObject.action
```
geometry_msgs/PointStamped target       # object center
float32 approach_height_m               # 0 = use config default
---
bool success
string message
---
string stage                            # plan_approach | approach | grasp | lift
float32 progress                        # 0..1
```

### action/PlaceObject.action
```
geometry_msgs/PointStamped target       # placement point (surface)
float32 release_height_m                # 0 = use config default
---
bool success
string message
---
string stage                            # plan_approach | approach | release | retreat
float32 progress
```

### action/MoveToNamedPose.action
```
string pose_name                        # SRDF group state, e.g. "home"
---
bool success
string message
---
float32 progress
```

### action/ExecuteSkill.action
```
string instruction                      # language task passed to the VLA
string checkpoint                       # HF repo id / path; empty = registry default
float32 max_duration_s
---
bool success
string message
uint32 actions_executed
float32 mean_rate_hz
---
float32 elapsed_s
float32 rate_hz
uint32 queue_size
float32 latency_ms
```

### action/RunAgentTask.action
```
string query
---
bool success
string summary
---
cognibot_interfaces/AgentEvent event
```

## 5. Parameters shared by convention

| Parameter | Nodes | Meaning |
|---|---|---|
| `robot` | all project nodes | Registry key (`so101`, `panda`) |
| `use_sim_time` | all | `true` in sim profiles |
| `registry_path` | all | Override path to `robot.yaml` (defaults to the installed `cognibot_sim` share) |
