import { ArrowDown, ArrowUp, Grip } from "lucide-react";
import type { JogKey, Mode } from "../lib/modes";

interface Props {
  mode: Mode;
  pressed: ReadonlySet<JogKey>;
  backendOnline: boolean;
  stopped: boolean;
  onJog: (jog: JogKey) => void;
}

const AXES: { axis: string; keys: { jog: JogKey; legend: string; cap: string }[] }[] = [
  {
    axis: "X  forward / back",
    keys: [
      { jog: "x+", legend: "+X", cap: "W" },
      { jog: "x-", legend: "−X", cap: "S" },
    ],
  },
  {
    axis: "Y  left / right",
    keys: [
      { jog: "y+", legend: "+Y", cap: "A" },
      { jog: "y-", legend: "−Y", cap: "D" },
    ],
  },
  {
    axis: "Z  up / down",
    keys: [
      { jog: "z+", legend: "+Z", cap: "↑" },
      { jog: "z-", legend: "−Z", cap: "↓" },
    ],
  },
];

/** Cartesian jog keys. They wake only in TELEOP and only move the arm when mink teleop runs. */
export function JogBlock({ mode, pressed, backendOnline, stopped, onJog }: Props) {
  const live = mode === "TELEOP" && !stopped;
  const reason = stopped
    ? "Stopped: release the stop to jog."
    : mode !== "TELEOP"
      ? "Turn the key to TELEOP (2) to jog."
      : backendOnline
        ? "Hold a key to jog; release stops within 300 ms."
        : "Teleop backend offline: keys show input but send nothing.";

  return (
    <section aria-labelledby="jog-title">
      <h2 id="jog-title" className="group-title legend">
        Jog
      </h2>
      <div className="jog">
        {AXES.map(({ axis, keys }) => (
          <div key={axis} style={{ display: "contents" }}>
            <span className="jog__axis legend">{axis}</span>
            {keys.map((k) => (
              <button
                key={k.jog}
                type="button"
                className="key"
                aria-disabled={!live}
                data-pressed={live && pressed.has(k.jog)}
                onClick={() => live && onJog(k.jog)}
              >
                <span className="led" />
                <span className="key__legend">
                  {k.jog === "z+" ? (
                    <ArrowUp size={14} />
                  ) : k.jog === "z-" ? (
                    <ArrowDown size={14} />
                  ) : (
                    k.legend
                  )}
                </span>
                <span className="key__cap">{k.cap}</span>
              </button>
            ))}
          </div>
        ))}
        <button
          type="button"
          className="key jog__wide"
          aria-disabled={!live}
          data-pressed={live && pressed.has("grip")}
          onClick={() => live && onJog("grip")}
        >
          <span className="led" />
          <span
            className="key__legend"
            style={{ display: "inline-flex", gap: 6, alignItems: "center" }}
          >
            <Grip size={14} /> Gripper
          </span>
          <span className="key__cap">G</span>
        </button>
      </div>
      <p className="deadman" style={{ marginTop: 10 }}>
        <span className="led" data-tone={live && backendOnline ? "yellow" : undefined} />
        {reason}
      </p>
    </section>
  );
}
