interface Props {
  title: string;
  missing: string;
  start: string;
  children: React.ReactNode;
}

/** An honest empty state for a subsystem that is not running yet. */
export function NotRunning({ title, missing, start, children }: Props) {
  return (
    <section className="notrunning">
      <h2>{title}</h2>
      <p className="notrunning__status">
        <span className="led" data-tone="yellow" /> {missing} is not running
      </p>
      <p>{children}</p>
      <p>
        Start it with <code>{start}</code>; this view connects on its own.
      </p>
    </section>
  );
}
