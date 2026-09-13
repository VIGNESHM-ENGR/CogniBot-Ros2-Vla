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

export interface StageFeedback {
  stage: string;
  progress: number;
}

export interface ResultMessage {
  success: boolean;
  message: string;
}
