import { describe, expect, it } from "vitest";
import type { DecisionMsg } from "../ros/messages";
import { currentTask, gated, rankOptions } from "./decisions";

const decision = (over: Partial<DecisionMsg> = {}): DecisionMsg => ({
  header: { frame_id: "", stamp: { sec: 0, nanosec: 0 } },
  task_id: "rlcd-1",
  step: 0,
  question_id: "skill",
  options: ["fetch", "place", "home", "done"],
  probabilities: [0.1, 0.7, 0.05, 0.15],
  choice: "place",
  confidence: 0.62,
  act_probability: 0.9,
  model: "english",
  latency_ms: 480,
  ...over,
});

describe("rankOptions", () => {
  it("orders by probability and marks the choice", () => {
    const options = rankOptions(decision());
    expect(options.map((o) => o.label)).toEqual(["place", "done", "fetch", "home"]);
    expect(options[0]).toMatchObject({ probability: 0.7, chosen: true });
  });

  it("caps the list", () => {
    expect(rankOptions(decision(), 2)).toHaveLength(2);
  });

  it("treats a missing probability as zero", () => {
    const options = rankOptions(decision({ options: ["a", "b"], probabilities: [0.9] }));
    expect(options[1]).toMatchObject({ label: "b", probability: 0 });
  });
});

describe("currentTask", () => {
  it("keeps only the newest task", () => {
    const rows = [decision({ task_id: "rlcd-1" }), decision({ task_id: "rlcd-2", step: 1 })];
    expect(currentTask(rows).map((d) => d.task_id)).toEqual(["rlcd-2"]);
  });

  it("is empty without decisions", () => {
    expect(currentTask([])).toEqual([]);
  });
});

describe("gated", () => {
  it("is true below the gate", () => {
    expect(gated(decision({ confidence: 0.2 }), 0.35)).toBe(true);
    expect(gated(decision({ confidence: 0.62 }), 0.35)).toBe(false);
  });
});
