import { formatThaiDate } from "@maehai/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { ErrorNotice } from "../components/Notice";
import { api, unwrap } from "../lib/api";

const REASONS = [
  { v: "receive", l: "รับของเข้า (+)", hint: "จำนวนที่เพิ่ม" },
  { v: "waste", l: "ของเสีย / หมดอายุ (−)", hint: "จำนวนที่ตัดออก" },
  { v: "count", l: "นับสต็อกจริง (ตั้งค่า)", hint: "จำนวนที่นับได้ตอนนี้" },
];

export function Inventory() {
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [sku, setSku] = useState<string | null>(null);
  const [mode, setMode] = useState<"adjust" | "transfer">("adjust");
  const [form, setForm] = useState({ branch: "", to: "", reason: "receive", quantity: "", note: "" });

  const branches = useQuery({ queryKey: ["branches"], queryFn: async () => unwrap(await api.GET("/api/admin/inventory/branches")) });
  const stock = useQuery({ queryKey: ["stock", q], placeholderData: (p) => p, queryFn: async () => unwrap(await api.GET("/api/admin/inventory/stock", { params: { query: { q: q || undefined } } })) });
  const moves = useQuery({ queryKey: ["movements", sku], queryFn: async () => unwrap(await api.GET("/api/admin/inventory/movements", { params: { query: { sku: sku ?? undefined, limit: 20 } } })) });
  const row = stock.data?.find((r) => r.sku === sku);
  const refresh = () => { for (const k of ["stock", "movements", "todo", "summary"]) void qc.invalidateQueries({ queryKey: [k] }); };

  const track = useMutation({
    mutationFn: async (v: { sku: string; track: boolean }) => unwrap(await api.POST("/api/admin/inventory/variants/{sku}/track", { params: { path: { sku: v.sku } }, body: { track: v.track } })),
    onSuccess: refresh,
  });
  const save = useMutation({
    mutationFn: async () => {
      const qty = parseInt(form.quantity, 10);
      if (!Number.isInteger(qty) || qty < 0) throw new Error("กรอกจำนวนเป็นตัวเลขเต็ม");
      const branch = form.branch || branches.data?.[0]?.code || "";
      if (mode === "transfer") return unwrap(await api.POST("/api/admin/inventory/transfer", { body: { from_branch: branch, to_branch: form.to || branches.data?.find((b) => b.code !== branch)?.code || "", sku: sku!, quantity: qty, note: form.note } }));
      return unwrap(await api.POST("/api/admin/inventory/adjust", { body: { branch, sku: sku!, reason: form.reason, quantity: qty, note: form.note } }));
    },
    onSuccess: () => { setForm((f) => ({ ...f, quantity: "", note: "" })); refresh(); },
  });
  const onSubmit = (e: FormEvent) => { e.preventDefault(); save.mutate(); };
  const hint = REASONS.find((r) => r.v === form.reason)?.hint;

  return (
    <>
      <div className="topbar"><h1>สต็อกสินค้า</h1></div>
      <p className="sm ink-muted">“ว่าง” คือของที่ขายได้จริง = มีอยู่ − จองไว้ให้คำสั่งซื้อที่ยังไม่ส่ง สินค้าที่ไม่เปิดนับสต็อกจะขายได้ไม่จำกัด เปิดนับหลังกรอกจำนวนจริงเข้าระบบแล้ว</p>
      <form className="toolbar" role="search" onSubmit={(e) => e.preventDefault()}>
        <div className="searchbox">
          <svg className="ic" viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="M20 20l-4-4" /></svg>
          <label htmlFor="iq" style={{ position: "absolute", left: -9999 }}>ค้นหาสินค้า</label>
          <input className="mh-input" id="iq" value={q} onChange={(e) => setQ(e.target.value)} placeholder="ค้นหาชื่อสินค้า" />
        </div>
      </form>
      <ErrorNotice error={stock.error ?? track.error} />

      <div className="cols cols--2-1" style={{ alignItems: "start" }}>
        <div className="mh-tablewrap">
          <table className="mh-table">
            <thead>
              <tr><th>สินค้า</th>{branches.data?.map((b) => <th key={b.code} className="r">{b.name}<br /><span className="xs ink-muted" style={{ fontWeight: 400 }}>ว่าง / มีอยู่ (จอง)</span></th>)}<th>นับสต็อก</th><th /></tr>
            </thead>
            <tbody>
              {stock.data?.map((r) => (
                <tr key={r.sku} className={r.sku === sku ? "sel" : ""}>
                  <td><span className="bold">{r.product_name}</span><br /><span className="xs ink-muted">{r.variant_label} · {r.sku}</span></td>
                  {r.levels.map((l) => (
                    <td key={l.branch} className="r">
                      {r.track_stock || l.on_hand > 0 ? <span style={r.track_stock ? undefined : { opacity: 0.55 }}><span className={r.track_stock && l.available <= 5 ? "stock-low" : "bold"}>{l.available}</span> <span className="xs ink-muted">/ {l.on_hand}{l.reserved ? ` (${l.reserved})` : ""}</span></span> : <span className="ink-muted">—</span>}
                    </td>
                  ))}
                  <td><button className="mh-chip" style={{ minHeight: 32 }} aria-pressed={r.track_stock} disabled={track.isPending} onClick={() => track.mutate({ sku: r.sku, track: !r.track_stock })}>{r.track_stock ? "เปิด" : "ปิด"}</button></td>
                  <td><button className="mh-btn mh-btn--secondary mh-btn--sm" onClick={() => { setSku(r.sku); save.reset(); }}>ปรับสต็อก</button></td>
                </tr>
              ))}
              {stock.data?.length === 0 && <tr><td colSpan={5} className="ink-muted">ไม่พบสินค้า</td></tr>}
            </tbody>
          </table>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 16, minWidth: 0 }}>
          {row ? (
            <form className="apanel" onSubmit={onSubmit}>
              <div className="apanel-head"><h2>{row.product_name} ({row.variant_label})</h2><button type="button" className="mh-btn mh-btn--secondary mh-btn--sm" onClick={() => setSku(null)}>ปิด</button></div>
              {!row.track_stock && <div className="notice notice--info"><p>สินค้านี้ยังไม่เปิดนับสต็อก ลูกค้าสั่งได้ไม่จำกัด กรอกจำนวนแล้วกด “เปิด” ในตารางเพื่อเริ่มตัดสต็อก</p></div>}
              <div className="seg" role="group" aria-label="ประเภทการปรับ">
                <button type="button" aria-pressed={mode === "adjust"} onClick={() => setMode("adjust")}>ปรับจำนวน</button>
                <button type="button" aria-pressed={mode === "transfer"} onClick={() => setMode("transfer")}>โอนระหว่างสาขา</button>
              </div>
              <div className="form-grid">
                <div className="mh-field"><label className="mh-label" htmlFor="ib">{mode === "transfer" ? "จากสาขา" : "สาขา"}</label>
                  <select className="mh-select" id="ib" value={form.branch || branches.data?.[0]?.code} onChange={(e) => setForm({ ...form, branch: e.target.value })}>{branches.data?.map((b) => <option key={b.code} value={b.code}>{b.name}</option>)}</select></div>
                {mode === "transfer" ? (
                  <div className="mh-field"><label className="mh-label" htmlFor="it">ไปสาขา</label>
                    <select className="mh-select" id="it" value={form.to || branches.data?.find((b) => b.code !== (form.branch || branches.data?.[0]?.code))?.code} onChange={(e) => setForm({ ...form, to: e.target.value })}>{branches.data?.map((b) => <option key={b.code} value={b.code}>{b.name}</option>)}</select></div>
                ) : (
                  <div className="mh-field"><label className="mh-label" htmlFor="ir">เหตุผล</label>
                    <select className="mh-select" id="ir" value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })}>{REASONS.map((r) => <option key={r.v} value={r.v}>{r.l}</option>)}</select></div>
                )}
              </div>
              <div className="mh-field"><label className="mh-label" htmlFor="iqty">{mode === "transfer" ? "จำนวนที่โอน" : hint}</label><input className="mh-input num" id="iqty" inputMode="numeric" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} required /></div>
              <div className="mh-field"><label className="mh-label" htmlFor="in">หมายเหตุ (ถ้ามี)</label><input className="mh-input" id="in" maxLength={200} value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} placeholder="เช่น ล็อตเช้า" /></div>
              <ErrorNotice error={save.error} />
              {save.isSuccess && <div className="notice notice--ok" role="status"><p>บันทึกแล้ว</p></div>}
              <button className="mh-btn mh-btn--primary" type="submit" disabled={save.isPending}>{save.isPending ? "กำลังบันทึก…" : mode === "transfer" ? "โอนสต็อก" : "บันทึก"}</button>
              <p className="xs ink-muted">ลดต่ำกว่าจำนวนที่จองไว้ไม่ได้ ระบบจะบอกให้ยกเลิกหรือย้ายคำสั่งซื้อก่อน</p>
            </form>
          ) : <div className="apanel"><p className="ink-muted">เลือก “ปรับสต็อก” ที่สินค้าในตารางเพื่อรับของเข้า นับสต็อก หรือโอนระหว่างสาขา</p></div>}

          <section className="apanel">
            <h2>ประวัติ{row ? ` ${row.variant_label}` : "ล่าสุด"}</h2>
            {moves.data?.length === 0 && <p className="ink-muted">ยังไม่มีการเคลื่อนไหว</p>}
            <ol className="tl">
              {moves.data?.map((m, i) => (
                <li key={i} className="done">
                  <span className="pt" />
                  <div>
                    <h3><span className={m.delta < 0 ? "" : "bold"}>{m.delta > 0 ? "+" : ""}{m.delta}</span> · {m.reason_label}{!row && ` · ${m.product_name} (${m.variant_label})`}</h3>
                    <p className="xs ink-muted">{branches.data?.find((b) => b.code === m.branch)?.name} · เหลือ {m.on_hand_after} · {formatThaiDate(m.created_at)} · {m.actor}{m.note ? ` · ${m.note}` : ""}{m.order_number && <> · <Link to={`/orders/${m.order_number}`}>{m.order_number}</Link></>}</p>
                  </div>
                </li>
              ))}
            </ol>
          </section>
        </div>
      </div>
    </>
  );
}
