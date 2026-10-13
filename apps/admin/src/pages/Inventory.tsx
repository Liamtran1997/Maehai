import { formatThaiDate } from "@maehai/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { ErrorNotice } from "../components/Notice";
import { api, unwrap } from "../lib/api";
import { useAuth } from "../lib/auth";

type Mode = "adjust" | "limits";

// Receiving goods happens only through a receipt slip at the central warehouse, and moving them between places through
// transfer slips. Here: what is lost or counted on the shelf.
const REASONS = [
  { v: "waste", l: "ของเสีย / หมดอายุ (−)", hint: "จำนวนที่ตัดออก" },
  { v: "count", l: "นับสต็อกจริง (ตั้งค่า)", hint: "จำนวนที่นับได้ตอนนี้" },
];

export function Inventory() {
  const qc = useQueryClient();
  const canAdjust = useAuth().can("inventory.adjust");
  const [q, setQ] = useState("");
  const [sku, setSku] = useState<string | null>(null);
  const [mode, setMode] = useState<Mode>("adjust");
  const [form, setForm] = useState({ branch: "", reason: "waste", quantity: "", note: "", quota: "", line: "" });
  const [importing, setImporting] = useState(false);
  const [lowOnly, setLowOnly] = useState(false);

  const branches = useQuery({ queryKey: ["branches"], queryFn: async () => unwrap(await api.GET("/api/admin/inventory/branches")) });
  const stock = useQuery({ queryKey: ["stock", q], placeholderData: (p) => p, queryFn: async () => unwrap(await api.GET("/api/admin/inventory/stock", { params: { query: { q: q || undefined } } })) });
  const moves = useQuery({ queryKey: ["movements", sku], queryFn: async () => unwrap(await api.GET("/api/admin/inventory/movements", { params: { query: { sku: sku ?? undefined, limit: 20 } } })) });

  // Summary tiles and the "ใกล้หมด" filter are computed from the rows already loaded.
  const rows = stock.data ?? [];
  const isLow = (r: (typeof rows)[number]) => r.track_stock && r.levels.some((l) => Number(l.available) <= Number(l.low_stock_line));
  const isOut = (r: (typeof rows)[number]) => r.track_stock && r.levels.every((l) => Number(l.available) <= 0);
  const lowCount = rows.filter(isLow).length;
  const outCount = rows.filter(isOut).length;
  const trackedCount = rows.filter((r) => r.track_stock).length;
  const visible = lowOnly ? rows.filter(isLow) : rows;
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
      return unwrap(await api.POST("/api/admin/inventory/adjust", { body: { branch, sku: sku!, reason: form.reason, quantity: qty, note: form.note } }));
    },
    onSuccess: () => { setForm((f) => ({ ...f, quantity: "", note: "" })); refresh(); },
  });
  const branchCode = form.branch || branches.data?.[0]?.code || "";
  const level = row?.levels.find((l) => l.branch === branchCode);
  // The limits form starts from what is saved, so a blank box always means "no limit / shop default" on purpose.
  const savedQuota = level?.online_quota ?? null;
  const savedLine = level?.low_stock_threshold ?? null;
  useEffect(() => {
    setForm((f) => ({ ...f, quota: savedQuota === null ? "" : String(savedQuota), line: savedLine === null ? "" : String(savedLine) }));
  }, [sku, branchCode, mode, savedQuota, savedLine]);
  const saveLimits = useMutation({
    mutationFn: async () => {
      const num = (v: string, label: string) => {
        if (v.trim() === "") return null;
        const n = Number(v);
        if (!Number.isInteger(n) || n < 0) throw new Error(`${label} ต้องเป็นตัวเลขเต็ม หรือเว้นว่างไว้`);
        return n;
      };
      return unwrap(await api.PUT("/api/admin/inventory/levels", { body: { branch: branchCode, sku: sku!, online_quota: num(form.quota, "โควตาออนไลน์"), low_stock_threshold: num(form.line, "จุดเตือนของใกล้หมด") } }));
    },
    onSuccess: refresh,
  });
  const soldOut = useMutation({
    mutationFn: async () => unwrap(await api.POST("/api/admin/inventory/sold-out", { body: { branch: branchCode, sku: sku!, note: "" } })),
    onSuccess: refresh,
  });
  const onSubmit = (e: FormEvent) => { e.preventDefault(); if (mode === "limits") saveLimits.mutate(); else save.mutate(); };
  const hint = REASONS.find((r) => r.v === form.reason)?.hint;

  return (
    <>
      <div className="page-head">
        <div><h2 style={{ margin: 0, font: "600 18px/1.5 var(--font-sans)" }}>สต็อกในแต่ละสาขา</h2></div>
        {canAdjust && <div className="actions"><button className="mh-btn mh-btn--secondary mh-btn--sm" onClick={() => { setImporting(true); setSku(null); }}>นำเข้าสต็อกจากไฟล์ CSV</button></div>}
      </div>
      <p className="sm ink-muted">รับของเข้า โอนไปสาขา และรับคืนทำในหน้า “คลังสินค้า” “ว่าง” คือของที่ขายได้จริง = มีอยู่ − จองไว้ให้คำสั่งซื้อที่ยังไม่ส่ง สินค้าที่ไม่เปิดนับสต็อกจะขายได้ไม่จำกัด เปิดนับหลังกรอกจำนวนจริงเข้าระบบแล้ว ถ้าตั้ง “โควตาออนไลน์” ไว้ ร้านออนไลน์จะขายได้ไม่เกินโควตาต่อวัน ส่วนที่เหลือเก็บไว้ขายหน้าร้าน</p>
      <form className="toolbar" role="search" onSubmit={(e) => e.preventDefault()}>
        <div className="searchbox">
          <svg className="ic" viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="M20 20l-4-4" /></svg>
          <label htmlFor="iq" style={{ position: "absolute", left: -9999 }}>ค้นหาสินค้า</label>
          <input className="mh-input" id="iq" value={q} onChange={(e) => setQ(e.target.value)} placeholder="ค้นหาชื่อสินค้า" />
        </div>
        <button type="button" className="mh-chip" aria-pressed={lowOnly} onClick={() => setLowOnly(!lowOnly)}>เฉพาะที่ใกล้หมด</button>
      </form>
      <ErrorNotice error={stock.error ?? track.error} />

      {stock.data && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 16 }}>
          <div className="mh-tile"><span className="mh-tile__label">ใกล้หมด</span><span className="mh-tile__value" style={{ color: lowCount ? "var(--band-red)" : undefined }}>{lowCount} รายการ</span><span className="small muted">ต่ำกว่าจุดเตือนในสาขาใดสาขาหนึ่ง</span></div>
          <div className="mh-tile"><span className="mh-tile__label">หมดแล้ว</span><span className="mh-tile__value">{outCount} รายการ</span><span className="small muted">ขายได้เป็นศูนย์ในทุกสาขา</span></div>
          <div className="mh-tile"><span className="mh-tile__label">เปิดนับสต็อก</span><span className="mh-tile__value">{trackedCount} / {stock.data.length}</span><span className="small muted">สินค้าที่ตัดสต็อกตามจำนวนจริง</span></div>
        </div>
      )}

      <div className="cols cols--2-1" style={{ alignItems: "start" }}>
        <div className="mh-tablewrap">
          <table className="mh-table">
            <thead>
              <tr><th>สินค้า</th>{branches.data?.map((b) => <th key={b.code} className="r">{b.name}<br /><span className="xs ink-muted" style={{ fontWeight: 400 }}>ว่าง / มีอยู่ (จอง)</span></th>)}<th>นับสต็อก</th><th /></tr>
            </thead>
            <tbody>
              {visible.map((r) => (
                <tr key={r.sku} className={r.sku === sku ? "sel" : ""}>
                  <td><span className="bold">{r.product_name}</span><br /><span className="xs ink-muted">{r.variant_label} · {r.sku}</span></td>
                  {r.levels.map((l) => (
                    <td key={l.branch} className="r">
                      {r.track_stock || l.on_hand > 0 ? <span style={r.track_stock ? undefined : { opacity: 0.55 }}><span className={r.track_stock && l.available <= l.low_stock_line ? "stock-low" : "bold"}>{l.available}</span> <span className="xs ink-muted">/ {l.on_hand}{l.reserved ? ` (${l.reserved})` : ""}</span></span> : <span className="ink-muted">—</span>}
                      {r.track_stock && l.online_quota !== null && l.online_quota !== undefined && <><br /><span className="xs ink-muted">ออนไลน์วันนี้ {l.online_sold_today}/{l.online_quota}</span></>}
                    </td>
                  ))}
                  <td><button className="mh-chip" style={{ minHeight: 32 }} aria-pressed={r.track_stock} disabled={track.isPending || !canAdjust} onClick={() => track.mutate({ sku: r.sku, track: !r.track_stock })}>{r.track_stock ? "เปิด" : "ปิด"}</button></td>
                  <td><button className="mh-btn mh-btn--secondary mh-btn--sm" onClick={() => { setSku(r.sku); setImporting(false); save.reset(); saveLimits.reset(); soldOut.reset(); }}>{canAdjust ? "ปรับสต็อก" : "ประวัติ"}</button></td>
                </tr>
              ))}
              {stock.data?.length === 0 && <tr><td colSpan={(branches.data?.length ?? 0) + 4} className="ink-muted">ไม่พบสินค้า</td></tr>}
              {stock.data && stock.data.length > 0 && visible.length === 0 && <tr><td colSpan={(branches.data?.length ?? 0) + 4} className="ink-muted">ไม่มีสินค้าที่ใกล้หมด</td></tr>}
            </tbody>
          </table>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 16, minWidth: 0 }}>
          {importing && canAdjust ? <ImportPanel onClose={() => setImporting(false)} onDone={refresh} /> : row && canAdjust ? (
            <form className="apanel" onSubmit={onSubmit}>
              <div className="apanel-head"><h2>{row.product_name} ({row.variant_label})</h2><button type="button" className="mh-btn mh-btn--secondary mh-btn--sm" onClick={() => setSku(null)}>ปิด</button></div>
              {!row.track_stock && <div className="notice notice--info"><p>สินค้านี้ยังไม่เปิดนับสต็อก ลูกค้าสั่งได้ไม่จำกัด กรอกจำนวนแล้วกด “เปิด” ในตารางเพื่อเริ่มตัดสต็อก</p></div>}
              <div className="seg" role="group" aria-label="ประเภทการปรับ">
                <button type="button" aria-pressed={mode === "adjust"} onClick={() => setMode("adjust")}>ปรับจำนวน</button>
                <button type="button" aria-pressed={mode === "limits"} onClick={() => setMode("limits")}>โควตา / จุดเตือน</button>
              </div>
              <div className="form-grid">
                <div className="mh-field"><label className="mh-label" htmlFor="ib">สาขา</label>
                  <select className="mh-select" id="ib" value={form.branch || branches.data?.[0]?.code} onChange={(e) => setForm({ ...form, branch: e.target.value })}>{branches.data?.map((b) => <option key={b.code} value={b.code}>{b.name}</option>)}</select></div>
                {mode === "adjust" && (
                  <div className="mh-field"><label className="mh-label" htmlFor="ir">เหตุผล</label>
                    <select className="mh-select" id="ir" value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })}>{REASONS.map((r) => <option key={r.v} value={r.v}>{r.l}</option>)}</select></div>
                )}
              </div>
              {mode === "limits" ? (
                <>
                  <p className="sm ink-muted">ที่สาขานี้ ว่างทั้งหมด {level?.available ?? 0} ชิ้น · ร้านออนไลน์ขายได้อีกวันนี้ {level?.online_available ?? 0} ชิ้น{level?.online_quota != null ? ` (ขายไปแล้ว ${level.online_sold_today} จากโควตา ${level.online_quota})` : " (ไม่จำกัดโควตา)"}</p>
                  <div className="mh-field"><label className="mh-label" htmlFor="iquota">โควตาออนไลน์ต่อวัน</label>
                    <input className="mh-input num" id="iquota" inputMode="numeric" value={form.quota} placeholder="ไม่จำกัด" onChange={(e) => setForm({ ...form, quota: e.target.value })} />
                    <p className="xs ink-muted">จำนวนสูงสุดที่ร้านออนไลน์ขายได้ต่อวันจากสาขานี้ ที่เหลือเก็บไว้ขายหน้าร้าน เว้นว่าง = ไม่จำกัด (ขายได้จนสต็อกหมด) นับใหม่ทุกเที่ยงคืน</p></div>
                  <div className="mh-field"><label className="mh-label" htmlFor="iline">จุดเตือนของใกล้หมด</label>
                    <input className="mh-input num" id="iline" inputMode="numeric" value={form.line} placeholder={`ค่ากลาง ${level?.low_stock_line ?? 5}`} onChange={(e) => setForm({ ...form, line: e.target.value })} />
                    <p className="xs ink-muted">แจ้งทาง LINE หนึ่งครั้งเมื่อของว่างลดลงถึงจำนวนนี้ เว้นว่าง = ใช้ค่ากลางของร้าน</p></div>
                  <ErrorNotice error={saveLimits.error ?? soldOut.error} />
                  {saveLimits.isSuccess && <div className="notice notice--ok" role="status"><p>บันทึกแล้ว</p></div>}
                  {soldOut.isSuccess && <div className="notice notice--ok" role="status"><p>หยุดขายออนไลน์แล้ว สต็อกที่เหลือคือของที่จองไว้ให้คำสั่งซื้อเท่านั้น</p></div>}
                  <button className="mh-btn mh-btn--primary" type="submit" disabled={saveLimits.isPending}>{saveLimits.isPending ? "กำลังบันทึก…" : "บันทึกโควตาและจุดเตือน"}</button>
                  <button type="button" className="mh-btn mh-btn--danger" disabled={soldOut.isPending || !row.track_stock}
                    onClick={() => { if (window.confirm("ขายหน้าร้านหมดแล้วใช่ไหม ร้านออนไลน์จะหยุดขายสินค้านี้ที่สาขานี้ทันที (คำสั่งซื้อที่จองไว้แล้วยังส่งได้ตามปกติ)")) soldOut.mutate(); }}>
                    {soldOut.isPending ? "กำลังบันทึก…" : "หมดหน้าร้าน — หยุดขายออนไลน์ทันที"}
                  </button>
                  {!row.track_stock && <p className="xs ink-muted">ต้องเปิดนับสต็อกของสินค้านี้ก่อน จึงใช้ปุ่มนี้ได้</p>}
                </>
              ) : (
                <>
                  <div className="mh-field"><label className="mh-label" htmlFor="iqty">{hint}</label><input className="mh-input num" id="iqty" inputMode="numeric" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} required /></div>
                  <div className="mh-field"><label className="mh-label" htmlFor="in">หมายเหตุ (ถ้ามี)</label><input className="mh-input" id="in" maxLength={200} value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} placeholder="เช่น ล็อตเช้า" /></div>
                  <ErrorNotice error={save.error} />
                  {save.isSuccess && <div className="notice notice--ok" role="status"><p>บันทึกแล้ว</p></div>}
                  <button className="mh-btn mh-btn--primary" type="submit" disabled={save.isPending}>{save.isPending ? "กำลังบันทึก…" : "บันทึก"}</button>
                  <p className="xs ink-muted">ลดต่ำกว่าจำนวนที่จองไว้ไม่ได้ ระบบจะบอกให้ยกเลิกหรือย้ายคำสั่งซื้อก่อน</p>
                </>
              )}
            </form>
          ) : <div className="apanel"><p className="ink-muted">เลือก “ปรับสต็อก” ที่สินค้าในตารางเพื่อรับของเข้า นับสต็อก โอนระหว่างสาขา หรือตั้งโควตาออนไลน์ หรือกด “นำเข้าสต็อกจากไฟล์ CSV” เพื่อใส่ยอดยกมาทีเดียวหลายรายการ</p></div>}

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


type Preview = NonNullable<Awaited<ReturnType<typeof previewCsv>>>;
async function previewCsv(csv: string) {
  return unwrap(await api.POST("/api/admin/inventory/import/preview", { body: { csv } }));
}

/** Opening stock from a CSV: download the template, fill it in, check it, then apply. Nothing is written until "ยืนยัน". */
function ImportPanel({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const [text, setText] = useState<string | null>(null);
  const [fileName, setFileName] = useState("");
  const [result, setResult] = useState<{ rows: number; changed: number } | null>(null);

  const preview = useMutation({ mutationFn: (csv: string) => previewCsv(csv) });
  const apply = useMutation({
    mutationFn: async () => unwrap(await api.POST("/api/admin/inventory/import/apply", { body: { csv: text! } })),
    onSuccess: (r) => { setResult(r); onDone(); },
  });
  const download = useMutation({
    mutationFn: async () => {
      const t = unwrap(await api.GET("/api/admin/inventory/import/template"));
      const url = URL.createObjectURL(new Blob([t.csv], { type: "text/csv;charset=utf-8" }));
      const a = document.createElement("a");
      a.href = url; a.download = t.filename; a.click();
      URL.revokeObjectURL(url);
    },
  });

  const onFile = async (file: File | undefined) => {
    setResult(null); apply.reset();
    if (!file) return;
    const csv = await file.text();
    setText(csv); setFileName(file.name);
    preview.mutate(csv);
  };
  const p: Preview | undefined = preview.data;
  const shown = p ? [...p.rows.filter((r) => r.errors.length), ...p.rows.filter((r) => !r.errors.length)].slice(0, 200) : [];

  return (
    <section className="apanel">
      <div className="apanel-head"><h2>นำเข้าสต็อกจากไฟล์ CSV</h2><button type="button" className="mh-btn mh-btn--secondary mh-btn--sm" onClick={onClose}>ปิด</button></div>
      <ol className="sm" style={{ paddingLeft: 20, display: "grid", gap: 4 }}>
        <li>ดาวน์โหลดไฟล์ตัวอย่าง (มีทุกสินค้าและทุกสาขา พร้อมตัวเลขปัจจุบัน)</li>
        <li>เปิดด้วย Excel แล้วกรอก <code>tracking</code> เป็น <code>stock</code> (นับสต็อก) หรือ <code>none</code> (ไม่นับ), จำนวน <code>on_hand</code>, โควตาออนไลน์ และจุดเตือน (เว้นว่างได้)</li>
        <li>เลือกไฟล์กลับเข้ามา ระบบตรวจให้ก่อน ยังไม่บันทึก</li>
        <li>ไม่มีแถวผิดเลย จึงกด “ยืนยัน” ได้</li>
      </ol>
      <div className="mh-row" style={{ gap: 8 }}>
        <button type="button" className="mh-btn mh-btn--secondary mh-btn--sm" disabled={download.isPending} onClick={() => download.mutate()}>ดาวน์โหลดไฟล์ตัวอย่าง</button>
        <label className="mh-btn mh-btn--secondary mh-btn--sm" style={{ cursor: "pointer" }}>
          เลือกไฟล์ CSV
          <input type="file" accept=".csv,text/csv" style={{ display: "none" }} onChange={(e) => { void onFile(e.target.files?.[0]); e.target.value = ""; }} />
        </label>
        {fileName && <span className="xs ink-muted">{fileName}</span>}
      </div>
      <ErrorNotice error={download.error ?? preview.error ?? apply.error} />
      {preview.isPending && <p className="ink-muted">กำลังตรวจไฟล์…</p>}
      {p && !result && (
        <>
          <div className={`notice ${p.error_count ? "notice--warn" : "notice--ok"}`} role="status">
            <p>{p.total} แถว · ถูกต้อง {p.ok_count} · ผิด {p.error_count}{p.error_count ? " (แก้ไฟล์แล้วเลือกใหม่)" : ""}</p>
          </div>
          <div className="mh-tablewrap" style={{ maxHeight: 360, overflowY: "auto" }}>
            <table className="mh-table">
              <thead><tr><th>แถว</th><th>สินค้า</th><th>สาขา</th><th>นับ</th><th className="r">มีอยู่</th><th className="r">เปลี่ยน</th><th>ปัญหา</th></tr></thead>
              <tbody>
                {shown.map((r) => (
                  <tr key={r.line} className={r.errors.length ? "sel" : ""}>
                    <td className="num">{r.line}</td>
                    <td className="wrap"><span className="bold">{r.product_name || "—"}</span><br /><span className="xs ink-muted">{r.variant_label} {r.sku}</span></td>
                    <td>{r.branch_code}</td><td>{r.tracking}</td>
                    <td className="r">{r.on_hand ?? "—"}</td>
                    <td className="r">{r.delta == null ? "—" : r.delta > 0 ? `+${r.delta}` : r.delta}</td>
                    <td className="wrap" style={{ minWidth: 180 }}>{r.errors.length ? r.errors.join(" · ") : <span className="ink-muted">ถูกต้อง</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {p.rows.length > shown.length && <p className="xs ink-muted">แสดง {shown.length} จาก {p.rows.length} แถว (แถวที่ผิดอยู่ก่อน)</p>}
          <button type="button" className="mh-btn mh-btn--primary" disabled={apply.isPending || p.error_count > 0 || p.total === 0} onClick={() => apply.mutate()}>
            {apply.isPending ? "กำลังบันทึก…" : "ยืนยันนำเข้า"}
          </button>
        </>
      )}
      {result && <div className="notice notice--ok" role="status"><p>นำเข้าแล้ว {result.rows} แถว มีการเปลี่ยนแปลง {result.changed} รายการ ดูได้ในประวัติด้านล่าง</p></div>}
    </section>
  );
}
