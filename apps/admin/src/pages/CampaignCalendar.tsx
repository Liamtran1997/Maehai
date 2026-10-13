import { useState } from "react";
import { Link } from "react-router-dom";
import type { Campaign } from "../lib/api";

const MONTHS = ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."];
const TONE: Record<string, string> = { live: "var(--leaf)", scheduled: "#0b5d82", draft: "var(--surface-300)", ended: "var(--ink-muted)" };
const BKK_YEAR = (iso: string) => Number(new Intl.DateTimeFormat("en", { timeZone: "Asia/Bangkok", year: "numeric" }).format(new Date(iso)));

/** The year at a glance: one row per campaign, a bar over the months it runs. Click a bar to open it. */
export function CampaignCalendar({ campaigns }: { campaigns: Campaign[] }) {
  const thisYear = BKK_YEAR(new Date().toISOString());
  const [year, setYear] = useState(thisYear);
  const yearStart = Date.UTC(year, 0, 1) - 7 * 3600_000;          // Bangkok midnight, 1 January
  const yearEnd = Date.UTC(year + 1, 0, 1) - 7 * 3600_000;
  const span = yearEnd - yearStart;
  const rows = campaigns.filter((c) => BKK_YEAR(c.starts_at) <= year && BKK_YEAR(c.ends_at) >= year);
  const pct = (t: number) => Math.min(100, Math.max(0, ((t - yearStart) / span) * 100));

  return (
    <section className="panel" aria-label={`ปฏิทินแคมเปญปี ${year + 543}`} style={{ overflowX: "auto" }}>
      <div className="mh-row" style={{ gap: 8 }}>
        <button className="mh-btn mh-btn--secondary mh-btn--sm" type="button" aria-label="ปีก่อน" onClick={() => setYear(year - 1)}>‹</button>
        <b style={{ font: "500 18px/1 var(--font-display)" }}>ปี {year + 543}</b>
        <button className="mh-btn mh-btn--secondary mh-btn--sm" type="button" aria-label="ปีถัดไป" onClick={() => setYear(year + 1)}>›</button>
        {year !== thisYear && <button className="mh-btn mh-btn--secondary mh-btn--sm" type="button" onClick={() => setYear(thisYear)}>ปีนี้</button>}
      </div>
      <div style={{ minWidth: 760, display: "grid", gridTemplateColumns: "180px repeat(12, minmax(0, 1fr))", gap: "8px 0", fontSize: 13, marginTop: 12 }}>
        <span />
        {MONTHS.map((m) => <span key={m} className="muted" style={{ fontWeight: 600, textAlign: "center" }}>{m}</span>)}
        {rows.length === 0 && <p className="ink-muted" style={{ gridColumn: "1 / -1", margin: 0 }}>ยังไม่มีแคมเปญในปีนี้</p>}
        {rows.map((c) => {
          const s = pct(Math.max(Date.parse(c.starts_at), yearStart));
          const e = pct(Math.min(Date.parse(c.ends_at), yearEnd));
          return (
            <div key={c.id} style={{ display: "contents" }}>
              <Link to={`/campaigns/${c.id}`} style={{ gridColumn: 1, alignSelf: "center", color: "var(--ink)", fontWeight: 600, textDecoration: "none", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{c.name}</Link>
              <div style={{ gridColumn: "2 / 14", position: "relative", height: 28, alignSelf: "center" }}>
                <Link to={`/campaigns/${c.id}`} aria-label={`${c.name} · ${c.status_label}`}
                  style={{ position: "absolute", left: `${s}%`, width: `${Math.max(e - s, 0.8)}%`, top: 0, bottom: 0, borderRadius: 6, background: TONE[c.status],
                    border: c.status === "draft" ? "2px dashed var(--ink-muted)" : "none", color: c.status === "draft" ? "var(--ink)" : "#fff",
                    display: "flex", alignItems: "center", padding: "0 8px", fontSize: 12, fontWeight: 600, textDecoration: "none", whiteSpace: "nowrap", overflow: "hidden" }}>
                </Link>
              </div>
            </div>
          );
        })}
      </div>
      <div className="small muted" style={{ display: "flex", flexWrap: "wrap", gap: 16, marginTop: 12 }}>
        <span>● กำลังแสดง</span><span>● ตั้งเวลาแล้ว</span><span>● จบแล้ว</span><span>ร่างมีเส้นประ</span>
      </div>
    </section>
  );
}
