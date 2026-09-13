/** Endpoints and topic names. Everything binds to loopback (docs/NETWORKING.md). */
export const ROSBRIDGE_URL = import.meta.env.VITE_ROSBRIDGE_URL ?? "ws://127.0.0.1:9090";
export const VIDEO_URL = import.meta.env.VITE_VIDEO_URL ?? "http://127.0.0.1:8080";

export const TOPICS = {
  jointStates: "/joint_states",
  jointCommand: "/cognibot/joint_command",
  robotDescription: "/robot_description",
  robotDescriptionSemantic: "/robot_description_semantic",
  clock: "/clock",
  gpu: "/cognibot/gpu",
  teleop: "/cognibot/teleop/cmd",
  teleopTarget: "/cognibot/teleop/ee_target",
  mode: "/cognibot/mode",
  frontCamera: "/mujoco_camera_plugin/front_rgbd/color",
  objectPoses: "/object_poses/free_joint_states",
  wristCamera: "/mujoco_camera_plugin/wrist_cam/color",
} as const;

export const SERVICES = {
  setMode: "/cognibot/set_mode",
  listControllers: "/controller_manager/list_controllers",
  resetObjects: "/cognibot/sim/reset_objects",
  setFreeJointState: "/mujoco_ros2_control_node/set_free_joint_state",
} as const;

export const ACTIONS = {
  trajectory: "/joint_trajectory_controller/follow_joint_trajectory",
  gripper: "/gripper_controller/gripper_cmd",
  moveGroup: "/move_action",
  fetch: "/cognibot/fetch_object",
  place: "/cognibot/place_object",
} as const;

/** MoveIt planning group, tip link and base frame of the upstream SO-101 config. */
export const MOVEIT = {
  arm: "manipulator",
  gripper: "gripper",
  tip: "gripper_frame_link",
  base: "base_link",
};

export const mjpegUrl = (topic: string, quality = 80) =>
  // web_video_server does not decode %2F, so topic names (already URL-safe) go in raw.
  `${VIDEO_URL}/stream?topic=${topic}&type=mjpeg&quality=${quality}`;

/** Scene mirror assets copied from cognibot_sim by scripts/sync-scene.mjs. */
export const SCENE_URL = `${import.meta.env.BASE_URL}sim/so101`;

/** Cubes in the scene, by colour; the MuJoCo body is `<colour>_cube`. Reset parks them again. */
export const CUBES = ["green", "red", "blue", "yellow", "white"] as const;
export type CubeColor = (typeof CUBES)[number];
export const cubeBody = (color: CubeColor) => `${color}_cube`;
/** Half-size of a cube: spawning rests it on the floor. */
export const CUBE_HALF = 0.0125;
/** Where the IK pick-and-place demo drops the cube (static MuJoCo body). */
export const DEMO = { target: "target" };
