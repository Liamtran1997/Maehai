import { StatusPill, formatThaiDate, formatTHB } from "@maehai/ui";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ErrorNotice } from "../components/Notice";
import { api, unwrap } from "../lib/api";
import { PILL, STATUS_TABS } from "../lib/status";

const PAGE = 25;

export function Orders() {
  const [params, setParams] = useSearchParams();
  const status = params.get("status") ?? "";
  const q = params.get("q") ?? "";
  const [offset, setOffset] = useState(0);
  const [draft, setDraft] = useState(q);

  const set = (next: Record<string, string>) => {
    const p = new URLSearchParams(params);
    for (const [k, v] of Object.entries(next)) v ? p.set(k, v) : p.delete(k);
    setParams(p); setOffset(0);
  };

  const list = useQuery({
    queryKey: ["orders", status, q, offset], placeholderData: (prev) => prev,
    queryFn: async () => unwrap(await api.GET("/api/admin/orders", { params: { query: { status: status || undefined, q: q || undefined, limit: PAGE, offset } } })),
  });
  const total = list.data?.count ?? 0;

  return (
    <>
      <div className="topbar"><h1>คำสั่งซื้อ</h1></div>
      <div className="tabs" role="group" aria-label="กรองตามสถานะ">
        {STATUS_TABS.map((t) => <button key={t.key} className="mh-chip" aria-pressed={status === t.key} onClick={() => set({ status: t.key })}>{t.label}</button>)}
      </div>
      <form className="toolbar" role="search" onSubmit={(e) => { e.preventDefault(); set({ q: draft.trim() }); }}>
        <div className="searchbox">
          <svg className="ic" viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="M20 20l-4-4" /></svg>
          <label htmlFor="s" style={{ position: "absolute", left: -9999 }}>ค้นหาคำสั่งซื้อ</label>
          <input className="mh-input" id="s" value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="เลขที่สั่งซื้อ ชื่อ หรือเบอร์โทร" />
        </div>
        <button className="mh-btn mh-btn--secondary mh-btn--sm" type="submit">ค้นหา</button>
      </form>
      <ErrorNotice error={list.error} />
      <div className="mh-tablewrap">
        <table className="mh-table">
          <thead><tr><th>เลขที่สั่งซื้อ</th><th>ลูกค้า</th><th>โทร</th><th>วิธีรับ</th><th>นัดรับ</th><th className="r">ยอดรวม</th><th>สถานะ</th><th>สั่งเมื่อ</th></tr></thead>
          <tbody>
            {list.data?.items.map((o) => (
              <tr key={o.number}>
                <td><Link className="mh-code" to={`/orders/${o.number}`}>{o.number}</Link></td><td className="wrap">{o.customer_name}</td><td className="num">{o.phone}</td>
                <td className="wrap">{o.shipping_method.name}</td><td className="wrap">{formatThaiDate(o.requested_date)}</td>
                <td className="r">{o.total_satang === null ? "รอแจ้งค่าส่ง" : formatTHB(o.total_satang)}</td>
                <td><StatusPill status={PILL[o.status]} /></td><td className="wrap">{formatThaiDate(o.created_at)}</td>
              </tr>
            ))}
            {list.data && list.data.items.length === 0 && <tr><td colSpan={8} className="ink-muted">ไม่พบคำสั่งซื้อ</td></tr>}
          </tbody>
        </table>
      </div>
      <div className="pager">
        <p className="sm ink-muted">{total === 0 ? "ไม่มีรายการ" : `แสดง ${offset + 1} ถึง ${Math.min(offset + PAGE, total)} จาก ${total} รายการ`}</p>
        <div className="mh-row" style={{ gap: 8 }}>
          <button className="mh-btn mh-btn--secondary mh-btn--sm" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>ก่อนหน้า</button>
          <button className="mh-btn mh-btn--secondary mh-btn--sm" disabled={offset + PAGE >= total} onClick={() => setOffset(offset + PAGE)}>ถัดไป</button>
        </div>
      </div>
    </>
  );
}
