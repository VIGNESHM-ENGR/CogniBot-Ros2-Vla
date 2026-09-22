export const MODES = ["IDLE", "TELEOP", "MOTION", "VLA", "TWIN"] as const;
export type Mode = (typeof MODES)[number];

/** Key angle for each mode detent, sweeping from -60° to +60°. */
export const detentAngle = (mode: Mode): number => -60 + MODES.indexOf(mode) * 30;

export const MODE_HELP: Record<Mode, string> = {
  IDLE: "Arm idle. Console keys that move the arm stay dead.",
  TELEOP: "Keyboard jog through mink teleop and the safety filter.",
  MOTION: "Planned moves through MoveIt 2: named poses, gripper, move to point.",
  VLA: "SmolVLA skills stream joint targets through the safety filter.",
  TWIN: "Mirror a real SO-101 into the simulation.",
};

export type ViewId = "camera" | "motion" | "agent" | "vla" | "rlcd" | "system";

export const SOURCES = ["free", "front", "wrist"] as const;
export type SourceId = (typeof SOURCES)[number];
export const nextSource = (s: SourceId): SourceId =>
  SOURCES[(SOURCES.indexOf(s) + 1) % SOURCES.length] as SourceId;

export const VIEWS: { id: ViewId; key: string; label: string }[] = [
  { id: "camera", key: "F1", label: "Camera" },
  { id: "motion", key: "F2", label: "Motion" },
  { id: "agent", key: "F3", label: "Agent" },
  { id: "vla", key: "F4", label: "VLA" },
  { id: "rlcd", key: "F5", label: "RLCD" },
  { id: "system", key: "F6", label: "System" },
];

export type JogKey =
  "x+" | "x-" | "y+" | "y-" | "z+" | "z-" | "pan+" | "pan-" | "roll+" | "roll-" | "grip";

const JOG_BY_CODE: Record<string, JogKey> = {
  KeyW: "x+",
  KeyS: "x-",
  KeyA: "y+",
  KeyD: "y-",
  ArrowUp: "z+",
  ArrowDown: "z-",
  KeyQ: "pan+",
  KeyE: "pan-",
  ArrowLeft: "roll+",
  ArrowRight: "roll-",
  KeyG: "grip",
};

export type ConsoleCommand =
  | { kind: "stop" }
  | { kind: "release" }
  | { kind: "cancel" }
  | { kind: "cycleSource" }
  | { kind: "mode"; mode: Mode }
  | { kind: "view"; view: ViewId }
  | { kind: "jog"; jog: JogKey };

/** The jog key a keyup releases, if any. */
export const jogForKey = (code: string): JogKey | null => JOG_BY_CODE[code] ?? null;

/** Map a keydown to a console command. Text fields only receive Esc. */
export function commandForKey(code: string, inTextField: boolean): ConsoleCommand | null {
  if (code === "Escape") return { kind: "stop" };
  if (inTextField) return null;
  if (code === "KeyR") return { kind: "release" };
  if (code === "KeyC") return { kind: "cancel" };
  if (code === "KeyV") return { kind: "cycleSource" };
  const digit = /^Digit([1-5])$/.exec(code);
  if (digit) return { kind: "mode", mode: MODES[Number(digit[1]) - 1] as Mode };
  const fkey = VIEWS.find((v) => v.key === code);
  if (fkey) return { kind: "view", view: fkey.id };
  const jog = JOG_BY_CODE[code];
  return jog ? { kind: "jog", jog } : null;
}
