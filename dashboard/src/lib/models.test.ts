import { describe, expect, it } from "vitest";
import type { ModelStatusMsg } from "../ros/messages";
import { mergeStatus, stateOf, swapNotice } from "./models";

const status = (name: string, state: number, model = ""): ModelStatusMsg => ({
  header: { frame_id: "", stamp: { sec: 0, nanosec: 0 } },
  name,
  model,
  state,
  detail: "",
});

describe("model status", () => {
  it("keeps the newest status per model", () => {
    let m = mergeStatus({}, status("vla", 1, "smolvla"));
    m = mergeStatus(m, status("vla", 2, "smolvla"));
    m = mergeStatus(m, status("vlm", 0));
    expect(m.vla && stateOf(m.vla)).toBe("loaded");
    expect(Object.keys(m).sort()).toEqual(["vla", "vlm"]);
  });

  it("warns while any model is loading or unloading, and is silent otherwise", () => {
    expect(swapNotice({ vlm: status("vlm", 2, "Qwen3-VL-4B") })).toBeNull();
    const notice = swapNotice({
      vla: status("vla", 1, "smolvla_arena_multitask"),
      rlcd: status("rlcd", 3, "Laya (auto)"),
    });
    expect(notice).toContain("loading smolvla_arena_multitask");
    expect(notice).toContain("unloading Laya (auto)");
  });
});
