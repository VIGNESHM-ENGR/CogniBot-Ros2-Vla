import type { DecisionMsg } from "../ros/messages";

/** The two decision tracks, in the order of the RunDecisionTask constants. */
export const TRACKS = [
  {
    id: 0,
    label: "Skills",
    legend: "Skill per step",
    help: "One decision picks a skill and an object; the scripted fetch, place and home actions run it.",
  },
  {
    id: 1,
    label: "Primitives",
    legend: "Primitive per step",
    help: "One decision picks a 2 cm motion; the teleop IK turns it into joint targets through the safety filter.",
  },
] as const;

export type TrackId = (typeof TRACKS)[number]["id"];

export interface Option {
  label: string;
  probability: number;
  chosen: boolean;
}

/**
 * Options of a decision, most likely first, capped at `limit`.
 *
 * The model scores every option it was given; showing the top few keeps the row readable while
 * the confidence beside it still describes the whole distribution.
 */
export function rankOptions(decision: DecisionMsg, limit = 4): Option[] {
  return decision.options
    .map((label, i) => ({
      label,
      probability: decision.probabilities[i] ?? 0,
      chosen: label === decision.choice,
    }))
    .sort((a, b) => b.probability - a.probability)
    .slice(0, limit);
}

/** Decisions of the newest task only, oldest first — a new task id starts a fresh trace. */
export function currentTask(decisions: DecisionMsg[]): DecisionMsg[] {
  const latest = decisions[decisions.length - 1]?.task_id;
  return latest === undefined ? [] : decisions.filter((d) => d.task_id === latest);
}

/**
 * Whether a decision cleared the confidence gate.
 *
 * Below the gate the node escalates instead of moving, which is the point of a calibrated model:
 * a wrong answer it is unsure about never reaches the arm.
 */
export const gated = (decision: DecisionMsg, minConfidence: number): boolean =>
  decision.confidence < minConfidence;
