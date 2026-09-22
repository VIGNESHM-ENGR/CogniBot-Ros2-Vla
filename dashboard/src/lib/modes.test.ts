import { describe, expect, it } from "vitest";
import { commandForKey, detentAngle, nextSource } from "./modes";

describe("commandForKey", () => {
  it("stops from anywhere, including text fields", () => {
    expect(commandForKey("Escape", true)).toEqual({ kind: "stop" });
    expect(commandForKey("Escape", false)).toEqual({ kind: "stop" });
  });
  it("ignores console keys while typing", () => {
    expect(commandForKey("KeyW", true)).toBeNull();
    expect(commandForKey("Digit2", true)).toBeNull();
  });
  it("maps digits to mode detents and F-keys to views", () => {
    expect(commandForKey("Digit2", false)).toEqual({ kind: "mode", mode: "TELEOP" });
    expect(commandForKey("F5", false)).toEqual({ kind: "view", view: "rlcd" });
    expect(commandForKey("F6", false)).toEqual({ kind: "view", view: "system" });
    expect(commandForKey("Digit9", false)).toBeNull();
  });
  it("maps jog keys", () => {
    expect(commandForKey("ArrowUp", false)).toEqual({ kind: "jog", jog: "z+" });
    expect(commandForKey("KeyG", false)).toEqual({ kind: "jog", jog: "grip" });
    expect(commandForKey("KeyQ", false)).toEqual({ kind: "jog", jog: "pan+" });
    expect(commandForKey("ArrowRight", false)).toEqual({ kind: "jog", jog: "roll-" });
  });
});

describe("detentAngle", () => {
  it("sweeps five detents from -60 to +60 degrees", () => {
    expect(detentAngle("IDLE")).toBe(-60);
    expect(detentAngle("MOTION")).toBe(0);
    expect(detentAngle("TWIN")).toBe(60);
  });
});

describe("viewport sources", () => {
  it("cycles free look, front and wrist with V", () => {
    expect(commandForKey("KeyV", false)).toEqual({ kind: "cycleSource" });
    expect(nextSource("free")).toBe("front");
    expect(nextSource("wrist")).toBe("free");
  });
});
