/** Parse the pieces of URDF and SRDF the console needs: joint limits and named group states. */

export interface JointLimit {
  name: string;
  lower: number;
  upper: number;
}

export interface GroupState {
  name: string;
  group: string;
  joints: Record<string, number>;
}

export interface UrdfSummary {
  robotName: string;
  joints: JointLimit[];
}

function parseXml(xml: string): Document | null {
  const doc = new DOMParser().parseFromString(xml, "application/xml");
  return doc.getElementsByTagName("parsererror").length > 0 ? null : doc;
}

/** Movable (revolute/prismatic) joints with finite limits, in document order. */
export function parseUrdf(xml: string): UrdfSummary | null {
  const doc = parseXml(xml);
  if (!doc) return null;
  const robot = doc.documentElement;
  const joints: JointLimit[] = [];
  for (const joint of Array.from(robot.getElementsByTagName("joint"))) {
    const type = joint.getAttribute("type");
    if (type !== "revolute" && type !== "prismatic") continue;
    if (joint.getElementsByTagName("mimic").length > 0) continue;
    const limit = joint.getElementsByTagName("limit")[0];
    const lower = Number(limit?.getAttribute("lower"));
    const upper = Number(limit?.getAttribute("upper"));
    if (!Number.isFinite(lower) || !Number.isFinite(upper)) continue;
    joints.push({ name: joint.getAttribute("name") ?? "", lower, upper });
  }
  return { robotName: robot.getAttribute("name") ?? "robot", joints };
}

export function parseSrdfGroupStates(xml: string): GroupState[] {
  const doc = parseXml(xml);
  if (!doc) return [];
  return Array.from(doc.getElementsByTagName("group_state")).map((state) => {
    const joints: Record<string, number> = {};
    for (const joint of Array.from(state.getElementsByTagName("joint"))) {
      joints[joint.getAttribute("name") ?? ""] = Number(joint.getAttribute("value"));
    }
    return {
      name: state.getAttribute("name") ?? "",
      group: state.getAttribute("group") ?? "",
      joints,
    };
  });
}

export type LimitState = "nominal" | "near" | "at";

/** How close a joint is to either limit: within 8% of the range is "near", 1% is "at". */
export function limitState(value: number, limit: JointLimit): LimitState {
  const range = limit.upper - limit.lower;
  if (range <= 0) return "nominal";
  const margin = Math.min(value - limit.lower, limit.upper - value) / range;
  if (margin <= 0.01) return "at";
  if (margin <= 0.08) return "near";
  return "nominal";
}

/** Position of `value` inside the limit range, clamped to 0..1. */
export function rangeFraction(value: number, limit: JointLimit): number {
  const range = limit.upper - limit.lower;
  if (range <= 0) return 0.5;
  return Math.min(1, Math.max(0, (value - limit.lower) / range));
}
