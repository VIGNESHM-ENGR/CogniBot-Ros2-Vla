import { describe, expect, it } from "vitest";
import { fromSeconds, toSeconds, trajectoryProgress } from "./duration";

describe("duration", () => {
  it("round-trips seconds", () => {
    expect(fromSeconds(2.5)).toEqual({ sec: 2, nanosec: 500000000 });
    expect(toSeconds({ sec: 1, nanosec: 250000000 })).toBe(1.25);
  });
  it("clamps trajectory progress", () => {
    expect(trajectoryProgress(1, 2)).toBe(0.5);
    expect(trajectoryProgress(3, 2)).toBe(1);
    expect(trajectoryProgress(1, 0)).toBe(1);
  });
});
