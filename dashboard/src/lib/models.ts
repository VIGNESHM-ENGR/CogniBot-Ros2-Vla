import type { ModelStatusMsg } from "../ros/messages";

export const MODEL_STATES = ["unloaded", "loading", "loaded", "unloading"] as const;
export type ModelState = (typeof MODEL_STATES)[number];

/** The three GPU models, in the order the gauge lists them. */
export const MODEL_SLOTS = [
  { name: "vlm", label: "VLM" },
  { name: "vla", label: "VLA" },
  { name: "rlcd", label: "RLCD" },
] as const;

export const stateOf = (m: ModelStatusMsg): ModelState => MODEL_STATES[m.state] ?? "unloaded";

/** Keep the newest status per model name. */
export function mergeStatus(
  current: Record<string, ModelStatusMsg>,
  next: ModelStatusMsg,
): Record<string, ModelStatusMsg> {
  return { ...current, [next.name]: next };
}

/**
 * The warning shown while models are swapped on the GPU, or null when nothing is moving.
 * Loading and unloading happen together when the operator switches between VLM, VLA and RLCD.
 */
export function swapNotice(models: Record<string, ModelStatusMsg>): string | null {
  const moving = MODEL_SLOTS.map((s) => models[s.name]).filter(
    (m): m is ModelStatusMsg => !!m && (stateOf(m) === "loading" || stateOf(m) === "unloading"),
  );
  if (moving.length === 0) return null;
  const parts = moving.map(
    (m) => `${stateOf(m) === "loading" ? "loading" : "unloading"} ${m.model || m.name}`,
  );
  return `GPU: ${parts.join(" · ")} — the arm waits until it is ready`;
}
