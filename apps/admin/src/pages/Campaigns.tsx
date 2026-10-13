import { formatThaiDate } from "@maehai/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ErrorNotice } from "../components/Notice";
import { api, unwrap, type Campaign } from "../lib/api";
import { useAuth } from "../lib/auth";
import { CampaignReport } from "./CampaignReport";

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
export function bangkokRange(c: Campaign) {
  return `${formatThaiDate(c.starts_at)} ถึง ${formatThaiDate(c.ends_at)}`;
}

export function Campaigns() {
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") === "report" ? "report" : "list";
  const { can } = useAuth();
  const canReport = can("reports.view");
  return (
    <>
      <div className="page-head">
        <div>
          <h1>แคมเปญ</h1>
          <p>เปลี่ยนหน้าตาหน้าร้านตามเทศกาล ตั้งเวลาไว้ล่วงหน้า ระบบเปิดและปิดให้เองตามเวลา</p>
        </div>
        {tab === "list" && <div className="actions"><Link className="mh-btn mh-btn--primary mh-btn--sm" to="/campaigns/new">สร้างแคมเปญ</Link></div>}
      </div>
      <div className="list-tabs" role="tablist" aria-label="ส่วนของแคมเปญ">
        <button type="button" role="tab" className="tab" aria-selected={tab === "list"} aria-pressed={tab === "list"} onClick={() => setParams({})}>แคมเปญ</button>
        {canReport && <button type="button" role="tab" className="tab" aria-selected={tab === "report"} aria-pressed={tab === "report"} onClick={() => setParams({ tab: "report" })}>รายงาน</button>}
      </div>
      {tab === "report" && canReport ? <CampaignReport /> : <CampaignList />}
    </>
  );
}

function CampaignList() {
  const qc = useQueryClient();
  const { can } = useAuth();
  const canPublish = can("campaigns.publish");
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
      <ErrorNotice error={list.error ?? end.error} />
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
