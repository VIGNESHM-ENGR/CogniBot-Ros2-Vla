import { describe, expect, it } from "vitest";
import { holdGoal, jointGoal, nudgeInsideLimits, pointGoal } from "./goals";

describe("MoveGroup goals", () => {
  it("builds joint constraints from a group state", () => {
    const goal = jointGoal("manipulator", { shoulder_pan: 0.5 });
    expect(goal.request.group_name).toBe("manipulator");
    expect(goal.request.goal_constraints[0]?.joint_constraints[0]).toMatchObject({
      joint_name: "shoulder_pan",
      position: 0.5,
      tolerance_above: 0.01,
    });
    expect(goal.planning_options.plan_only).toBe(false);
  });

  it("builds a sphere position constraint on the tip link", () => {
    const goal = pointGoal("manipulator", "gripper_frame_link", "base_link", {
      x: 0.3,
      y: 0,
      z: 0.1,
    });
    const constraint = goal.request.goal_constraints[0]?.position_constraints[0];
    expect(constraint?.link_name).toBe("gripper_frame_link");
    expect(constraint?.header.frame_id).toBe("base_link");
    expect(constraint?.constraint_region.primitives[0]).toEqual({ type: 2, dimensions: [0.005] });
    expect(constraint?.constraint_region.primitive_poses[0]?.position).toEqual({
      x: 0.3,
      y: 0,
      z: 0.1,
    });
  });
});

describe("holdGoal", () => {
  it("holds current positions over a short trajectory", () => {
    expect(holdGoal(["a"], [1.5])).toEqual({
      trajectory: {
        joint_names: ["a"],
        points: [{ positions: [1.5], time_from_start: { sec: 0, nanosec: 250000000 } }],
      },
    });
  });
});

describe("nudgeInsideLimits", () => {
  const limits = [
    { name: "a", lower: -1, upper: 1 },
    { name: "b", lower: -2, upper: 2 },
  ];
  it("returns null when every joint is inside its limits", () => {
    expect(nudgeInsideLimits(limits, ["a", "b"], [0.5, -1.5])).toBeNull();
  });
  it("clamps joints on or past a limit and keeps the others", () => {
    expect(nudgeInsideLimits(limits, ["b", "a"], [-2.0001, 0.3])).toEqual({
      names: ["a", "b"],
      positions: [0.3, -1.99],
    });
  });
});
