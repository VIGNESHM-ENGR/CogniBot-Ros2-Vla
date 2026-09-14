import { useEffect, useRef, useState } from "react";
import { mjpegUrl } from "../config";

export interface FeedOverlay {
  /** Pixel box in the source image plus that image's size. */
  bbox: number[];
  label: string;
  width: number;
  height: number;
}

/** One MJPEG stream from web_video_server with a no-signal state and an optional bbox overlay. */
export function CameraFeed({
  topic,
  label,
  compact = false,
  overlay = null,
}: {
  topic: string;
  label: string;
  compact?: boolean;
  overlay?: FeedOverlay | null;
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
      {live && overlay && (
        // Same box as the contained <img>: an SVG with the source size as viewBox and "meet"
        // scaling lands exactly on the frame, so pixel boxes need no geometry in JS.
        <svg
          className="camera__overlay"
          viewBox={`0 0 ${overlay.width} ${overlay.height}`}
          preserveAspectRatio="xMidYMid meet"
          aria-hidden="true"
        >
          <rect
            x={overlay.bbox[0]}
            y={overlay.bbox[1]}
            width={(overlay.bbox[2] ?? 0) - (overlay.bbox[0] ?? 0)}
            height={(overlay.bbox[3] ?? 0) - (overlay.bbox[1] ?? 0)}
          />
          <text x={overlay.bbox[0]} y={(overlay.bbox[1] ?? 0) - 6}>
            {overlay.label}
          </text>
        </svg>
      )}
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
