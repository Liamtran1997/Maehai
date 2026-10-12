export type StatTileProps = {
  label: string;
  value: string;
  /** Percent or count change vs. previous period, shown with an arrow. */
  delta?: { text: string; direction: "up" | "down"; note?: string };
  /** 2 to 30 points; drawn as a sparkline. */
  series?: number[];
};

function spark(series: number[]) {
  const min = Math.min(...series), max = Math.max(...series), span = max - min || 1;
  return series.map((v, i) => {
    const x = 2 + (i * 116) / (series.length - 1);
    const y = 34 - ((v - min) / span) * 28;
    return [x, y] as const;
  });
}

export function StatTile({ label, value, delta, series }: StatTileProps) {
  const pts = series && series.length > 1 ? spark(series) : null;
  const last = pts?.[pts.length - 1];
  return (
    <div className="mh-tile">
      <span className="mh-tile__label">{label}</span>
      <span className="mh-tile__value">{value}</span>
      {delta && (
        <span className={`mh-delta mh-delta--${delta.direction}`}>
          ▲ {delta.text} {delta.note && <span className="ink-muted" style={{ fontWeight: 400 }}>{delta.note}</span>}
        </span>
      )}
      {pts && last && (
        <svg className="mh-spark" viewBox="0 0 120 40" preserveAspectRatio="none" aria-hidden="true">
          <polyline points={pts.map((p) => p.join(",")).join(" ")} />
          <circle cx={last[0]} cy={last[1]} r="3" />
        </svg>
      )}
    </div>
  );
}
