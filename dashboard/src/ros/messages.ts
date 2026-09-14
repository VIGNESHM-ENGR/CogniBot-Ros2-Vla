import type { RosDuration } from "../lib/duration";

export interface Header {
  stamp: { sec: number; nanosec: number };
  frame_id: string;
}

export interface JointState {
  header: Header;
  name: string[];
  position: number[];
  velocity: number[];
}

export interface GpuStatus {
  header: Header;
  name: string;
  memory_total_mib: number;
  memory_used_mib: number;
  utilization_pct: number;
  temperature_c: number;
  process_names: string[];
  process_memory_mib: number[];
}

export interface StringMsg {
  data: string;
}

export interface Clock {
  clock: { sec: number; nanosec: number };
}

export interface TrajectoryPoint {
  positions: number[];
  time_from_start: RosDuration;
}

export interface FollowJointTrajectoryGoal {
  trajectory: { joint_names: string[]; points: TrajectoryPoint[] };
}

export interface FollowJointTrajectoryFeedback {
  joint_names: string[];
  desired: TrajectoryPoint;
}

export interface ControllerState {
  name: string;
  state: string;
  type: string;
}

export interface FreeJointStateArray {
  header: Header;
  free_joints: {
    name: string;
    pose: {
      pose: {
        position: { x: number; y: number; z: number };
        orientation: { x: number; y: number; z: number; w: number };
      };
    };
  }[];
}

export interface ExecuteSkillGoal {
  instruction: string;
  checkpoint: string;
  max_duration_s: number;
}

export interface ExecuteSkillFeedback {
  elapsed_s: number;
  rate_hz: number;
  queue_size: number;
  latency_ms: number;
}

export interface ExecuteSkillResult {
  success: boolean;
  message: string;
  actions_executed: number;
  mean_rate_hz: number;
}

export interface AgentEventMsg {
  header: Header;
  task_id: string;
  step: number;
  /** 0 thought, 1 tool call, 2 tool result, 3 info, 4 error, 5 done */
  type: number;
  tool_name: string;
  content: string;
  duration_s: number;
}

export interface ObjectDetectionMsg {
  header: Header;
  label: string;
  confidence: number;
  bbox_xyxy: number[];
  position: { header: Header; point: { x: number; y: number; z: number } };
  has_position: boolean;
}

export interface RunAgentTaskGoal {
  query: string;
}

export interface RunAgentTaskFeedback {
  event: AgentEventMsg;
}

export interface RunAgentTaskResult {
  success: boolean;
  summary: string;
}

export interface StageFeedback {
  stage: string;
  progress: number;
}

interface Vector3 {
  x: number;
  y: number;
  z: number;
}

export interface SetFreeJointStateRequest {
  free_joints: {
    name: string;
    pose: {
      header: { frame_id: string };
      pose: { position: Vector3; orientation: { x: number; y: number; z: number; w: number } };
    };
    twist: { header: { frame_id: string }; twist: { linear: Vector3; angular: Vector3 } };
  }[];
}

export interface ResultMessage {
  success: boolean;
  message: string;
}

export interface ControlModeMsg {
  stamp: { sec: number; nanosec: number };
  mode: number;
  requester: string;
  reason: string;
}

export interface SetControlModeResponse {
  success: boolean;
  message: string;
  active_mode: number;
}
