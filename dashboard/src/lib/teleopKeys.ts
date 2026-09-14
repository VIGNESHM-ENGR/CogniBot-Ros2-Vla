/** Keyboard jog state → TeleopCommand. Pure so the reducer and mapping are testable. */

import type { JogKey } from "./modes";

export interface JogState {
  held: ReadonlySet<JogKey>;
  /** Gripper toggle requested since the last publish (edge-triggered). */
  gripperToggle: boolean;
}

export const EMPTY_JOG: JogState = { held: new Set(), gripperToggle: false };

export type JogEvent =
  | { type: "down"; jog: JogKey }
  | { type: "up"; jog: JogKey }
  | { type: "release-all" }
  | { type: "published" };

export function jogReducer(state: JogState, event: JogEvent): JogState {
  switch (event.type) {
    case "down": {
      if (event.jog === "grip") return { ...state, gripperToggle: true };
      if (state.held.has(event.jog)) return state;
      return { ...state, held: new Set(state.held).add(event.jog) };
    }
    case "up": {
      if (event.jog === "grip" || !state.held.has(event.jog)) return state;
      const held = new Set(state.held);
      held.delete(event.jog);
      return { ...state, held };
    }
    case "release-all":
      return state.held.size === 0 && !state.gripperToggle ? state : EMPTY_JOG;
    case "published":
      return state.gripperToggle ? { ...state, gripperToggle: false } : state;
  }
}

export interface TeleopCommandMsg {
  header: { frame_id: string };
  linear: { x: number; y: number; z: number };
  wrist_roll: number;
  shoulder_pan: number;
  gripper: number;
}

export const GRIPPER_NONE = 0;
export const GRIPPER_TOGGLE = 1;

const axis = (held: ReadonlySet<JogKey>, plus: JogKey, minus: JogKey) =>
  (held.has(plus) ? 1 : 0) - (held.has(minus) ? 1 : 0);

/** The command for the current key state; null when nothing is held and no toggle is pending. */
export function commandFor(state: JogState, frameId: string): TeleopCommandMsg | null {
  if (state.held.size === 0 && !state.gripperToggle) return null;
  return {
    header: { frame_id: frameId },
    linear: {
      x: axis(state.held, "x+", "x-"),
      y: axis(state.held, "y+", "y-"),
      z: axis(state.held, "z+", "z-"),
    },
    wrist_roll: axis(state.held, "roll+", "roll-"),
    shoulder_pan: axis(state.held, "pan+", "pan-"),
    gripper: state.gripperToggle ? GRIPPER_TOGGLE : GRIPPER_NONE,
  };
}
