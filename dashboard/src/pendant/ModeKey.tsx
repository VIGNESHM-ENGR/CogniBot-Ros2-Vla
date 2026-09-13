import type { KeyboardEvent } from "react";
import { detentAngle, MODE_HELP, MODES, type Mode } from "../lib/modes";

interface Props {
  mode: Mode;
  onChange: (mode: Mode) => void;
  managerOnline: boolean;
}

/** The pendant's key switch: five detents, one lit LED, and the mode it selects. */
export function ModeKey({ mode, onChange, managerOnline }: Props) {
  const index = MODES.indexOf(mode);
  const step = (delta: number) =>
    onChange(MODES[Math.min(MODES.length - 1, Math.max(0, index + delta))] as Mode);

  const onKeyDown = (event: KeyboardEvent) => {
    if (event.key === "ArrowRight" || event.key === "ArrowDown") step(1);
    else if (event.key === "ArrowLeft" || event.key === "ArrowUp") step(-1);
    else return;
    event.preventDefault();
    event.stopPropagation();
  };

  return (
    <section className="modekey" aria-labelledby="modekey-title">
      <h2 id="modekey-title" className="group-title legend">
        Mode key
      </h2>
      <button
        type="button"
        className="modekey__dial"
        aria-label={`Mode key at ${mode}. Click to turn to the next mode.`}
        onClick={() => onChange(MODES[(index + 1) % MODES.length] as Mode)}
        onKeyDown={onKeyDown}
      >
        <span className="modekey__face" />
        <span className="modekey__bar" style={{ transform: `rotate(${detentAngle(mode)}deg)` }} />
      </button>
      <ul className="modekey__list" role="radiogroup" aria-label="Control mode">
        {MODES.map((m, i) => (
          <li key={m}>
            <button
              type="button"
              role="radio"
              aria-checked={m === mode}
              className="modekey__item"
              onClick={() => onChange(m)}
              title={MODE_HELP[m]}
            >
              <span className="led" data-on={m === mode} />
              <span className="modekey__num">{i + 1}</span>
              <span className="legend">{m}</span>
            </button>
          </li>
        ))}
      </ul>
      <p className="modekey__note">
        {managerOnline
          ? MODE_HELP[mode]
          : "Mode manager offline: the key selects which console keys are live; controllers are not switched."}
      </p>
    </section>
  );
}
