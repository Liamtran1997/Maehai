export type BandColor = "yellow" | "red";

/** The wrapped หมูยอ log with a rubber band. Placeholder art until real product photos exist. */
export function LogMark({ bands = ["yellow"] }: { bands?: BandColor[] }) {
  const xs = [100, 60, 20];
  return (
    <svg className="mh-log" viewBox="0 0 160 64" aria-hidden="true">
      <rect className="wrap" width="160" height="64" rx="32" />
      {bands.map((b, i) => (
        <rect key={i} className={b === "red" ? "band-r" : "band-y"} x={xs[i] ?? 100} width="14" height="64" />
      ))}
    </svg>
  );
}
