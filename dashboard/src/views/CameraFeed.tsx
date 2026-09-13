import { useEffect, useRef, useState } from "react";
import { mjpegUrl } from "../config";

/** One MJPEG stream from web_video_server with a no-signal state. */
export function CameraFeed({
  topic,
  label,
  compact = false,
}: {
  topic: string;
  label: string;
  compact?: boolean;
}) {
  const img = useRef<HTMLImageElement>(null);
  const [live, setLive] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    // MJPEG streams fire no reliable load event: poll for a decoded frame, quickly until the
    // first one arrives, and reconnect after ~6 s without frames.
    let misses = 0;
    let timer: ReturnType<typeof setTimeout>;
    const check = () => {
      const ok = (img.current?.naturalWidth ?? 0) > 0;
      setLive(ok);
      misses = ok ? 0 : misses + 1;
      if (misses >= 12) {
        misses = 0;
        setAttempt((a) => a + 1);
      }
      timer = setTimeout(check, ok ? 3000 : 500);
    };
    timer = setTimeout(check, 500);
    return () => clearTimeout(timer);
  }, [topic]);

  return (
    <div className="camera">
      <img
        ref={img}
        key={attempt}
        className="camera__feed"
        src={`${mjpegUrl(topic)}&attempt=${attempt}`}
        alt={`${label} camera`}
        onError={() => setLive(false)}
      />
      {!live && (
        <div className="nosignal" role="status">
          <span className="nosignal__title">No signal</span>
          {!compact && <span className="mono">{topic}</span>}
        </div>
      )}
      <span className="camera__tag legend">{label}</span>
    </div>
  );
}
