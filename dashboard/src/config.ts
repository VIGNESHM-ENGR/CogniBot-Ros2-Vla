/** Endpoints and topic names. Everything binds to loopback (docs/NETWORKING.md). */
export const ROSBRIDGE_URL = import.meta.env.VITE_ROSBRIDGE_URL ?? "ws://127.0.0.1:9090";
export const VIDEO_URL = import.meta.env.VITE_VIDEO_URL ?? "http://127.0.0.1:8080";

export const TOPICS = {
  jointStates: "/joint_states",
  robotDescription: "/robot_description",
  robotDescriptionSemantic: "/robot_description_semantic",
  clock: "/clock",
  gpu: "/cognibot/gpu",
  teleop: "/cognibot/teleop/cmd",
  frontCamera: "/mujoco_camera_plugin/front_rgbd/color",
  wristCamera: "/mujoco_camera_plugin/wrist_cam/color",
} as const;

export const SERVICES = {
  setMode: "/cognibot/set_mode",
  listControllers: "/controller_manager/list_controllers",
} as const;

export const ACTIONS = {
  trajectory: "/joint_trajectory_controller/follow_joint_trajectory",
  gripper: "/gripper_controller/gripper_cmd",
  moveGroup: "/move_action",
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
