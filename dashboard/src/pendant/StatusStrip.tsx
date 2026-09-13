import type { Mode } from "../lib/modes";
import type { LinkState } from "../ros/RosProvider";

interface Props {
  link: LinkState;
  url: string;
  robotName: string | null;
  mode: Mode;
  stopped: boolean;
  commander: string;
  jointRate: number;
  simTime: number | null;
}

/** Pendant status line: link, robot, mode, who holds the arm, data rate and sim clock. */
export function StatusStrip(props: Props) {
  const { link, url, robotName, mode, stopped, commander, jointRate, simTime } = props;
  return (
    <header className="status">
      <span className="status__item">
        <span
          className="led"
          data-on={link === "connected"}
          data-tone={link === "disconnected" ? "red" : undefined}
        />
        <span className="status__label">Link</span>
        <span className="status__value" data-tone={link === "disconnected" ? "red" : undefined}>
          {link === "connected" ? "online" : link === "connecting" ? "connecting" : "lost"}
        </span>
        <span className="mono" style={{ color: "var(--ink-3)" }}>
          {url.replace(/^ws:\/\//, "")}
        </span>
      </span>
      <span className="status__item">
        <span className="status__label">Robot</span>
        <span className="status__value">{robotName ?? "—"}</span>
      </span>
      <span className="status__item">
        <span className="status__label">Mode</span>
        <span className="status__value">{mode}</span>
      </span>
      <span className="status__item">
        <span className="status__label">Arm</span>
        <span className="status__value" data-tone={stopped ? "red" : undefined}>
          {stopped ? "stopped" : commander}
        </span>
      </span>
      <span className="status__spacer" />
      <span className="status__item">
        <span className="status__label">Joints</span>
        <span className="status__value">{jointRate.toFixed(0)} Hz</span>
      </span>
      <span className="status__item">
        <span className="status__label">Sim</span>
        <span className="status__value">{simTime === null ? "—" : `${simTime.toFixed(1)} s`}</span>
      </span>
    </header>
  );
}
