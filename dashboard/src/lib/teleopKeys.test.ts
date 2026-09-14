import { describe, expect, it } from "vitest";
import { commandFor, EMPTY_JOG, GRIPPER_TOGGLE, jogReducer } from "./teleopKeys";

describe("jogReducer", () => {
  it("tracks held keys and ignores repeats", () => {
    let s = jogReducer(EMPTY_JOG, { type: "down", jog: "x+" });
    const again = jogReducer(s, { type: "down", jog: "x+" });
    expect(again).toBe(s);
    s = jogReducer(s, { type: "down", jog: "z-" });
    expect([...s.held]).toEqual(["x+", "z-"]);
    s = jogReducer(s, { type: "up", jog: "x+" });
    expect([...s.held]).toEqual(["z-"]);
  });
  it("edge-triggers the gripper and clears it once published", () => {
    let s = jogReducer(EMPTY_JOG, { type: "down", jog: "grip" });
    expect(commandFor(s, "base_link")?.gripper).toBe(GRIPPER_TOGGLE);
    s = jogReducer(s, { type: "published" });
    expect(commandFor(s, "base_link")).toBeNull();
  });
  it("release-all drops everything (window blur)", () => {
    const s = jogReducer(jogReducer(EMPTY_JOG, { type: "down", jog: "y-" }), {
      type: "release-all",
    });
    expect(s).toBe(EMPTY_JOG);
  });
});

describe("commandFor", () => {
  it("combines opposing keys to zero and maps axes", () => {
    let s = jogReducer(EMPTY_JOG, { type: "down", jog: "x+" });
    s = jogReducer(s, { type: "down", jog: "x-" });
    s = jogReducer(s, { type: "down", jog: "y+" });
    expect(commandFor(s, "base_link")?.linear).toEqual({ x: 0, y: 1, z: 0 });
  });
  it("maps pan and roll keys to the joint fields", () => {
    let s = jogReducer(EMPTY_JOG, { type: "down", jog: "pan-" });
    s = jogReducer(s, { type: "down", jog: "roll+" });
    const c = commandFor(s, "base_link");
    expect(c?.shoulder_pan).toBe(-1);
    expect(c?.wrist_roll).toBe(1);
    expect(c?.linear).toEqual({ x: 0, y: 0, z: 0 });
  });
});
