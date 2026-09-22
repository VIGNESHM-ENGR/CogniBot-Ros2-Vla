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
| `/camera/front/color/image_raw` | `sensor_msgs/Image` | mujoco_ros2_control camera plugin (or `/mujoco_camera_plugin/front_rgbd/color`) | vlm-agent, vla-client, bridge |
| `/camera/front/color/camera_info` | `sensor_msgs/CameraInfo` | camera plugin (or `/mujoco_camera_plugin/front_rgbd/camera_info`) | vlm-agent |
| `/camera/front/depth/image_raw` | `sensor_msgs/Image` (32FC1, m) | camera plugin (or `/mujoco_camera_plugin/front_rgbd/depth`) | vlm-agent |
| `/camera/wrist/color/image_raw` | `sensor_msgs/Image` | camera plugin (or `/mujoco_camera_plugin/wrist_cam/color`) | vla-client, bridge |
| `/object_poses/free_joint_states` | `mujoco_ros2_control_msgs/FreeJointStateArray` (world frame, 50 Hz; name fixed by the plugin instance) | mujoco_ros2_control `FreeJointStatePublisherPlugin` | pick_place_server, dashboard, eval scripts |

> In simulation, the `mujoco_ros2_control` camera plugin directly publishes `/mujoco_camera_plugin/{camera_name}/{color,depth,camera_info}`. Static TFs align `world -> front_rgbd_frame` (and alias `front_camera_optical_frame`). The `/camera/...` names are the contract for consumers; no remapping exists yet, so each consuming node (bridge, vlm-agent, vla-client) must remap from the plugin topics when it is added.

### 1.2 Control (owner: `motion`)

| Topic | Type | Publisher | Subscribers |
|---|---|---|---|
| `/joint_trajectory_controller/joint_trajectory` | `trajectory_msgs/JointTrajectory` | (debug only) | `joint_trajectory_controller` |
| `/cognibot/joint_command` | `sensor_msgs/JointState` (name + position, radians) | `mink_teleop`, LeRobot `robot_client` (`lerobot_robot_cognibot`), `twin_mirror` | `safety_filter` |
| `/arm_position_controller/commands` | `std_msgs/Float64MultiArray` (arm joints then gripper, registry order) | `safety_filter` **only** | `arm_position_controller` |
| `/cognibot/mode` | `cognibot_interfaces/ControlMode` (transient local) | `mode_manager` | safety_filter, teleop, skill_executor, dashboard |

> Mode → controllers and allowed transitions are in `cognibot_motion/config/modes.yaml`; the manager waits for the spawners to settle before publishing IDLE and switches only controllers whose state changes (STRICT rejects no-ops).
| `/cognibot/safety/status` | `diagnostic_msgs/DiagnosticArray` | `safety_filter` | dashboard |
| `/cognibot/viz/collision_spheres` | `visualization_msgs/MarkerArray` | `safety_filter` | RViz, dashboard |
| `/cognibot/viz/workspace` | `visualization_msgs/MarkerArray` (transient local) | `reach_query` | RViz, dashboard |

### 1.3 Teleop (owner: `cognibot_teleop`)

| Topic | Type | Publisher | Subscribers |
|---|---|---|---|
| `/cognibot/teleop/cmd` | `cognibot_interfaces/TeleopCommand` | dashboard (rosbridge) | `mink_teleop` |
| `/cognibot/teleop/ee_target` | `geometry_msgs/PoseStamped` | `mink_teleop` | dashboard, RViz |

> `mink_teleop` requests TELEOP on the first command, seeds its IK configuration from `/joint_states` on engage, integrates the target at `max_linear_speed` (0.1 m/s) inside the registry workspace shell and above `table_z_min`, yaws it about the base z axis for `shoulder_pan` and rolls the tool for `wrist_roll` (both at `max_angular_speed`), and streams at 100 Hz. The dashboard publishes `TeleopCommand` at 30 Hz while a jog key is held; the presence of `/cognibot/teleop/ee_target` is how it detects the node.

### 1.4 AI (owners: `cognibot_vlm`, `cognibot_vla`)

| Topic | Type | Publisher | Subscribers |
|---|---|---|---|
| `/cognibot/agent/events` | `cognibot_interfaces/AgentEvent` | `vlm_agent_node` | dashboard |
| `/cognibot/agent/detections` | `cognibot_interfaces/ObjectDetection` | `vlm_agent_node` | dashboard, RViz (overlay) |
| `/cognibot/vla/status` | `diagnostic_msgs/DiagnosticArray` | `skill_executor_node` (planned; the dashboard currently derives stream status from `/cognibot/mode` and `/cognibot/joint_command`) | dashboard |
| `/cognibot/gpu` | `cognibot_interfaces/GpuStatus` | `gpu_monitor` | dashboard |
| `/cognibot/rlcd/decisions` | `cognibot_interfaces/Decision` | `laya_decision` | dashboard (RLCD view) |

> `laya_decision` (ADR-0008) is the RLCD decision layer: it serialises the scene as JSON and asks a
> 421M text model typed questions. **Track A (skills)** decides a skill plus an object and runs the
> existing `FetchObject` / `PlaceObject` / `MoveToNamedPose` / `ExecuteSkill` servers in MOTION.
> **Track B (primitives)** decides one motion primitive per step and publishes `TeleopCommand` on
> `/cognibot/teleop/cmd` at 30 Hz, so `mink_teleop` does the IK and the arm runs in TELEOP: the
> model never emits joint angles. Both publish every answer with its option distribution on
> `/cognibot/rlcd/decisions` and their steps on `/cognibot/agent/events` (task ids start `rlcd-`).
> Object poses come from `/object_poses/free_joint_states` (simulation ground truth; the robot base
> is the world origin), not from the camera — Laya has no vision encoder.

## 2. Services

| Service | Type | Server | Clients |
|---|---|---|---|
| `/cognibot/set_mode` | `cognibot_interfaces/srv/SetControlMode` | `mode_manager` | dashboard, pick_place_server, skill_executor, twin |
| `/cognibot/check_reachability` | `cognibot_interfaces/srv/CheckReachability` | `reach_query` | vlm-agent, dashboard |
| `/cognibot/vlm/get_object_coordinates` | `cognibot_interfaces/srv/GetObjectCoordinates` | `vlm_agent_node` | dashboard (debug), eval scripts |
| `/cognibot/rlcd/decide` | `cognibot_interfaces/srv/Decide` | `laya_decision` | eval scripts, debugging (one state + question set → the raw model payload) |
| `/cognibot/sim/reset_objects` | `std_srvs/srv/Trigger` | `pick_place_server` | dashboard (simulation only: moves free bodies back to their MJCF spawn pose) |
| `/mujoco_ros2_control_node/set_free_joint_state` | `mujoco_ros2_control_msgs/srv/SetFreeJointState` | mujoco_ros2_control (upstream) | dashboard *Spawn cube* (simulation only: teleports a parked `<colour>_cube` body onto the floor) |
| `/controller_manager/switch_controller` | `controller_manager_msgs/srv/SwitchController` | controller_manager | `mode_manager` only |

## 3. Actions

| Action | Type | Server | Clients |
|---|---|---|---|
| `/cognibot/fetch_object` | `cognibot_interfaces/action/FetchObject` | `pick_place_server` | vlm-agent, dashboard |
| `/cognibot/place_object` | `cognibot_interfaces/action/PlaceObject` | `pick_place_server` | vlm-agent, dashboard |
| `/cognibot/move_to_named_pose` | `cognibot_interfaces/action/MoveToNamedPose` | `pick_place_server` | vlm-agent, dashboard |
| `/cognibot/vla/execute_skill` | `cognibot_interfaces/action/ExecuteSkill` | `skill_executor_node` | vlm-agent, dashboard |
| `/cognibot/agent/run_task` | `cognibot_interfaces/action/RunAgentTask` | `vlm_agent_node` | dashboard |
| `/cognibot/rlcd/run_task` | `cognibot_interfaces/action/RunDecisionTask` | `laya_decision` | dashboard (RLCD view) |

> `vlm_agent` (ADR-0007) takes the latest front frame as JPEG, runs Qwen3-VL through llama-swap with the tools in `cognibot_vlm/tools/schemas.py` (`get_object_coordinates(label)`, `check_reachability(x, y, z)`, `fetch_object(label)`, `place_object(label)`, `move_home`, `set_gripper(state)`, `run_vla_skill(instruction)`), publishes every step on `/cognibot/agent/events` and grounded boxes on `/cognibot/agent/detections`, and requests MOTION (via IDLE when needed) before scripted motions. `fetch_object`/`place_object` park the arm at home, ground their label themselves (top-face centroid; centre = top/2 for fetching, `top` as the surface for placing) and act — coordinates never pass through the model, which a 4B model would otherwise reuse after an object has moved. Camera topics are parameters (`config/agent.yaml`) pointing at the simulator's plugin topics; `check_reachability` uses the registry workspace sphere until `reach_query` exists. The llama-swap profile is `model_hybrid` while the arm is in VLA, `model_gpu` otherwise.
| `/joint_trajectory_controller/follow_joint_trajectory` | `control_msgs/action/FollowJointTrajectory` | JTC | move_group |
| `/gripper_controller/gripper_cmd` | `control_msgs/action/ParallelGripperCommand` | gripper controller | move_group, pick_place_server |

> `skill_executor_node` runs one `ExecuteSkill` goal at a time by starting LeRobot's async `robot_client` (`run_robot_client.sh`) as a subprocess with the container's policy configuration; a non-empty `instruction` overrides `TASK` and `checkpoint` overrides `VLA_CHECKPOINT`. The client requests VLA itself and IDLE on disconnect. Feedback carries `elapsed_s` and the observed `/cognibot/joint_command` rate (`queue_size`/`latency_ms` are 0 until the client exposes them). The run ends on cancel, `max_duration_s`, client exit, or when the arm leaves VLA (STOP or the mode key), which SIGINTs the client so it releases the arm.

> **rosbridge and actions (verified P3-T02, `ros-jazzy-rosbridge-server` 2.7.1):** the `send_action_goal` / `action_feedback` / `action_result` / `cancel_action_goal` ops work against `/joint_trajectory_controller/follow_joint_trajectory` (`control_msgs/action/FollowJointTrajectory`): feedback streams during execution (~20 Hz), a completed goal returns `status: 4` (SUCCEEDED), and a cancel sent mid-motion returns `status: 5` (CANCELED) 0.06 s later. The dashboard uses actions directly; no service shim is needed. The spike used the raw protocol from Python; P3-T04 confirms the same ops through the pinned roslibjs `Action` class.
>
> **Camera streams for the browser:** `web_video_server` on `127.0.0.1:8080` serves the simulator topics directly, e.g. `/stream?topic=/mujoco_camera_plugin/front_rgbd/color` (MJPEG) and `/snapshot?topic=…` (JPEG).

> **Pick and place targets (interim, until P2-T09):** `pick_place_server` executes `FetchObject`/`PlaceObject` with scripted top-down IK. `target.header.frame_id` empty, `world` or the robot base frame means `target.point` is a position; any other value names a MuJoCo body (`green_cube` resolves to its live pose from `/object_poses/free_joint_states`, static bodies such as `target` to their model position) and `point` is an offset. The IK keeps the tool vertical when it can and leans it 30°/45° away from the base when vertical is out of reach (stacking heights). Feedback stages follow the action definitions.

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
float64 shoulder_pan            # normalized [-1, 1]; yaws the target about the base z axis at max_angular_speed
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

### msg/Decision.msg
```
std_msgs/Header header
string task_id
uint32 step
string question_id      # skill | object | move | unsafe | out_of_scope | needs_human
string[] options
float32[] probabilities # parallel to options, sums to 1 within the question
string choice
float32 confidence      # calibrated, 0..1
float32 act_probability # act vs escalate head, 0..1
string model            # checkpoint that answered: english | multilingual | typed-decisions
float32 latency_ms
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

### srv/Decide.srv
```
string state_json
string questions_json
string model            # empty = route by script and language
---
bool success
string answers_json     # the model payload: answers, probabilities, confidences, routing
float32 latency_ms
string message
```

### srv/GetObjectCoordinates.srv
```
string label            # natural language, e.g. "green cube"
string camera           # registry camera key; empty = "front"
---
bool success
cognibot_interfaces/ObjectDetection detection
string message
```

### action/RunDecisionTask.action
```
uint8 TRACK_SKILLS=0        # decide which skill and object, execute with the scripted actions
uint8 TRACK_PRIMITIVES=1    # decide one motion primitive per step, jog through the teleop IK

string task
uint8 track
float32 max_duration_s      # 0 = node default
float32 min_confidence      # 0 = node default; below it a decision escalates instead of moving
---
bool success
string summary
uint32 decisions
---
uint32 step
cognibot_interfaces/Decision decision
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
