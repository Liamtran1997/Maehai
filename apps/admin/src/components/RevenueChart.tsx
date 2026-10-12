import { formatTHB, formatThaiDate } from "@maehai/ui";

type Day = { date: string; revenue_satang: number };
const W = 640, H = 220, L = 56, R = 16, T = 28, B = 34;

/** Rounds up to a "nice" axis maximum in baht (1, 2, 5 x 10^n). */
function niceMax(satang: number) {
  const baht = Math.max(satang / 100, 100);
  const p = 10 ** Math.floor(Math.log10(baht));
  const m = [1, 2, 5, 10].find((k) => k * p >= baht)!;
  return m * p * 100;
}

export function RevenueChart({ daily }: { daily: Day[] }) {
  const peak = daily.reduce((a, d) => (d.revenue_satang > a.revenue_satang ? d : a), daily[0]);
  const max = niceMax(peak.revenue_satang);
  const x = (i: number) => L + (daily.length === 1 ? (W - L - R) / 2 : (i * (W - L - R)) / (daily.length - 1));
  const y = (v: number) => T + (H - T - B) * (1 - v / max);
  const pts = daily.map((d, i) => `${x(i)},${y(d.revenue_satang)}`).join(" ");
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => f * max);
  const short = (s: number) => (s >= 100000 ? `${s / 100000}k` : String(s / 100));
  const every = Math.ceil(daily.length / 8);
  const pi = daily.indexOf(peak);
  const total = daily.reduce((a, d) => a + d.revenue_satang, 0);

  return (
    <svg className="chart" viewBox={`0 0 ${W} ${H}`} role="img"
      aria-label={total === 0 ? "ยังไม่มียอดขายในช่วงนี้" : `กราฟเส้นยอดขายรายวัน สูงสุด ${formatTHB(peak.revenue_satang)} วันที่ ${formatThaiDate(peak.date)}`}>
      {ticks.map((t) => (
        <g key={t}><line className="grid" x1={L} x2={W - R} y1={y(t)} y2={y(t)} /><text x={L - 8} y={y(t) + 4} textAnchor="end">{short(t)}</text></g>
      ))}
      {total > 0 && (
        <>
          <polygon className="area" points={`${x(0)},${y(0)} ${pts} ${x(daily.length - 1)},${y(0)}`} />
          <polyline className="ln" points={pts} />
          <circle className="pt" cx={x(pi)} cy={y(peak.revenue_satang)} r="5" />
          <text className="pt-lbl" x={Math.min(x(pi), W - R - 30)} y={y(peak.revenue_satang) - 10} textAnchor="middle">{formatTHB(peak.revenue_satang, { hideZeroSatang: true })}</text>
        </>
      )}
      {daily.map((d, i) => i % every === 0 && (
        <text key={d.date} x={x(i)} y={H - 10} textAnchor="middle">{new Date(d.date + "T00:00:00").getDate()}/{new Date(d.date + "T00:00:00").getMonth() + 1}</text>
      ))}
    </svg>
  );
}
