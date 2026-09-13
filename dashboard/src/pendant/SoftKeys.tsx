import { Camera, Cpu, MessagesSquare, Move3d, Waypoints } from "lucide-react";
import { VIEWS, type ViewId } from "../lib/modes";

const ICONS: Record<ViewId, typeof Camera> = {
  camera: Camera,
  motion: Move3d,
  agent: MessagesSquare,
  vla: Waypoints,
  system: Cpu,
};

/** Physical soft keys under the screen, F1–F5. */
export function SoftKeys({ view, onView }: { view: ViewId; onView: (v: ViewId) => void }) {
  return (
    <nav className="softkeys" aria-label="Screen views">
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
