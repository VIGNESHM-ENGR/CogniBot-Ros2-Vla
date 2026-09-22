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
    help: "Pick and place by motions: the model picks one move per step toward the current stage (above the cube, onto it, lift, carry, lower). Grasp, release and drop checks come from the cube's pose.",
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

/** Guard questions answer yes/no; only `unsafe` can refuse a run (cognibot_laya decide.BLOCKING). */
const GUARD = new Set(["unsafe", "out_of_scope", "needs_human"]);
const BLOCKING = new Set(["unsafe"]);

export interface Verdict {
  word: "acted" | "escalated" | "clear" | "blocked" | "advisory";
  /** LED state: lit green, lit yellow, or off. */
  tone: "on" | "yellow" | "off";
}

/**
 * What the node did with a decision, in the words the row shows.
 *
 * A choice either cleared the confidence gate (acted) or did not (escalated). A guard question is
 * a flag: `unsafe` above the threshold blocks the run; the other two are published but advisory,
 * because measured on this scene they swing with the object list rather than with the request.
 */
export function verdict(
  decision: DecisionMsg,
  minConfidence: number,
  guardThreshold: number,
): Verdict {
  if (GUARD.has(decision.question_id)) {
    const raised = (decision.probabilities[decision.options.indexOf("true")] ?? 0) > guardThreshold;
    if (!raised) return { word: "clear", tone: "off" };
    return BLOCKING.has(decision.question_id)
      ? { word: "blocked", tone: "yellow" }
      : { word: "advisory", tone: "yellow" };
  }
  return gated(decision, minConfidence)
    ? { word: "escalated", tone: "yellow" }
    : { word: "acted", tone: "on" };
}

/**
 * Whether a decision cleared the confidence gate.
 *
 * Below the gate the node escalates instead of moving, which is the point of a calibrated model:
 * a wrong answer it is unsure about never reaches the arm.
 */
export const gated = (decision: DecisionMsg, minConfidence: number): boolean =>
  decision.confidence < minConfidence;
