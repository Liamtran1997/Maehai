import { formatThaiDate } from "@maehai/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { ErrorNotice } from "../components/Notice";
import { api, unwrap, type Campaign } from "../lib/api";
import { useAuth } from "../lib/auth";
import { CampaignReport } from "./CampaignReport";
import { CampaignCalendar } from "./CampaignCalendar";
import { formatTHB } from "@maehai/ui";

const THEMES: Record<string, string> = {
  default: "ปกติ", candle_festival: "แห่เทียนพรรษา", songkran: "สงกรานต์", new_year: "ปีใหม่",
};
const FILTERS = [
  { v: "", l: "ทั้งหมด" }, { v: "live", l: "กำลังแสดง" }, { v: "scheduled", l: "ตั้งเวลาแล้ว" },
  { v: "draft", l: "ร่าง" }, { v: "ended", l: "จบแล้ว" },
];
const TONE: Record<string, string> = { live: "mh-status--done", scheduled: "mh-status--paid", draft: "mh-status--wait", ended: "mh-status--cancel" };
const GLYPH: Record<string, string> = { live: "●", scheduled: "◷", draft: "○", ended: "✓" };

/** Dates are shown and entered in Bangkok time, whatever the browser's zone. */
export function bangkokRange(c: { starts_at: string; ends_at: string }) {
  return `${formatThaiDate(c.starts_at)} ถึง ${formatThaiDate(c.ends_at)}`;
}

export function Campaigns() {
  const [params, setParams] = useSearchParams();
  const { can } = useAuth();
  const canReport = can("reports.view");
  const requested = params.get("tab");
  const tab = requested === "report" || requested === "calendar" ? requested : "list";
  const view = tab === "report" && !canReport ? "list" : tab;
  return (
    <>
      <div className="page-head">
        <div>
          <h1>แคมเปญ</h1>
          <p>เปลี่ยนหน้าตาหน้าร้านตามเทศกาล ตั้งเวลาไว้ล่วงหน้า ระบบเปิดและปิดให้เองตามเวลา</p>
        </div>
        {view === "list" && <div className="actions"><Link className="mh-btn mh-btn--primary mh-btn--sm" to="/campaigns/new">สร้างแคมเปญ</Link></div>}
      </div>
      <div className="list-tabs" role="tablist" aria-label="ส่วนของแคมเปญ">
        <button type="button" role="tab" className="tab" aria-selected={view === "list"} aria-pressed={view === "list"} onClick={() => setParams({})}>แคมเปญ</button>
        <button type="button" role="tab" className="tab" aria-selected={view === "calendar"} aria-pressed={view === "calendar"} onClick={() => setParams({ tab: "calendar" })}>ปฏิทิน</button>
        {canReport && <button type="button" role="tab" className="tab" aria-selected={view === "report"} aria-pressed={view === "report"} onClick={() => setParams({ tab: "report" })}>รายงาน</button>}
      </div>
      {view === "report" && <><CampaignSummary /><CampaignReport /></>}
      {view === "calendar" && <CalendarTab />}
      {view === "list" && <CampaignList />}
    </>
  );
}

function CalendarTab() {
  const list = useQuery({ queryKey: ["campaigns"], queryFn: async () => unwrap(await api.GET("/api/admin/campaigns")) });
  return <><ErrorNotice error={list.error} />{list.data && <CampaignCalendar campaigns={list.data.items} />}</>;
}

/** Orders, goods sold and hero presses per campaign, for the whole life of each campaign. */
function CampaignSummary() {
  const q = useQuery({ queryKey: ["campaign-summary"], queryFn: async () => unwrap(await api.GET("/api/admin/campaign-summary")) });
  return (
    <section className="apanel" style={{ marginBottom: 16 }}>
      <h2>ผลของแคมเปญ</h2>
      <ErrorNotice error={q.error} />
      {q.data && q.data.items.length === 0 && <p className="ink-muted">ยังไม่มีแคมเปญ</p>}
      {q.data && q.data.items.length > 0 && (
        <div className="mh-tablewrap" style={{ border: 0 }}>
          <table className="mh-table">
            <thead><tr><th>แคมเปญ</th><th>สถานะ</th><th className="r">ออเดอร์ที่จ่ายแล้ว</th><th className="r">ยอดสินค้า</th><th className="r">กดปุ่มบนหน้าแรก</th></tr></thead>
            <tbody>
              {q.data.items.map((c) => (
                <tr key={c.id}>
                  <td><span className="bold">{c.name}</span><br /><span className="xs ink-muted">{bangkokRange(c)}</span></td>
                  <td>{c.status_label}</td>
                  <td className="r">{c.orders}</td>
                  <td className="r">{formatTHB(c.goods_satang, { hideZeroSatang: true })}</td>
                  <td className="r">{c.hero_clicks}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="small muted" style={{ margin: "8px 0 0" }}>นับเฉพาะออเดอร์ที่ชำระเงินแล้วและไม่ถูกยกเลิก ในช่วงเวลาที่แคมเปญแสดงอยู่</p>
    </section>
  );
}

function CampaignList() {
  const qc = useQueryClient();
  const nav = useNavigate();
  const { can } = useAuth();
  const canPublish = can("campaigns.publish");
  const canEdit = can("campaigns.edit");
  const copy = useMutation({
    mutationFn: async (id: number) => unwrap(await api.POST("/api/admin/campaigns/{campaign_id}/duplicate", { params: { path: { campaign_id: id } } })),
    onSuccess: (c) => { void qc.invalidateQueries({ queryKey: ["campaigns"] }); nav(`/campaigns/${c.id}`); },
  });
  const [filter, setFilter] = useState("");
  const list = useQuery({ queryKey: ["campaigns"], queryFn: async () => unwrap(await api.GET("/api/admin/campaigns")) });
  const end = useMutation({
    mutationFn: async (id: number) => unwrap(await api.POST("/api/admin/campaigns/{campaign_id}/end", { params: { path: { campaign_id: id } } })),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["campaigns"] }),
  });
  const items = (list.data?.items ?? []).filter((c) => !filter || c.status === filter);

  return (
    <>
      <div className="toolbar" role="group" aria-label="กรองตามสถานะ">
        {FILTERS.map((f) => <button key={f.v} type="button" className="mh-chip" aria-pressed={filter === f.v} onClick={() => setFilter(f.v)}>{f.l}</button>)}
        <span className="small muted" style={{ marginLeft: "auto" }}>{items.length} รายการ</span>
      </div>
      <ErrorNotice error={list.error ?? end.error ?? copy.error} />
      <div className="mh-tablewrap">
        <table className="mh-table">
          <thead><tr><th>แคมเปญ</th><th>หน้าตา</th><th>ช่วงเวลา</th><th>ส่วนหัว</th><th>สถานะ</th><th><span style={{ position: "absolute", left: -9999 }}>จัดการ</span></th></tr></thead>
          <tbody>
            {items.map((c) => (
              <tr key={c.id}>
                <td className="cellname"><b>{c.name}</b><span>{c.products.length ? `${c.products.length} สินค้าของเทศกาล` : "ยังไม่ได้เลือกสินค้า"}</span></td>
                <td>{THEMES[c.theme] ?? c.theme}</td>
                <td className="wrap">{bangkokRange(c)}</td>
                <td>{c.hero_kind === "animation" ? "ภาพเคลื่อนไหว" : c.hero_kind === "image" ? "รูปภาพ" : "ปกติ"}</td>
                <td><span className={`mh-status ${TONE[c.status]}`} data-glyph={GLYPH[c.status]}>{c.status_label}</span></td>
                <td>
                  <div className="mh-row" style={{ gap: 8, flexWrap: "wrap", justifyContent: "flex-end" }}>
                    <Link className="mh-btn mh-btn--secondary mh-btn--sm" to={`/campaigns/${c.id}`}>{c.status === "ended" ? "ดู" : "แก้ไข"}</Link>
                    {canEdit && <button type="button" className="mh-btn mh-btn--secondary mh-btn--sm" disabled={copy.isPending} onClick={() => copy.mutate(c.id)}>ทำซ้ำ</button>}
                    {canPublish && c.status === "live" && (
                      <button type="button" className="mh-btn mh-btn--secondary mh-btn--sm" style={{ color: "var(--danger)" }} disabled={end.isPending}
                        onClick={() => { if (window.confirm(`จบ “${c.name}” ตอนนี้เลยหรือไม่ ลูกค้าจะเห็นหน้าปกติทันที`)) end.mutate(c.id); }}>จบก่อนกำหนด</button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
            {list.data && items.length === 0 && <tr><td colSpan={6} className="ink-muted">ยังไม่มีแคมเปญในกลุ่มนี้</td></tr>}
          </tbody>
        </table>
      </div>
    </>
  );
}
