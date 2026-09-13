import { fromSeconds } from "./duration";
import type { JointLimit } from "./robotModel";

const PLANNING = {
  num_planning_attempts: 3,
  allowed_planning_time: 3.0,
  max_velocity_scaling_factor: 0.5,
  max_acceleration_scaling_factor: 0.5,
};

const OPTIONS = { plan_only: false, look_around: false, replan: false };

/** MoveGroup goal to a joint configuration (e.g. an SRDF group state). */
export function jointGoal(group: string, joints: Record<string, number>, tolerance = 0.01) {
  return {
    request: {
      group_name: group,
      ...PLANNING,
      goal_constraints: [
        {
          joint_constraints: Object.entries(joints).map(([joint_name, position]) => ({
            joint_name,
            position,
            tolerance_above: tolerance,
            tolerance_below: tolerance,
            weight: 1.0,
          })),
        },
      ],
    },
    planning_options: OPTIONS,
  };
}

/** MoveGroup goal placing `link` inside a small sphere at a point (position-only, pick_ik). */
export function pointGoal(
  group: string,
  link: string,
  frame: string,
  point: { x: number; y: number; z: number },
  radius = 0.005,
) {
  return {
    request: {
      group_name: group,
      ...PLANNING,
      goal_constraints: [
        {
          position_constraints: [
            {
              header: { frame_id: frame },
              link_name: link,
              target_point_offset: { x: 0, y: 0, z: 0 },
              constraint_region: {
                primitives: [{ type: 2, dimensions: [radius] }],
                primitive_poses: [{ position: point, orientation: { x: 0, y: 0, z: 0, w: 1 } }],
              },
              weight: 1.0,
            },
          ],
        },
      ],
    },
    planning_options: OPTIONS,
  };
}

/** FollowJointTrajectory goal that holds the given joints where they are. */
export function holdGoal(joints: string[], positions: number[], seconds = 0.25) {
  return {
    trajectory: {
      joint_names: joints,
      points: [{ positions, time_from_start: fromSeconds(seconds) }],
    },
  };
}

/**
 * Joints sitting on (or a hair past) a limit, clamped `margin` rad inside it. MoveIt refuses to
 * plan from a start state outside the URDF bounds, and a position controller can settle ~1e-4 rad
 * past a limit it was sent to.
 */
export function nudgeInsideLimits(
  limits: JointLimit[],
  names: string[],
  positions: number[],
  margin = 0.01,
): { names: string[]; positions: number[] } | null {
  const out = { names: [] as string[], positions: [] as number[] };
  let needed = false;
  for (const limit of limits) {
    const i = names.indexOf(limit.name);
    if (i < 0) continue;
    const value = positions[i] ?? 0;
    const clamped = Math.min(limit.upper - margin, Math.max(limit.lower + margin, value));
    if (clamped !== value) needed = true;
    out.names.push(limit.name);
    out.positions.push(clamped);
  }
  return needed ? out : null;
}

/** moveit_msgs/MoveItErrorCodes (Jazzy numbering), phrased for the operator. */
export const MOVEIT_ERRORS: Record<number, string> = {
  1: "success",
  [-1]: "planning failed",
  [-2]: "invalid motion plan",
  [-3]: "plan invalidated by environment change",
  [-4]: "control failed",
  [-6]: "timed out",
  [-7]: "preempted",
  [-10]: "start state in collision",
  [-12]: "goal in collision",
  [-14]: "goal constraints violated",
  [-16]: "invalid goal constraints",
  [-21]: "frame transform failed",
  [-23]: "robot state stale",
  [-26]: "start state invalid (joint outside limits)",
  [-27]: "goal state invalid",
  [-31]: "no IK solution",
};
