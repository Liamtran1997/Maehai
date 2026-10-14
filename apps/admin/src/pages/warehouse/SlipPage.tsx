import { formatThaiDate } from "@maehai/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import { ErrorNotice } from "../../components/Notice";
import { api, unwrap } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { REFUSE, useBranches, type DocLine, type FullDoc } from "./shared";

/** One slip (IN-, TR-, RT-): its lines, the counting a branch or the central warehouse does, and the steps it has passed. */
export function SlipPage() {
  const { number = "" } = useParams();
  const qc = useQueryClient();
  const { can, user } = useAuth();
  const branches = useBranches();
  const detail = useQuery({
    queryKey: ["document", number],
    queryFn: async () => unwrap(await api.GET("/api/admin/inventory/documents/{number}", { params: { path: { number } } })),
  });
  const refresh = () => { for (const k of ["documents", "document", "stock", "materials", "report", "summary", "todo"]) void qc.invalidateQueries({ queryKey: [k] }); };
  const doc = detail.data;
  if (detail.error) return <div className="notice notice--warn" role="alert"><p>ไม่พบเอกสารนี้ หรือไม่มีสิทธิ์ดูสาขานี้</p></div>;
  if (!doc) return <p className="ink-muted">กำลังโหลด…</p>;
  const receiving = doc.kind === "transfer" && doc.status === "sent" && can("inventory.receive_transfer");
  const returning = doc.kind === "return" && doc.status === "sent_back" && can("inventory.receive_return");
  const aside = (
    <aside className="slip-aside">
      <section className="panel" aria-labelledby="info-h">
        <h2 id="info-h">ข้อมูลใบ</h2>
        <dl className="kv">
          {doc.from_branch && <><dt>จาก</dt><dd>{doc.from_branch}</dd></>}
          {doc.to_branch && <><dt>ไป</dt><dd><b>{doc.to_branch}</b></dd></>}
          {doc.source && <><dt>แหล่ง</dt><dd>{doc.source}</dd></>}
          {doc.vehicle && <><dt>รถ</dt><dd>{doc.vehicle}</dd></>}
          {doc.carrier && <><dt>ผู้นำส่ง</dt><dd>{doc.carrier}</dd></>}
          {doc.origin && <><dt>ของใบ</dt><dd className="mh-code">{doc.origin}</dd></>}
          <dt>สร้างโดย</dt><dd>{doc.created_by}</dd>
          <dt>หมายเหตุ</dt><dd className="muted">{doc.note || "—"}</dd>
        </dl>
      </section>
      <section className="panel" aria-labelledby="hist-h">
        <h2 id="hist-h">ความเคลื่อนไหว</h2>
        <ol style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 12, fontSize: 14 }}>
          <li><b>สร้างใบ</b><br /><span className="small muted">{formatThaiDate(doc.created_at)} · {doc.created_by}</span></li>
          {doc.sent_at && <li><b>ส่งออก</b><br /><span className="small muted">{formatThaiDate(doc.sent_at)}</span></li>}
          {doc.closed_at && <li><b>{doc.status === "cancelled" ? "ยกเลิก" : "ปิดใบ"}</b><br /><span className="small muted">{formatThaiDate(doc.closed_at)} · {doc.closed_by}</span>{doc.substitute_reason && <><br /><span className="small">รับแทนสาขา: {doc.substitute_reason}</span></>}</li>}
          {doc.cancel_reason && <li><span className="small">เหตุผลที่ยกเลิก: {doc.cancel_reason}</span></li>}
        </ol>
      </section>
      {doc.kind === "transfer" && doc.status === "sent" && can("inventory.transfer") && <CancelSlip number={doc.number} onDone={refresh} />}
    </aside>
  );
  return (
    <div className={receiving ? "slip-receiving" : undefined}>
      <Link className="slip-back" to="/warehouse?tab=docs">‹ เอกสาร</Link>
      <nav className="crumbs" aria-label="ตำแหน่ง"><Link to="/warehouse?tab=docs">คลังสินค้า</Link><span aria-hidden="true">›</span><Link to="/warehouse?tab=docs">เอกสาร</Link><span aria-hidden="true">›</span><span>{doc.number}</span></nav>
      <div className="page-head">
        <div>
          <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 12 }}>
            <h1>{doc.kind_label} <span className="mh-code" style={{ fontSize: 22 }}>{doc.number}</span></h1>
            <span className={`mh-status ${statusTone(doc.status)}`} data-glyph={statusGlyph(doc.status)}>{doc.status_label}</span>
          </div>
          <p>{routeLine(doc)}</p>
        </div>
        <div className="actions">
          {doc.kind === "transfer" && <button type="button" className="mh-btn mh-btn--secondary mh-btn--sm" onClick={() => window.print()}>พิมพ์ใบส่งสินค้า</button>}
        </div>
      </div>

      <Steps doc={doc} />

      {receiving
        ? <ReceiveSlip doc={doc} toName={branches.data?.find((b) => b.code === doc.to_branch)?.name ?? doc.to_branch ?? ""} isSubstitute={user?.role !== "branch_manager"} onDone={refresh} aside={aside} />
        : returning
          ? <ReceiveReturnSlip doc={doc} onDone={refresh} aside={aside} />
          : (
            <div className="slip-grid">
              <section className="panel" aria-labelledby="lines-h">
                <div className="panel-head"><h2 id="lines-h">รายการ</h2><span className="small muted">{doc.lines.length} รายการ</span></div>
                <ReadOnlyLines lines={doc.lines} />
              </section>
              {aside}
            </div>
          )}
      {doc.kind === "transfer" && <PrintSlip doc={doc} />}
    </div>
  );
}

function statusTone(status: string) {
  if (status === "received_full" || status === "posted" || status === "closed") return "mh-status--done";
  if (status === "cancelled" || status === "received_none") return "mh-status--cancel";
  if (status === "sent" || status === "sent_back" || status === "pending_approval" || status === "counting" || status === "received_partial") return "mh-status--wait";
  return "mh-status--paid";
}

function statusGlyph(status: string) {
  if (status === "received_full" || status === "posted" || status === "closed") return "✓";
  if (status === "cancelled" || status === "received_none") return "✕";
  return "○";
}

function routeLine(doc: FullDoc) {
  if (doc.kind === "receipt") return `แหล่ง ${doc.source ?? "—"} → ${doc.to_branch ?? "คลังกลาง"}`;
  if (doc.kind === "transfer") return `${doc.from_branch ?? "—"} → ${doc.to_branch ?? "—"} · ส่งเมื่อ ${doc.sent_at ? formatThaiDate(doc.sent_at) : "—"}`;
  return `${doc.from_branch ?? "—"} → ${doc.to_branch ?? "—"}`;
}

/** The path a slip has travelled, with the step it is on now highlighted. */
function Steps({ doc }: { doc: FullDoc }) {
  const steps: { label: string; state: "done" | "now" | "todo" }[] =
    doc.kind === "transfer"
      ? [{ label: "ส่งออกจากคลังกลาง", state: "done" }, { label: "สาขาตรวจรับ", state: doc.status === "sent" ? "now" : "done" }, { label: "ปิดใบ", state: doc.status === "sent" ? "todo" : "done" }]
      : doc.kind === "return"
        ? [{ label: "สาขาส่งคืน", state: "done" }, { label: "คลังกลางรับคืน", state: doc.status === "sent_back" ? "now" : "done" }]
        : [{ label: "บันทึกใบ", state: "done" }];
  if (doc.status === "cancelled") return <div className="slip-steps"><span className="slip-step slip-step--now"><i>✕</i>ยกเลิกแล้ว</span></div>;
  return (
    <div className="slip-steps" aria-label="ขั้นตอน">
      {steps.map((s, i) => (
        <span key={s.label} style={{ display: "contents" }}>
          {i > 0 && <span className="slip-step-line" aria-hidden="true" />}
          <span className={`slip-step ${s.state === "done" ? "slip-step--done" : s.state === "now" ? "slip-step--now" : ""}`}>
            <i>{s.state === "done" ? "✓" : i + 1}</i>{s.label}
          </span>
        </span>
      ))}
    </div>
  );
}

function ReadOnlyLines({ lines }: { lines: DocLine[] }) {
  return (
    <div className="mh-tablewrap" style={{ border: 0 }}>
      <table className="mh-table">
        <thead><tr><th>รายการ</th><th className="r">ส่ง</th><th className="r">รับ</th><th className="r">คืน</th><th className="r">หาย</th></tr></thead>
        <tbody>
          {lines.map((l) => (
            <tr key={l.id}>
              <td className="wrap">{l.name}{l.refuse_reason && <><br /><span className="xs ink-muted">{REFUSE.find((r) => r.v === l.refuse_reason)?.l ?? l.refuse_reason}{l.refuse_note ? ` · ${l.refuse_note}` : ""}</span></>}</td>
              <td className="r">{Number(l.sent)} {l.unit}</td>
              <td className="r">{l.received === null ? "—" : Number(l.received)}</td>
              <td className="r">{Number(l.refused) > 0 ? Number(l.refused) : "—"}</td>
              <td className="r">{Number(l.missing) > 0 ? Number(l.missing) : "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Counter for a quantity: the − and + buttons are large enough for a thumb. */
function Qty({ value, onChange, label, max }: { value: string; onChange: (v: string) => void; label: string; max: number }) {
  const n = Number(value) || 0;
  const step = (d: number) => onChange(String(Math.min(max, Math.max(0, n + d))));
  return (
    <span className="qty">
      <button type="button" aria-label={`ลด ${label}`} onClick={() => step(-1)}>−</button>
      <input aria-label={`จำนวนที่รับ ${label}`} inputMode="decimal" value={value} onChange={(e) => onChange(e.target.value)} />
      <button type="button" aria-label={`เพิ่ม ${label}`} onClick={() => step(1)}>+</button>
    </span>
  );
}

/** Receiving a transfer. The form sits in the lines card; the confirm bar sits at the bottom of the page. */
function ReceiveSlip({ doc, toName, isSubstitute, onDone, aside }: { doc: FullDoc; toName: string; isSubstitute: boolean; onDone: () => void; aside: ReactNode }) {
  const [rows, setRows] = useState(() => doc.lines.map((l) => ({ line_id: l.id, received: String(Number(l.sent)), reason: "", note: "", sent: l.sent, name: l.name, unit: l.unit })));
  const [substitute, setSubstitute] = useState("");
  const shortTotal = rows.reduce((t, r) => t + Math.max(0, Number(r.sent) - Number(r.received)), 0);
  const confirm = useMutation({
    mutationFn: async () => unwrap(await api.POST("/api/admin/inventory/documents/{number}/receive", {
      params: { path: { number: doc.number } },
      body: {
        lines: rows.map((r) => ({ line_id: r.line_id, received: r.received.trim(), reason: Number(r.received) < Number(r.sent) ? r.reason : "", note: r.note })),
        substitute_reason: isSubstitute ? substitute : "",
      },
    })),
    onSuccess: onDone,
  });
  const set = (i: number, patch: Partial<(typeof rows)[number]>) => setRows(rows.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  return (
    <>
      <div className="slip-grid">
        <section className="panel" aria-labelledby="lines-h">
          <div className="panel-head"><h2 id="lines-h">รายการ</h2><span className="small muted">{doc.lines.length} รายการ</span></div>
          <form id="receive-form" onSubmit={(e) => { e.preventDefault(); confirm.mutate(); }} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <p className="small" style={{ margin: 0 }}>รับที่ <b>{toName}</b></p>
            <p className="small muted" style={{ margin: 0 }}>นับของที่มาถึงจริง ถ้าไม่ครบให้เลือกเหตุผล ของที่ชำรุดหรือไม่ตรงจะกลับคลังกลาง ของที่หายระหว่างทางจะไม่กลับ</p>
            {rows.map((r, i) => {
              const short = Number(r.received) < Number(r.sent);
              return (
                <div key={r.line_id} style={{ display: "grid", gap: 8, paddingBottom: 12, borderBottom: "1px solid var(--line)" }}>
                  <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 12 }}>
                    <b style={{ flex: "1 1 200px" }}>{r.name}</b>
                    <span className="small muted">ส่ง {Number(r.sent)} {r.unit}</span>
                    <Qty value={r.received} onChange={(v) => set(i, { received: v })} label={r.name} max={Number(r.sent)} />
                  </div>
                  {short && (
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
                      <div className="mh-chips" role="group" aria-label={`เหตุผลที่ไม่ครบ ${r.name}`}>
                        {REFUSE.map((o) => (
                          <button key={o.v} type="button" className="mh-chip" aria-pressed={r.reason === o.v} style={{ minHeight: 40 }} onClick={() => set(i, { reason: o.v })}>{o.l}</button>
                        ))}
                      </div>
                      {r.reason && r.reason !== "missing" && (
                        <input className="mh-input" aria-label={`รายละเอียด ${r.name}`} placeholder={r.reason === "other" ? "ต้องพิมพ์รายละเอียด" : "รายละเอียด (ถ้ามี)"} style={{ flex: "1 1 220px" }} value={r.note} onChange={(e) => set(i, { note: e.target.value })} />
                      )}
                    </div>
                  )}
                </div>
              );
            })}
            {isSubstitute && (
              <div className="mh-field"><label className="mh-label" htmlFor="sub">รับแทนผู้จัดการสาขา: เหตุผล</label>
                <input className="mh-input" id="sub" value={substitute} onChange={(e) => setSubstitute(e.target.value)} placeholder="เช่น ผู้จัดการสาขาไม่อยู่" />
              </div>
            )}
            <ErrorNotice error={confirm.error} />
          </form>
        </section>
        {aside}
      </div>
      <div className="action-bar">
        <span className="grow">{shortTotal > 0 ? <><b style={{ color: "var(--ink)" }}>ไม่ครบ {shortTotal} ชิ้น</b> · จะมีใบคืนสินค้าสำหรับส่วนที่ไม่รับ</> : <>รับครบทุกรายการ</>}</span>
        <button form="receive-form" className="mh-btn mh-btn--primary" type="submit" disabled={confirm.isPending}>{confirm.isPending ? "กำลังบันทึก…" : "ยืนยันรับของ"}</button>
      </div>
    </>
  );
}

/** Receiving a store return at the central warehouse. Same layout as ReceiveSlip: form in the card, confirm bar at the page bottom. */
function ReceiveReturnSlip({ doc, onDone, aside }: { doc: FullDoc; onDone: () => void; aside: ReactNode }) {
  const [rows, setRows] = useState(() => doc.lines.map((l) => ({ line_id: l.id, restock: String(Number(l.sent)), discard: "0", sent: l.sent, name: l.name, unit: l.unit })));
  const confirm = useMutation({
    mutationFn: async () => unwrap(await api.POST("/api/admin/inventory/documents/{number}/receive-return", {
      params: { path: { number: doc.number } },
      body: { lines: rows.map((r) => ({ line_id: r.line_id, restock: r.restock.trim(), discard: r.discard.trim() })) },
    })),
    onSuccess: onDone,
  });
  return (
    <>
      <div className="slip-grid">
        <section className="panel" aria-labelledby="lines-h">
          <div className="panel-head"><h2 id="lines-h">รายการ</h2><span className="small muted">{doc.lines.length} รายการ</span></div>
          <form id="receive-form" onSubmit={(e) => { e.preventDefault(); confirm.mutate(); }} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <p className="small muted" style={{ margin: 0 }}>เข้าสต็อก = ยังขายได้ · ทิ้ง = เสียหายไม่กลับเข้าสต็อก · ส่วนที่นับไม่ครบจะถือว่าหาย</p>
            {rows.map((r, i) => (
              <div key={r.line_id} style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 12, paddingBottom: 12, borderBottom: "1px solid var(--line)" }}>
                <b style={{ flex: "1 1 200px" }}>{r.name}</b>
                <span className="small muted">ส่งคืน {Number(r.sent)} {r.unit}</span>
                <label className="small">เข้าสต็อก <input className="mh-input num" aria-label={`เข้าสต็อก ${r.name}`} style={{ width: 90 }} value={r.restock}
                  onChange={(e) => setRows(rows.map((x, j) => (j === i ? { ...x, restock: e.target.value } : x)))} /></label>
                <label className="small">ทิ้ง <input className="mh-input num" aria-label={`ทิ้ง ${r.name}`} style={{ width: 90 }} value={r.discard}
                  onChange={(e) => setRows(rows.map((x, j) => (j === i ? { ...x, discard: e.target.value } : x)))} /></label>
              </div>
            ))}
            <ErrorNotice error={confirm.error} />
          </form>
        </section>
        {aside}
      </div>
      <div className="action-bar">
        <span className="grow">รับคืนเข้าคลังกลาง</span>
        <button form="receive-form" className="mh-btn mh-btn--primary" type="submit" disabled={confirm.isPending}>{confirm.isPending ? "กำลังบันทึก…" : "ยืนยันรับคืน"}</button>
      </div>
    </>
  );
}

function CancelSlip({ number, onDone }: { number: string; onDone: () => void }) {
  const [reason, setReason] = useState("");
  const cancel = useMutation({
    mutationFn: async () => unwrap(await api.POST("/api/admin/inventory/documents/{number}/cancel", { params: { path: { number } }, body: { reason } })),
    onSuccess: onDone,
  });
  return (
    <form className="panel" onSubmit={(e) => { e.preventDefault(); cancel.mutate(); }}>
      <h2>ยกเลิกใบส่ง</h2>
      <p className="small muted" style={{ margin: 0 }}>ของจะกลับเข้าคลังกลาง ทำได้เฉพาะก่อนสาขารับ</p>
      <div className="mh-field"><label className="mh-label" htmlFor="cr">เหตุผล</label><input className="mh-input" id="cr" value={reason} onChange={(e) => setReason(e.target.value)} required /></div>
      <ErrorNotice error={cancel.error} />
      <button className="mh-btn mh-btn--secondary mh-btn--sm" type="submit" disabled={cancel.isPending || !reason.trim()} style={{ color: "var(--danger)" }}>ยกเลิกใบส่ง</button>
    </form>
  );
}

/** Shown only when printing: a transfer slip with the number, place, vehicle, lines and signature boxes. */
export function PrintSlip({ doc }: { doc: FullDoc }) {
  const branches = useBranches();
  const nameOf = (code: string | null | undefined) => branches.data?.find((b) => b.code === code)?.name ?? code ?? "—";
  return (
    <div className="print-slip" aria-hidden="true">
      <style>{`
        .print-slip { display: none; }
        @media print {
          html, body { background: #fff !important; }
          body * { visibility: hidden; }
          .print-slip, .print-slip * { visibility: visible; }
          .print-slip { display: block; position: absolute; left: 0; top: 0; width: 100%; padding: 16mm; font-size: 12pt; color: #000; background: #fff; }
          .print-slip table { width: 100%; border-collapse: collapse; margin-top: 8mm; }
          .print-slip th, .print-slip td { border: 1px solid #000; padding: 4px 6px; text-align: left; }
          .print-slip .sign { display: flex; justify-content: space-between; margin-top: 18mm; }
          .print-slip .sign div { width: 40%; border-top: 1px solid #000; padding-top: 4px; text-align: center; }
        }
      `}</style>
      <h2 style={{ margin: 0 }}>ใบส่งสินค้า {doc.number}</h2>
      <p>จาก: {nameOf(doc.from_branch)} &nbsp;→&nbsp; ไป: <b>{nameOf(doc.to_branch)}</b></p>
      <p>รถที่ใช้ส่ง: {doc.vehicle} {doc.carrier && <>· ผู้นำส่ง: {doc.carrier}</>}</p>
      <p>วันที่ส่ง: {doc.sent_at ? formatThaiDate(doc.sent_at) : "—"}</p>
      <table>
        <thead><tr><th>#</th><th>รายการ</th><th>จำนวน</th></tr></thead>
        <tbody>{doc.lines.map((l, i) => <tr key={l.id}><td>{i + 1}</td><td>{l.name}</td><td>{String(Number(l.sent))} {l.unit}</td></tr>)}</tbody>
      </table>
      {doc.note && <p>หมายเหตุ: {doc.note}</p>}
      <div className="sign"><div>ผู้ส่ง</div><div>ผู้รับ (ตรวจนับแล้ว)</div></div>
    </div>
  );
}
