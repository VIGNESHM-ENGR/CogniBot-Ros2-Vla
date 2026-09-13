interface Props {
  latched: boolean;
  onStop: () => void;
  onRelease: () => void;
}

/** Mushroom stop on its yellow backplate. Latches until released, like the physical one. */
export function EStop({ latched, onStop, onRelease }: Props) {
  return (
    <section className="estop" data-latched={latched} aria-label="Stop">
      <button
        type="button"
        className="estop__button"
        onClick={onStop}
        aria-describedby="estop-hint"
      >
        STOP
      </button>
      <div className="estop__state" role="status" aria-live="assertive">
        {latched ? "Stopped" : "Run"}
      </div>
      <p className="estop__hint" id="estop-hint">
        Esc · cancels every goal and holds the current pose
      </p>
      {latched && (
        <button type="button" className="key estop__release" onClick={onRelease}>
          <span className="key__legend">Release</span>
          <span className="key__cap">R</span>
        </button>
      )}
    </section>
  );
}
