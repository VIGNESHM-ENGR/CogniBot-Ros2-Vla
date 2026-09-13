// @vitest-environment happy-dom
import { describe, expect, it } from "vitest";
import { limitState, parseSrdfGroupStates, parseUrdf, rangeFraction } from "./robotModel";

const URDF = `<robot name="so101_arm">
  <joint name="base" type="fixed"/>
  <joint name="shoulder_pan" type="revolute"><limit lower="-1.9" upper="1.9"/></joint>
  <joint name="gripper" type="revolute"><limit lower="-0.17" upper="1.74"/></joint>
  <joint name="finger2" type="prismatic"><mimic joint="gripper"/><limit lower="0" upper="0.04"/></joint>
</robot>`;

const SRDF = `<robot name="so101_arm">
  <group_state name="rest" group="manipulator">
    <joint name="shoulder_pan" value="0"/><joint name="elbow_flex" value="1.57"/>
  </group_state>
  <group_state name="open" group="gripper"><joint name="gripper" value="1.5"/></group_state>
</robot>`;

describe("parseUrdf", () => {
  it("keeps movable non-mimic joints with limits", () => {
    const urdf = parseUrdf(URDF);
    expect(urdf?.robotName).toBe("so101_arm");
    expect(urdf?.joints.map((j) => j.name)).toEqual(["shoulder_pan", "gripper"]);
    expect(urdf?.joints[1]).toEqual({ name: "gripper", lower: -0.17, upper: 1.74 });
  });

  it("returns null for malformed XML", () => {
    expect(parseUrdf("<robot")).toBeNull();
  });
});

describe("parseSrdfGroupStates", () => {
  it("reads group states with joint values", () => {
    const states = parseSrdfGroupStates(SRDF);
    expect(states).toHaveLength(2);
    expect(states[0]).toEqual({
      name: "rest",
      group: "manipulator",
      joints: { shoulder_pan: 0, elbow_flex: 1.57 },
    });
  });
});

describe("limits", () => {
  const limit = { name: "j", lower: -1, upper: 1 };
  it("classifies distance to the nearest limit", () => {
    expect(limitState(0, limit)).toBe("nominal");
    expect(limitState(0.9, limit)).toBe("near");
    expect(limitState(-0.995, limit)).toBe("at");
  });
  it("clamps the range fraction", () => {
    expect(rangeFraction(0, limit)).toBe(0.5);
    expect(rangeFraction(5, limit)).toBe(1);
  });
});
