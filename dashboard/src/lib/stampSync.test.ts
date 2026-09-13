import { describe, expect, it } from "vitest";
import { StampBuffer, lerp, nlerpQuat, stampSeconds } from "./stampSync";

const at = (sec: number, nanosec = 0) => ({
  header: { stamp: { sec, nanosec } },
  id: `${sec}.${nanosec}`,
});

describe("StampBuffer", () => {
  it("brackets a stamp between its neighbours", () => {
    const buf = new StampBuffer<ReturnType<typeof at>>();
    [at(10, 0), at(10, 20e6), at(10, 40e6)].forEach((m) => buf.push(m));
    const b = buf.bracket(10.03);
    expect(b?.before.id).toBe("10.20000000");
    expect(b?.after.id).toBe("10.40000000");
    expect(b?.alpha).toBeCloseTo(0.5);
  });
  it("clamps outside the buffered range", () => {
    const buf = new StampBuffer<ReturnType<typeof at>>();
    [at(1), at(2)].forEach((m) => buf.push(m));
    expect(buf.bracket(0)?.after.id).toBe("1.0");
    expect(buf.bracket(5)?.before.id).toBe("2.0");
    expect(buf.latestStamp).toBe(2);
  });
  it("keeps out-of-order arrivals sorted and drops old messages", () => {
    const buf = new StampBuffer<ReturnType<typeof at>>(3);
    [at(1), at(3), at(2), at(4)].forEach((m) => buf.push(m));
    expect(buf.bracket(2.5)?.before.id).toBe("2.0");
    expect(buf.bracket(0)?.before.id).toBe("2.0");
  });
  it("converts stamps to seconds", () => {
    expect(stampSeconds(at(3, 500e6))).toBe(3.5);
  });
});

describe("interpolation", () => {
  it("lerps", () => {
    expect(lerp(1, 3, 0.25)).toBe(1.5);
  });
  it("nlerps quaternions the short way", () => {
    const q = nlerpQuat([1, 0, 0, 0], [-1, 0, 0, 0], 0.5);
    expect(q[0]).toBeCloseTo(1);
    const half = nlerpQuat([1, 0, 0, 0], [0, 0, 0, 1], 0.5);
    expect(half[0]).toBeCloseTo(Math.SQRT1_2);
    expect(half[3]).toBeCloseTo(Math.SQRT1_2);
  });
});
