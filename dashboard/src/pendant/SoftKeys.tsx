import { Camera, Cpu, MessagesSquare, Move3d, Split, Waypoints } from "lucide-react";
import {
  SOURCE_KEY,
  SOURCE_LABELS,
  VIEWS,
  nextSource,
  type SourceId,
  type ViewId,
} from "../lib/modes";

const ICONS: Record<ViewId, typeof Camera> = {
  motion: Move3d,
  agent: MessagesSquare,
  vla: Waypoints,
  rlcd: Split,
  system: Cpu,
};

interface Props {
  view: ViewId;
  onView: (v: ViewId) => void;
  source: SourceId;
  onSource: (s: SourceId) => void;
}

/**
 * Physical soft keys under the screen. F1 flips the viewport to the next camera and names the one
 * showing; F2–F6 choose the control panel beside the stop, so the robot never leaves the screen.
 */
export function SoftKeys({ view, onView, source, onSource }: Props) {
  return (
    <nav className="softkeys" aria-label="Viewport and control panels">
      <button
        type="button"
        className="key softkeys__view"
        onClick={() => onSource(nextSource(source))}
        aria-label={`Viewport: ${SOURCE_LABELS[source]}. Show ${SOURCE_LABELS[nextSource(source)]}`}
      >
        <Camera size={16} aria-hidden="true" />
        <span className="key__legend">{SOURCE_LABELS[source]}</span>
        <span className="key__cap">{SOURCE_KEY}</span>
      </button>
      {VIEWS.map((v) => {
        const Icon = ICONS[v.id];
        return (
          <button
            key={v.id}
            type="button"
            className="key"
            aria-current={v.id === view}
            onClick={() => onView(v.id)}
          >
            <Icon size={16} aria-hidden="true" />
            <span className="key__legend">{v.label}</span>
            <span className="key__cap">{v.key}</span>
          </button>
        );
      })}
    </nav>
  );
}
