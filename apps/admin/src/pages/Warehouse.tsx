import { formatThaiDate } from "@maehai/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { ErrorNotice } from "../components/Notice";
import { api, unwrap } from "../lib/api";
import { useAuth } from "../lib/auth";

type Tab = "docs" | "receipt" | "transfer" | "return" | "counts" | "dayclose" | "materials" | "sources" | "places" | "report";

const TABS: { key: Tab; label: string; perm: string }[] = [
  { key: "docs", label: "เอกสาร", perm: "inventory.view" },
  { key: "receipt", label: "รับของเข้าคลังกลาง", perm: "inventory.receive" },
  { key: "transfer", label: "ส่งไปสาขา", perm: "inventory.transfer" },
  { key: "return", label: "สาขาส่งคืนคลัง", perm: "inventory.adjust" },
  { key: "counts", label: "นับสต็อก", perm: "inventory.adjust" },
  { key: "dayclose", label: "ปิดยอดหน้าร้าน", perm: "inventory.adjust" },
  { key: "materials", label: "วัตถุดิบและวัสดุ", perm: "inventory.view" },
  { key: "sources", label: "แหล่งสินค้า", perm: "inventory.receive" },
  { key: "places", label: "สาขาและกลุ่ม LINE", perm: "inventory.approve" },
  { key: "report", label: "รายงานคลัง", perm: "inventory.view" },
];

const REFUSE = [
  { v: "damaged", l: "ชำรุด" },
  { v: "wrong", l: "ไม่ตรงรายการ" },
  { v: "other", l: "อื่นๆ" },
  { v: "missing", l: "ขาด (หายระหว่างทาง)" },
];

const today = () => new Date().toISOString().slice(0, 10);

type StockRow = { sku: string; product_name: string; variant_label: string; track_stock: boolean };
type MatRow = { code: string; name: string; kind: string; kind_label: string; unit: string; low_stock_threshold: string | null; note: string; is_active: boolean; in_use: boolean };
type Line = { item: string; quantity: string; cost: string };

export function Warehouse() {
  const { can } = useAuth();
  const visible = TABS.filter((t) => can(t.perm));
  const [tab, setTab] = useState<Tab>(visible[0]?.key ?? "docs");
  return (
    <>
      <div className="topbar"><h1>คลังสินค้า</h1></div>
      <p className="sm ink-muted">คลังกลาง (สาขาศรีณรงค์) รับของจากแหล่งสินค้า แล้วส่งไปสาขาด้วยใบส่งสินค้า สาขาต้องตรวจรับ ของที่ไม่รับกลับคลังกลางด้วยใบคืนสินค้า</p>
      <div className="seg" role="tablist" aria-label="หมวดคลัง" style={{ flexWrap: "wrap" }}>
        {visible.map((t) => (
          <button key={t.key} type="button" role="tab" aria-selected={tab === t.key} aria-pressed={tab === t.key} onClick={() => setTab(t.key)}>{t.label}</button>
        ))}
      </div>
      {tab === "docs" && <DocumentsTab />}
      {tab === "receipt" && <ReceiptTab />}
      {tab === "transfer" && <TransferTab />}
      {tab === "return" && <StoreReturnTab />}
      {tab === "counts" && <CountsTab />}
      {tab === "dayclose" && <DayCloseTab />}
      {tab === "materials" && <MaterialsTab />}
      {tab === "sources" && <SourcesTab />}
      {tab === "places" && <PlacesTab />}
      {tab === "report" && <ReportTab />}
    </>
  );
}

// ---------------------------------------------------------------- shared queries

function useBranches() {
  return useQuery({ queryKey: ["branches"], queryFn: async () => unwrap(await api.GET("/api/admin/inventory/branches")) });
}
function useStockItems() {
  return useQuery({ queryKey: ["stock", ""], queryFn: async () => unwrap(await api.GET("/api/admin/inventory/stock", { params: { query: {} } })) });
}
function useMaterials() {
  return useQuery({ queryKey: ["materials"], queryFn: async () => unwrap(await api.GET("/api/admin/inventory/materials", { params: { query: {} } })) });
}
function useSources() {
  return useQuery({ queryKey: ["sources"], queryFn: async () => unwrap(await api.GET("/api/admin/inventory/sources", { params: { query: { include_hidden: true } } })) });
}

/** Lines of a slip: a tracked size or a material, a quantity, and (receipts only) a unit cost. */
function LineBuilder({ lines, onChange, items, withCost }: {
  lines: Line[]; onChange: (l: Line[]) => void; items: { value: string; label: string }[]; withCost?: boolean;
}) {
  const set = (i: number, patch: Partial<Line>) => onChange(lines.map((l, j) => (j === i ? { ...l, ...patch } : l)));
  return (
    <div style={{ display: "grid", gap: 8 }}>
      {lines.map((l, i) => (
        <div key={i} className="mh-row" style={{ gap: 8, flexWrap: "nowrap" }}>
          <select className="mh-select" aria-label={`รายการที่ ${i + 1}`} style={{ flex: 1, minWidth: 0 }} value={l.item} onChange={(e) => set(i, { item: e.target.value })}>
            <option value="">— เลือกรายการ —</option>
            {items.map((it) => <option key={it.value} value={it.value}>{it.label}</option>)}
          </select>
          <input className="mh-input num" aria-label={`จำนวนที่ ${i + 1}`} inputMode="decimal" placeholder="จำนวน" style={{ width: 110 }} value={l.quantity} onChange={(e) => set(i, { quantity: e.target.value })} />
          {withCost && <input className="mh-input num" aria-label={`ราคาต่อหน่วย (สตางค์) ${i + 1}`} inputMode="numeric" placeholder="ราคา/หน่วย" style={{ width: 120 }} value={l.cost} onChange={(e) => set(i, { cost: e.target.value })} />}
          <button type="button" className="mh-btn mh-btn--secondary mh-btn--sm" onClick={() => onChange(lines.filter((_, j) => j !== i))}>ลบ</button>
        </div>
      ))}
      <button type="button" className="mh-btn mh-btn--secondary mh-btn--sm" style={{ justifySelf: "start" }} onClick={() => onChange([...lines, { item: "", quantity: "", cost: "" }])}>+ เพิ่มรายการ</button>
    </div>
  );
}

/** Turn the builder's lines into the API shape. Sizes are sent by SKU, materials by code. */
function toApiLines(lines: Line[], withCost: boolean) {
  return lines.filter((l) => l.item).map((l) => {
    const [kind, key] = [l.item.slice(0, 2), l.item.slice(2)];
    return {
      sku: kind === "p:" ? key : null,
      material_code: kind === "m:" ? key : null,
      quantity: l.quantity.trim(),
      unit_cost_satang: withCost && l.cost.trim() ? Number(l.cost) : null,
    };
  });
}

function itemOptions(stock: StockRow[] | undefined, mats: MatRow[] | undefined) {
  return [
    ...(stock ?? []).filter((r) => r.track_stock).map((r) => ({ value: `p:${r.sku}`, label: `${r.product_name} (${r.variant_label})` })),
    ...(mats ?? []).map((m) => ({ value: `m:${m.code}`, label: `${m.name} · ${m.unit}` })),
  ];
}

function Created({ number }: { number: string | null }) {
  if (!number) return null;
  return <div className="notice notice--ok" role="status"><p>บันทึกแล้ว เลขที่ {number}</p></div>;
}

// ---------------------------------------------------------------- documents

function DocumentsTab() {
  const qc = useQueryClient();
  const { can, user } = useAuth();
  const [kind, setKind] = useState("");
  const [status, setStatus] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const docs = useQuery({
    queryKey: ["documents", kind, status],
    queryFn: async () => unwrap(await api.GET("/api/admin/inventory/documents", { params: { query: { kind: kind || undefined, status: status || undefined, limit: 100 } } })),
  });
  const detail = useQuery({
    queryKey: ["document", selected],
    enabled: !!selected,
    queryFn: async () => unwrap(await api.GET("/api/admin/inventory/documents/{number}", { params: { path: { number: selected! } } })),
  });
  const refresh = () => { for (const k of ["documents", "document", "stock", "materials", "report", "summary", "todo"]) void qc.invalidateQueries({ queryKey: [k] }); };

  return (
    <div className="cols cols--2-1" style={{ alignItems: "start" }}>
      <div style={{ display: "grid", gap: 12, minWidth: 0 }}>
        <div className="toolbar">
          <select className="mh-select" aria-label="ประเภทเอกสาร" style={{ width: "auto" }} value={kind} onChange={(e) => setKind(e.target.value)}>
            <option value="">ทุกประเภท</option><option value="receipt">ใบรับสินค้า (IN)</option><option value="transfer">ใบส่งสินค้า (TR)</option><option value="return">ใบคืนสินค้า (RT)</option>
          </select>
          <select className="mh-select" aria-label="สถานะ" style={{ width: "auto" }} value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">ทุกสถานะ</option><option value="sent">กำลังส่ง / รอรับ</option><option value="sent_back">กำลังส่งคืน</option>
            <option value="received_full">รับครบ</option><option value="received_partial">รับบางส่วน</option><option value="received_none">ไม่รับทั้งหมด</option>
            <option value="cancelled">ยกเลิก</option><option value="closed">รับคืนแล้ว</option><option value="posted">บันทึกแล้ว</option>
          </select>
        </div>
        <ErrorNotice error={docs.error} />
        <div className="mh-tablewrap">
          <table className="mh-table">
            <thead><tr><th>เลขที่</th><th>ประเภท</th><th>จาก → ไป</th><th>สถานะ</th><th>วันที่</th></tr></thead>
            <tbody>
              {docs.data?.map((d) => (
                <tr key={d.number} className={d.number === selected ? "sel" : ""} onClick={() => setSelected(d.number)} style={{ cursor: "pointer" }}>
                  <td><span className="mh-code">{d.number}</span>{d.overdue && <span className="mh-status mh-status--wait" data-glyph="!">ค้างเกิน 24 ชม.</span>}</td>
                  <td>{d.kind_label}</td>
                  <td className="wrap">{d.from_branch ?? d.source ?? "—"} → {d.to_branch ?? "—"}</td>
                  <td className="wrap">{d.status_label}</td>
                  <td className="xs">{formatThaiDate(d.created_at)}</td>
                </tr>
              ))}
              {docs.data?.length === 0 && <tr><td colSpan={5} className="ink-muted">ยังไม่มีเอกสาร</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
      {detail.data?.kind === "transfer" && <PrintSlip doc={detail.data} />}
      <div style={{ display: "grid", gap: 16, minWidth: 0 }}>
        {detail.data ? (
          <section className="apanel">
            <div className="apanel-head"><h2>{detail.data.number}</h2><button type="button" className="mh-btn mh-btn--secondary mh-btn--sm" onClick={() => setSelected(null)}>ปิด</button></div>
            <p className="sm">{detail.data.kind_label} · <b>{detail.data.status_label}</b></p>
            {detail.data.kind === "transfer" && <button type="button" className="mh-btn mh-btn--secondary mh-btn--sm" onClick={() => window.print()}>พิมพ์ใบส่งสินค้า</button>}
            <p className="xs ink-muted">
              {detail.data.from_branch && <>จาก {detail.data.from_branch} </>}
              {detail.data.to_branch && <>ไป {detail.data.to_branch} </>}
              {detail.data.source && <>· แหล่ง {detail.data.source} </>}
              {detail.data.vehicle && <>· รถ {detail.data.vehicle} </>}
              {detail.data.carrier && <>· ผู้ส่ง {detail.data.carrier} </>}
              {detail.data.origin && <>· ของใบ <span className="mh-code">{detail.data.origin}</span></>}
            </p>
            {detail.data.note && <p className="xs ink-muted">หมายเหตุ: {detail.data.note}</p>}
            {detail.data.cancel_reason && <p className="xs">ยกเลิก: {detail.data.cancel_reason}</p>}
            {detail.data.substitute_reason && <p className="xs">รับแทนสาขา: {detail.data.substitute_reason}</p>}
            <div className="mh-tablewrap" style={{ border: 0 }}>
              <table className="mh-table">
                <thead><tr><th>รายการ</th><th className="r">ส่ง</th><th className="r">รับ</th><th className="r">คืน</th><th className="r">หาย</th></tr></thead>
                <tbody>
                  {detail.data.lines.map((l) => (
                    <tr key={l.id}>
                      <td className="wrap">{l.name}{l.refuse_reason && <><br /><span className="xs ink-muted">{REFUSE.find((r) => r.v === l.refuse_reason)?.l ?? l.refuse_reason}{l.refuse_note ? ` · ${l.refuse_note}` : ""}</span></>}</td>
                      <td className="r">{l.sent} {l.unit}</td>
                      <td className="r">{l.received ?? "—"}</td>
                      <td className="r">{l.refused !== "0" ? l.refused : "—"}</td>
                      <td className="r">{l.missing !== "0" ? l.missing : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {detail.data.kind === "transfer" && detail.data.status === "sent" && can("inventory.receive_transfer") && (
              <ReceiveTransferForm number={detail.data.number} lines={detail.data.lines} isSubstitute={user?.role !== "branch_manager"} onDone={refresh} />
            )}
            {detail.data.kind === "transfer" && detail.data.status === "sent" && can("inventory.transfer") && (
              <CancelTransferForm number={detail.data.number} onDone={refresh} />
            )}
            {detail.data.kind === "return" && detail.data.status === "sent_back" && can("inventory.receive_return") && (
              <ReceiveReturnForm number={detail.data.number} lines={detail.data.lines} onDone={refresh} />
            )}
          </section>
        ) : (
          <div className="apanel"><p className="ink-muted">เลือกเอกสารจากรายการเพื่อดูรายละเอียดและดำเนินการ</p></div>
        )}
      </div>
    </div>
  );
}

type DocLine = { id: number; name: string; unit: string; sent: string; received: string | null; refused: string; missing: string; refuse_reason: string; refuse_note: string };

function ReceiveTransferForm({ number, lines, isSubstitute, onDone }: { number: string; lines: DocLine[]; isSubstitute: boolean; onDone: () => void }) {
  const [rows, setRows] = useState(() => lines.map((l) => ({ line_id: l.id, received: l.sent, reason: "", note: "", sent: l.sent })));
  const [substitute, setSubstitute] = useState("");
  const confirm = useMutation({
    mutationFn: async () => unwrap(await api.POST("/api/admin/inventory/documents/{number}/receive", {
      params: { path: { number } },
      body: {
        lines: rows.map((r) => ({ line_id: r.line_id, received: r.received.trim(), reason: Number(r.received) < Number(r.sent) ? r.reason : "", note: r.note })),
        substitute_reason: isSubstitute ? substitute : "",
      },
    })),
    onSuccess: onDone,
  });
  const onSubmit = (e: FormEvent) => { e.preventDefault(); confirm.mutate(); };
  return (
    <form className="apanel" onSubmit={onSubmit} style={{ marginTop: 12 }}>
      <h2>ตรวจรับของเข้าสาขา</h2>
      <p className="xs ink-muted">นับของที่มาถึงจริง ถ้าไม่ครบ เลือกเหตุผล ของที่ไม่รับจะกลับคลังกลางด้วยใบคืนสินค้า (ขาด = หายระหว่างทาง ไม่กลับ)</p>
      {rows.map((r, i) => {
        const short = Number(r.received) < Number(r.sent);
        return (
          <div key={r.line_id} className="mh-row" style={{ gap: 8, flexWrap: "wrap" }}>
            <span className="bold" style={{ minWidth: 140 }}>{lines[i].name}</span>
            <span className="xs ink-muted">ส่ง {r.sent}</span>
            <input className="mh-input num" aria-label={`รับ ${lines[i].name}`} inputMode="decimal" style={{ width: 90 }} value={r.received}
              onChange={(e) => setRows(rows.map((x, j) => (j === i ? { ...x, received: e.target.value } : x)))} />
            {short && (
              <select className="mh-select" aria-label={`เหตุผล ${lines[i].name}`} style={{ width: "auto" }} value={r.reason}
                onChange={(e) => setRows(rows.map((x, j) => (j === i ? { ...x, reason: e.target.value } : x)))}>
                <option value="">— เลือกเหตุผล —</option>
                {REFUSE.map((o) => <option key={o.v} value={o.v}>{o.l}</option>)}
              </select>
            )}
            {short && r.reason && r.reason !== "missing" && (
              <input className="mh-input" aria-label={`รายละเอียด ${lines[i].name}`} placeholder={r.reason === "other" ? "ต้องพิมพ์รายละเอียด" : "รายละเอียด (ถ้ามี)"} style={{ flex: 1, minWidth: 160 }}
                value={r.note} onChange={(e) => setRows(rows.map((x, j) => (j === i ? { ...x, note: e.target.value } : x)))} />
            )}
          </div>
        );
      })}
      {isSubstitute && (
        <div className="mh-field"><label className="mh-label" htmlFor="sub">เหตุผลที่รับแทนผู้จัดการสาขา</label>
          <input className="mh-input" id="sub" value={substitute} onChange={(e) => setSubstitute(e.target.value)} placeholder="เช่น ผู้จัดการสาขาไม่อยู่" />
        </div>
      )}
      <ErrorNotice error={confirm.error} />
      <button className="mh-btn mh-btn--primary" type="submit" disabled={confirm.isPending}>{confirm.isPending ? "กำลังบันทึก…" : "ยืนยันรับของ"}</button>
    </form>
  );
}

function CancelTransferForm({ number, onDone }: { number: string; onDone: () => void }) {
  const [reason, setReason] = useState("");
  const cancel = useMutation({
    mutationFn: async () => unwrap(await api.POST("/api/admin/inventory/documents/{number}/cancel", { params: { path: { number } }, body: { reason } })),
    onSuccess: onDone,
  });
  return (
    <form className="apanel" style={{ marginTop: 12 }} onSubmit={(e) => { e.preventDefault(); cancel.mutate(); }}>
      <h2>ยกเลิกใบส่ง</h2>
      <p className="xs ink-muted">ของจะกลับเข้าคลังกลาง ทำได้เฉพาะก่อนสาขารับ</p>
      <div className="mh-field"><label className="mh-label" htmlFor="cr">เหตุผล</label><input className="mh-input" id="cr" value={reason} onChange={(e) => setReason(e.target.value)} required /></div>
      <ErrorNotice error={cancel.error} />
      <button className="mh-btn mh-btn--danger" type="submit" disabled={cancel.isPending || !reason.trim()}>ยกเลิกใบส่ง</button>
    </form>
  );
}

function ReceiveReturnForm({ number, lines, onDone }: { number: string; lines: DocLine[]; onDone: () => void }) {
  const [rows, setRows] = useState(() => lines.map((l) => ({ line_id: l.id, restock: l.sent, discard: "0", sent: l.sent })));
  const confirm = useMutation({
    mutationFn: async () => unwrap(await api.POST("/api/admin/inventory/documents/{number}/receive-return", {
      params: { path: { number } },
      body: { lines: rows.map((r) => ({ line_id: r.line_id, restock: r.restock.trim(), discard: r.discard.trim() })) },
    })),
    onSuccess: onDone,
  });
  return (
    <form className="apanel" style={{ marginTop: 12 }} onSubmit={(e) => { e.preventDefault(); confirm.mutate(); }}>
      <h2>รับของคืนเข้าคลังกลาง</h2>
      <p className="xs ink-muted">เข้าสต็อก = ยังขายได้ ทิ้ง = เสียหาย ไม่กลับเข้าสต็อก ส่วนที่นับไม่ครบจะถือว่าหาย</p>
      {rows.map((r, i) => (
        <div key={r.line_id} className="mh-row" style={{ gap: 8, flexWrap: "wrap" }}>
          <span className="bold" style={{ minWidth: 140 }}>{lines[i].name}</span>
          <span className="xs ink-muted">ส่งคืน {r.sent}</span>
          <label className="xs">เข้าสต็อก <input className="mh-input num" aria-label={`เข้าสต็อก ${lines[i].name}`} style={{ width: 90 }} value={r.restock}
            onChange={(e) => setRows(rows.map((x, j) => (j === i ? { ...x, restock: e.target.value } : x)))} /></label>
          <label className="xs">ทิ้ง <input className="mh-input num" aria-label={`ทิ้ง ${lines[i].name}`} style={{ width: 90 }} value={r.discard}
            onChange={(e) => setRows(rows.map((x, j) => (j === i ? { ...x, discard: e.target.value } : x)))} /></label>
        </div>
      ))}
      <ErrorNotice error={confirm.error} />
      <button className="mh-btn mh-btn--primary" type="submit" disabled={confirm.isPending}>{confirm.isPending ? "กำลังบันทึก…" : "ยืนยันรับคืน"}</button>
    </form>
  );
}

// ---------------------------------------------------------------- receipts, transfers, returns

function ReceiptTab() {
  const qc = useQueryClient();
  const sources = useSources();
  const stock = useStockItems();
  const mats = useMaterials();
  const [sourceId, setSourceId] = useState("");
  const [supplierRef, setSupplierRef] = useState("");
  const [note, setNote] = useState("");
  const [lines, setLines] = useState<Line[]>([{ item: "", quantity: "", cost: "" }]);
  const [created, setCreated] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: async () => unwrap(await api.POST("/api/admin/inventory/documents/receipts", {
      body: { source_id: Number(sourceId), supplier_ref: supplierRef, note, lines: toApiLines(lines, true) },
    })),
    onSuccess: (d) => {
      setCreated(d.number); setLines([{ item: "", quantity: "", cost: "" }]); setSupplierRef(""); setNote("");
      for (const k of ["documents", "stock", "materials", "report"]) void qc.invalidateQueries({ queryKey: [k] });
    },
  });
  const onSubmit = (e: FormEvent) => { e.preventDefault(); setCreated(null); save.mutate(); };
  return (
    <form className="apanel" style={{ maxWidth: 820 }} onSubmit={onSubmit}>
      <h2>รับของจากแหล่งสินค้าเข้าคลังกลาง</h2>
      <p className="sm ink-muted">ของเข้าคลังกลางทันที ไม่ต้องรอสาขายืนยัน ระบุแหล่งที่มาและเลขใบส่งของ (ถ้ามี)</p>
      <div className="form-grid">
        <div className="mh-field"><label className="mh-label" htmlFor="rs">แหล่งสินค้า</label>
          <select className="mh-select" id="rs" value={sourceId} onChange={(e) => setSourceId(e.target.value)} required>
            <option value="">— เลือกแหล่ง —</option>
            {sources.data?.filter((s) => s.is_active).map((s) => <option key={s.id} value={s.id}>{s.name} ({s.kind_label})</option>)}
          </select></div>
        <div className="mh-field"><label className="mh-label" htmlFor="rref">เลขใบส่งของ/บิลของแหล่ง</label><input className="mh-input" id="rref" value={supplierRef} onChange={(e) => setSupplierRef(e.target.value)} maxLength={60} /></div>
      </div>
      <div className="mh-field"><span className="mh-label">รายการ</span>
        <LineBuilder lines={lines} onChange={setLines} items={itemOptions(stock.data, mats.data)} withCost />
        <span className="mh-help">ราคาต่อหน่วยเป็นสตางค์ (เว้นว่างได้) ใช้เก็บไว้สำหรับรายงานต้นทุนภายหลัง</span>
      </div>
      <div className="mh-field"><label className="mh-label" htmlFor="rnote">หมายเหตุ</label><input className="mh-input" id="rnote" value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} /></div>
      <Created number={created} />
      <ErrorNotice error={save.error} />
      <button className="mh-btn mh-btn--primary" type="submit" disabled={save.isPending || !sourceId || !lines.some((l) => l.item)}>{save.isPending ? "กำลังบันทึก…" : "บันทึกใบรับสินค้า"}</button>
      <p className="xs ink-muted">ยังไม่มีรายการ? สร้างแหล่งสินค้า วัตถุดิบ หรือวัสดุก่อนในแท็บที่เกี่ยวข้อง</p>
      <p className="xs"><Link to="/inventory">กลับไปหน้าสต็อก</Link></p>
    </form>
  );
}

function TransferTab() {
  const qc = useQueryClient();
  const branches = useBranches();
  const stock = useStockItems();
  const mats = useMaterials();
  const stores = branches.data?.filter((b) => b.kind === "store") ?? [];
  const [to, setTo] = useState("");
  const [vehicle, setVehicle] = useState("");
  const [carrier, setCarrier] = useState("");
  const [note, setNote] = useState("");
  const [lines, setLines] = useState<Line[]>([{ item: "", quantity: "", cost: "" }]);
  const [created, setCreated] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: async () => unwrap(await api.POST("/api/admin/inventory/documents/transfers", {
      body: { to_branch: to || stores[0]?.code || "", vehicle, carrier, note, lines: toApiLines(lines, false) },
    })),
    onSuccess: (d) => {
      setCreated(d.number); setLines([{ item: "", quantity: "", cost: "" }]); setVehicle(""); setCarrier(""); setNote("");
      for (const k of ["documents", "stock", "materials", "report", "summary", "todo"]) void qc.invalidateQueries({ queryKey: [k] });
    },
  });
  const onSubmit = (e: FormEvent) => { e.preventDefault(); setCreated(null); save.mutate(); };
  return (
    <form className="apanel" style={{ maxWidth: 820 }} onSubmit={onSubmit}>
      <h2>ส่งของจากคลังกลางไปสาขา</h2>
      <p className="sm ink-muted">ของจะออกจากคลังกลางทันที และจะเข้าสาขาเมื่อผู้จัดการสาขาตรวจรับแล้วเท่านั้น</p>
      <div className="form-grid">
        <div className="mh-field"><label className="mh-label" htmlFor="tto">ไปสาขา</label>
          <select className="mh-select" id="tto" value={to || stores[0]?.code || ""} onChange={(e) => setTo(e.target.value)}>
            {stores.map((b) => <option key={b.code} value={b.code}>{b.name}</option>)}
          </select></div>
        <div className="mh-field"><label className="mh-label" htmlFor="tveh">รถที่ใช้ส่ง</label><input className="mh-input" id="tveh" value={vehicle} onChange={(e) => setVehicle(e.target.value)} maxLength={100} placeholder="เช่น กระบะขาว กข-1234" required /></div>
        <div className="mh-field"><label className="mh-label" htmlFor="tcar">ผู้นำส่ง (ถ้ามี)</label><input className="mh-input" id="tcar" value={carrier} onChange={(e) => setCarrier(e.target.value)} maxLength={100} /></div>
      </div>
      <div className="mh-field"><span className="mh-label">รายการ</span>
        <LineBuilder lines={lines} onChange={setLines} items={itemOptions(stock.data, mats.data)} />
      </div>
      <div className="mh-field"><label className="mh-label" htmlFor="tnote">หมายเหตุ</label><input className="mh-input" id="tnote" value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} /></div>
      <Created number={created} />
      <ErrorNotice error={save.error} />
      <button className="mh-btn mh-btn--primary" type="submit" disabled={save.isPending || !vehicle.trim() || !lines.some((l) => l.item)}>{save.isPending ? "กำลังบันทึก…" : "บันทึกใบส่งสินค้า"}</button>
    </form>
  );
}

function StoreReturnTab() {
  const qc = useQueryClient();
  const branches = useBranches();
  const stock = useStockItems();
  const mats = useMaterials();
  const stores = branches.data?.filter((b) => b.kind === "store") ?? [];
  const [branch, setBranch] = useState("");
  const [note, setNote] = useState("");
  const [lines, setLines] = useState<Line[]>([{ item: "", quantity: "", cost: "" }]);
  const [created, setCreated] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: async () => unwrap(await api.POST("/api/admin/inventory/documents/returns", {
      body: { branch: branch || stores[0]?.code || "", note, lines: toApiLines(lines, false) },
    })),
    onSuccess: (d) => {
      setCreated(d.number); setLines([{ item: "", quantity: "", cost: "" }]); setNote("");
      for (const k of ["documents", "stock", "materials", "report", "summary", "todo"]) void qc.invalidateQueries({ queryKey: [k] });
    },
  });
  const onSubmit = (e: FormEvent) => { e.preventDefault(); setCreated(null); save.mutate(); };
  return (
    <form className="apanel" style={{ maxWidth: 820 }} onSubmit={onSubmit}>
      <h2>สาขาส่งของคืนคลังกลาง</h2>
      <p className="sm ink-muted">ใช้เมื่อสาขามีของเกินหรือใกล้หมดอายุ ของจะออกจากสาขาทันทีและกลับเข้าคลังกลางเมื่อคลังกลางรับแล้ว</p>
      <div className="mh-field"><label className="mh-label" htmlFor="rbr">สาขา</label>
        <select className="mh-select" id="rbr" value={branch || stores[0]?.code || ""} onChange={(e) => setBranch(e.target.value)}>
          {stores.map((b) => <option key={b.code} value={b.code}>{b.name}</option>)}
        </select></div>
      <div className="mh-field"><span className="mh-label">รายการ</span>
        <LineBuilder lines={lines} onChange={setLines} items={itemOptions(stock.data, mats.data)} />
      </div>
      <div className="mh-field"><label className="mh-label" htmlFor="rnote2">เหตุผล</label><input className="mh-input" id="rnote2" value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} /></div>
      <Created number={created} />
      <ErrorNotice error={save.error} />
      <button className="mh-btn mh-btn--primary" type="submit" disabled={save.isPending || !lines.some((l) => l.item)}>{save.isPending ? "กำลังบันทึก…" : "บันทึกใบคืนสินค้า"}</button>
    </form>
  );
}

// ---------------------------------------------------------------- materials and sources

function MaterialsTab() {
  const qc = useQueryClient();
  const { can } = useAuth();
  const mats = useMaterials();
  const branches = useBranches();
  const [editing, setEditing] = useState<MatRow | null>(null);
  const [form, setForm] = useState({ code: "", name: "", kind: "material", unit: "", low: "", note: "" });
  const [adj, setAdj] = useState({ branch: "", material: "", reason: "waste", quantity: "", note: "" });
  const refresh = () => { for (const k of ["materials", "stock", "report"]) void qc.invalidateQueries({ queryKey: [k] }); };
  const save = useMutation({
    mutationFn: async () => {
      const body = { name: form.name, kind: form.kind, low_stock_threshold: form.low.trim() || null, note: form.note, is_active: true };
      if (editing) return unwrap(await api.PUT("/api/admin/inventory/materials/{code}", { params: { path: { code: editing.code } }, body: { ...body, is_active: editing.is_active } }));
      return unwrap(await api.POST("/api/admin/inventory/materials", { body: { ...body, code: form.code, unit: form.unit, low_stock_threshold: body.low_stock_threshold } }));
    },
    onSuccess: () => { setEditing(null); setForm({ code: "", name: "", kind: "material", unit: "", low: "", note: "" }); refresh(); },
  });
  const adjust = useMutation({
    mutationFn: async () => unwrap(await api.POST("/api/admin/inventory/materials/adjust", {
      body: { branch: adj.branch || branches.data?.[0]?.code || "", material_code: adj.material, reason: adj.reason, quantity: adj.quantity.trim(), note: adj.note },
    })),
    onSuccess: () => { setAdj({ ...adj, quantity: "", note: "" }); refresh(); },
  });
  const onSubmit = (e: FormEvent) => { e.preventDefault(); save.mutate(); };
  return (
    <div className="cols cols--2-1" style={{ alignItems: "start" }}>
      <div className="mh-tablewrap">
        <table className="mh-table">
          <thead><tr><th>รายการ</th><th>ประเภท</th><th>หน่วย</th><th>เตือนเมื่อเหลือ</th><th /></tr></thead>
          <tbody>
            {mats.data?.map((m) => (
              <tr key={m.code} className={editing?.code === m.code ? "sel" : ""}>
                <td><span className="bold">{m.name}</span><br /><span className="xs ink-muted">{m.code}</span></td>
                <td>{m.kind_label}</td>
                <td>{m.unit}</td>
                <td className="num">{m.low_stock_threshold ?? "—"}</td>
                <td>{can("inventory.receive") && <button className="mh-btn mh-btn--secondary mh-btn--sm" onClick={() => { setEditing(m); setForm({ code: m.code, name: m.name, kind: m.kind, unit: m.unit, low: m.low_stock_threshold ?? "", note: m.note }); }}>แก้ไข</button>}</td>
              </tr>
            ))}
            {mats.data?.length === 0 && <tr><td colSpan={5} className="ink-muted">ยังไม่มีวัตถุดิบหรือวัสดุ</td></tr>}
          </tbody>
        </table>
      </div>
      <div style={{ display: "grid", gap: 16, minWidth: 0 }}>
        {can("inventory.receive") && (
          <form className="apanel" onSubmit={onSubmit}>
            <div className="apanel-head"><h2>{editing ? "แก้ไขรายการ" : "เพิ่มวัตถุดิบหรือวัสดุ"}</h2>{editing && <button type="button" className="mh-btn mh-btn--secondary mh-btn--sm" onClick={() => setEditing(null)}>ยกเลิก</button>}</div>
            <div className="mh-field"><label className="mh-label" htmlFor="mn">ชื่อ</label><input className="mh-input" id="mn" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required /></div>
            {!editing && <div className="mh-field"><label className="mh-label" htmlFor="mc">รหัส (a-z ตัวเลข ขีดกลาง)</label><input className="mh-input" id="mc" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value.toLowerCase() })} required pattern="[a-z0-9][a-z0-9-]+" /></div>}
            <div className="form-grid">
              <div className="mh-field"><label className="mh-label" htmlFor="mk">ประเภท</label>
                <select className="mh-select" id="mk" value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}>
                  <option value="material">วัตถุดิบ</option><option value="supply">วัสดุ/บรรจุภัณฑ์</option><option value="other">อื่นๆ</option>
                </select></div>
              {!editing && <div className="mh-field"><label className="mh-label" htmlFor="mu">หน่วย</label><input className="mh-input" id="mu" value={form.unit} onChange={(e) => setForm({ ...form, unit: e.target.value })} placeholder="กก., ชิ้น, ถุง" required /></div>}
              <div className="mh-field"><label className="mh-label" htmlFor="ml">เตือนเมื่อเหลือ</label><input className="mh-input num" id="ml" inputMode="decimal" value={form.low} onChange={(e) => setForm({ ...form, low: e.target.value })} /></div>
            </div>
            <div className="mh-field"><label className="mh-label" htmlFor="mnote">หมายเหตุ</label><input className="mh-input" id="mnote" value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} /></div>
            {editing?.in_use && <p className="xs ink-muted">หน่วยเปลี่ยนไม่ได้แล้ว เพราะมีการเคลื่อนไหวแล้ว</p>}
            <ErrorNotice error={save.error} />
            <button className="mh-btn mh-btn--primary" type="submit" disabled={save.isPending}>{save.isPending ? "กำลังบันทึก…" : "บันทึก"}</button>
          </form>
        )}
        {can("inventory.adjust") && (
          <form className="apanel" onSubmit={(e) => { e.preventDefault(); adjust.mutate(); }}>
            <h2>ตัดของเสีย / เบิกใช้ / นับ</h2>
            <div className="form-grid">
              <div className="mh-field"><label className="mh-label" htmlFor="ab">สาขา</label>
                <select className="mh-select" id="ab" value={adj.branch || branches.data?.[0]?.code || ""} onChange={(e) => setAdj({ ...adj, branch: e.target.value })}>
                  {branches.data?.map((b) => <option key={b.code} value={b.code}>{b.name}</option>)}
                </select></div>
              <div className="mh-field"><label className="mh-label" htmlFor="am">รายการ</label>
                <select className="mh-select" id="am" value={adj.material} onChange={(e) => setAdj({ ...adj, material: e.target.value })} required>
                  <option value="">— เลือก —</option>
                  {mats.data?.filter((m) => m.is_active).map((m) => <option key={m.code} value={m.code}>{m.name}</option>)}
                </select></div>
              <div className="mh-field"><label className="mh-label" htmlFor="ar">เหตุผล</label>
                <select className="mh-select" id="ar" value={adj.reason} onChange={(e) => setAdj({ ...adj, reason: e.target.value })}>
                  <option value="waste">ของเสีย / หมดอายุ</option><option value="consume">เบิกใช้ (ทำสินค้า)</option><option value="count">นับสต็อกจริง</option>
                </select></div>
              <div className="mh-field"><label className="mh-label" htmlFor="aq">จำนวน</label><input className="mh-input num" id="aq" inputMode="decimal" value={adj.quantity} onChange={(e) => setAdj({ ...adj, quantity: e.target.value })} required /></div>
            </div>
            <div className="mh-field"><label className="mh-label" htmlFor="an">หมายเหตุ</label><input className="mh-input" id="an" value={adj.note} onChange={(e) => setAdj({ ...adj, note: e.target.value })} maxLength={200} /></div>
            <ErrorNotice error={adjust.error} />
            <button className="mh-btn mh-btn--primary" type="submit" disabled={adjust.isPending || !adj.material}>{adjust.isPending ? "กำลังบันทึก…" : "บันทึก"}</button>
          </form>
        )}
      </div>
    </div>
  );
}

function SourcesTab() {
  const qc = useQueryClient();
  const sources = useSources();
  const [editing, setEditing] = useState<number | null>(null);
  const [form, setForm] = useState({ name: "", kind: "buy", phone: "", note: "", is_active: true });
  const save = useMutation({
    mutationFn: async () => {
      const body = { name: form.name, kind: form.kind, phone: form.phone, note: form.note, is_active: form.is_active };
      if (editing) return unwrap(await api.PUT("/api/admin/inventory/sources/{source_id}", { params: { path: { source_id: editing } }, body }));
      return unwrap(await api.POST("/api/admin/inventory/sources", { body }));
    },
    onSuccess: () => { setEditing(null); setForm({ name: "", kind: "buy", phone: "", note: "", is_active: true }); void qc.invalidateQueries({ queryKey: ["sources"] }); },
  });
  const onSubmit = (e: FormEvent) => { e.preventDefault(); save.mutate(); };
  return (
    <div className="cols cols--2-1" style={{ alignItems: "start" }}>
      <div className="mh-tablewrap">
        <table className="mh-table">
          <thead><tr><th>แหล่งสินค้า</th><th>ประเภท</th><th>สถานะ</th><th /></tr></thead>
          <tbody>
            {sources.data?.map((s) => (
              <tr key={s.id} className={editing === s.id ? "sel" : ""}>
                <td><span className="bold">{s.name}</span>{s.phone && <><br /><span className="xs ink-muted">{s.phone}</span></>}</td>
                <td>{s.kind_label}</td>
                <td>{s.is_active ? "ใช้งาน" : "ซ่อนอยู่"}</td>
                <td><button className="mh-btn mh-btn--secondary mh-btn--sm" onClick={() => { setEditing(s.id); setForm({ name: s.name, kind: s.kind, phone: s.phone, note: s.note, is_active: s.is_active }); }}>แก้ไข</button></td>
              </tr>
            ))}
            {sources.data?.length === 0 && <tr><td colSpan={4} className="ink-muted">ยังไม่มีแหล่งสินค้า</td></tr>}
          </tbody>
        </table>
      </div>
      <form className="apanel" onSubmit={onSubmit}>
        <div className="apanel-head"><h2>{editing ? "แก้ไขแหล่งสินค้า" : "เพิ่มแหล่งสินค้า"}</h2>{editing && <button type="button" className="mh-btn mh-btn--secondary mh-btn--sm" onClick={() => setEditing(null)}>ยกเลิก</button>}</div>
        <div className="mh-field"><label className="mh-label" htmlFor="sn">ชื่อ</label><input className="mh-input" id="sn" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required /></div>
        <div className="form-grid">
          <div className="mh-field"><label className="mh-label" htmlFor="sk">ประเภท</label>
            <select className="mh-select" id="sk" value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}>
              <option value="made">ผลิตเอง</option><option value="buy">ซื้อ</option><option value="other">อื่นๆ</option>
            </select></div>
          <div className="mh-field"><label className="mh-label" htmlFor="sp">เบอร์โทร</label><input className="mh-input" id="sp" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} /></div>
        </div>
        <div className="mh-field"><label className="mh-label" htmlFor="sno">หมายเหตุ</label><input className="mh-input" id="sno" value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} /></div>
        {editing && <label className="mh-row" style={{ gap: 8 }}><input type="checkbox" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} /> ใช้งานอยู่</label>}
        <ErrorNotice error={save.error} />
        <button className="mh-btn mh-btn--primary" type="submit" disabled={save.isPending}>{save.isPending ? "กำลังบันทึก…" : "บันทึก"}</button>
      </form>
    </div>
  );
}

function PlacesTab() {
  const qc = useQueryClient();
  const places = useQuery({ queryKey: ["branch-settings"], queryFn: async () => unwrap(await api.GET("/api/admin/inventory/branches/settings")) });
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const save = useMutation({
    mutationFn: async (code: string) => unwrap(await api.PUT("/api/admin/inventory/branches/{code}/line-group", {
      params: { path: { code } }, body: { line_group_id: (drafts[code] ?? "").trim() },
    })),
    onSuccess: (_d, code) => {
      setDrafts((d) => { const next = { ...d }; delete next[code]; return next; });
      void qc.invalidateQueries({ queryKey: ["branch-settings"] });
    },
  });
  return (
    <div style={{ display: "grid", gap: 12, maxWidth: 820 }}>
      <p className="sm ink-muted">แจ้งเตือนคลังของแต่ละสาขาจะส่งเข้ากลุ่ม LINE ของสาขานั้น เว้นว่างไว้จะใช้กลุ่มกลางของร้าน รหัสกลุ่มขึ้นต้นด้วย C ดูได้จากบอท LINE (พิมพ์ /id ในกลุ่ม)</p>
      <ErrorNotice error={save.error} />
      <div className="mh-tablewrap">
        <table className="mh-table">
          <thead><tr><th>สาขา</th><th>ประเภท</th><th>รหัสกลุ่ม LINE</th><th /></tr></thead>
          <tbody>
            {places.data?.map((p) => {
              const value = drafts[p.code] ?? p.line_group_id;
              return (
                <tr key={p.code}>
                  <td className="bold">{p.name}</td>
                  <td>{p.kind === "central" ? "คลังกลาง" : "สาขา"}</td>
                  <td><input className="mh-input" aria-label={`รหัสกลุ่ม LINE ${p.name}`} value={value} maxLength={64} placeholder="ใช้กลุ่มกลาง"
                    onChange={(e) => setDrafts({ ...drafts, [p.code]: e.target.value })} /></td>
                  <td><button className="mh-btn mh-btn--secondary mh-btn--sm" disabled={save.isPending || drafts[p.code] === undefined}
                    onClick={() => save.mutate(p.code)}>บันทึก</button></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- reconciliation

function ReportTab() {
  const branches = useBranches();
  const [branch, setBranch] = useState("");
  const [from, setFrom] = useState(today());
  const [to, setTo] = useState(today());
  const code = branch || branches.data?.[0]?.code || "";
  const report = useQuery({
    queryKey: ["report", code, from, to],
    enabled: !!code && !!from && !!to,
    queryFn: async () => unwrap(await api.GET("/api/admin/inventory/reports/reconcile", { params: { query: { branch: code, date_from: from, date_to: to } } })),
  });
  const FLOW_LABEL: Record<string, string> = {
    receive: "รับเข้า", transfer_in: "รับโอน", transfer_out: "โอนออก", transfer_cancel: "ยกเลิกส่ง",
    return_in: "รับคืน", return_out: "ส่งคืนคลัง", sale: "ขายออนไลน์", counter_sale: "ขายหน้าร้าน", consume: "เบิกใช้",
    waste: "ของเสีย", count: "นับจริง", opening: "ยอดยกมา", correction: "แก้ไข",
  };
  return (
    <div style={{ display: "grid", gap: 12 }}>
      <div className="toolbar">
        <select className="mh-select" aria-label="สาขา" style={{ width: "auto" }} value={code} onChange={(e) => setBranch(e.target.value)}>
          {branches.data?.map((b) => <option key={b.code} value={b.code}>{b.name}</option>)}
        </select>
        <input className="mh-input" type="date" aria-label="จากวันที่" value={from} onChange={(e) => setFrom(e.target.value)} style={{ width: "auto" }} />
        <input className="mh-input" type="date" aria-label="ถึงวันที่" value={to} onChange={(e) => setTo(e.target.value)} style={{ width: "auto" }} />
      </div>
      <ErrorNotice error={report.error} />
      {report.data && (
        <>
          <p className="sm">
            {report.data.unbalanced === 0
              ? <span className="mh-status mh-status--done" data-glyph="✓">ยอดตรงทุกรายการ</span>
              : <span className="mh-status mh-status--cancel" data-glyph="✕">มี {report.data.unbalanced} รายการที่ยอดไม่ตรง ต้องตรวจก่อน</span>}
            <span className="xs ink-muted"> · ยอดปลายงวด = ยอดต้นงวด + การเคลื่อนไหวในช่วง และต้องเท่ากับของที่มีจริงในระบบ</span>
          </p>
          <div className="mh-tablewrap">
            <table className="mh-table">
              <thead><tr style={{ whiteSpace: "normal" }}><th>รายการ</th><th className="r">ต้นงวด</th><th>การเคลื่อนไหว</th><th className="r">ปลายงวด</th><th className="r">มีอยู่</th><th className="r">กำลังส่ง (เข้า/ออก)</th><th className="r">หาย</th><th className="r">ทิ้ง</th></tr></thead>
              <tbody>
                {report.data.rows.map((r) => (
                  <tr key={`${r.kind}-${r.id}`}>
                    <td className="wrap"><span className="bold">{r.name}</span><br /><span className="xs ink-muted">{r.unit}</span></td>
                    <td className="r">{r.opening}</td>
                    <td className="wrap xs">{Object.entries(r.flows).filter(([, v]) => v !== "0").map(([k, v]) => `${FLOW_LABEL[k] ?? k} ${v.startsWith("-") ? v : `+${v}`}`).join(" · ") || "—"}</td>
                    <td className="r bold">{r.closing}</td>
                    <td className="r">{r.on_hand}{!r.balanced && <><br /><span className="mh-status mh-status--cancel" data-glyph="✕">ไม่ตรง</span></>}</td>
                    <td className="r">{r.in_transit_in} / {r.in_transit_out}</td>
                    <td className="r">{r.lost}</td>
                    <td className="r">{r.discarded}</td>
                  </tr>
                ))}
                {report.data.rows.length === 0 && <tr><td colSpan={8} className="ink-muted">ยังไม่มีการเคลื่อนไหวในช่วงนี้</td></tr>}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}


// ---------------------------------------------------------------- printable transfer slip (A5)

type FullDoc = NonNullable<Awaited<ReturnType<typeof getDoc>>>;
async function getDoc(number: string) {
  return unwrap(await api.GET("/api/admin/inventory/documents/{number}", { params: { path: { number } } }));
}

/** Shown only when printing: a transfer slip with the number, place, vehicle, lines and signature boxes. */
function PrintSlip({ doc }: { doc: FullDoc }) {
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

// ---------------------------------------------------------------- stock counts

function CountsTab() {
  const qc = useQueryClient();
  const { can } = useAuth();
  const branches = useBranches();
  const [branch, setBranch] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  const counts = useQuery({ queryKey: ["counts"], queryFn: async () => unwrap(await api.GET("/api/admin/inventory/documents", { params: { query: { kind: "count", limit: 50 } } })) });
  const detail = useQuery({
    queryKey: ["document", open], enabled: !!open,
    queryFn: async () => unwrap(await api.GET("/api/admin/inventory/documents/{number}", { params: { path: { number: open! } } })),
  });
  const refresh = () => { for (const k of ["counts", "document", "stock", "materials", "report", "summary", "todo"]) void qc.invalidateQueries({ queryKey: [k] }); };
  const start = useMutation({
    mutationFn: async () => unwrap(await api.POST("/api/admin/inventory/counts", { body: { branch: branch || branches.data?.[0]?.code || "", note: "" } })),
    onSuccess: (d) => { setOpen(d.number); refresh(); },
  });
  return (
    <div className="cols cols--2-1" style={{ alignItems: "start" }}>
      <div style={{ display: "grid", gap: 12, minWidth: 0 }}>
        {can("inventory.adjust") && (
          <div className="mh-row" style={{ gap: 8 }}>
            <select className="mh-select" aria-label="สาขาที่จะนับ" style={{ width: "auto" }} value={branch || branches.data?.[0]?.code || ""} onChange={(e) => setBranch(e.target.value)}>
              {branches.data?.map((b) => <option key={b.code} value={b.code}>{b.name}</option>)}
            </select>
            <button className="mh-btn mh-btn--primary mh-btn--sm" disabled={start.isPending} onClick={() => start.mutate()}>{start.isPending ? "กำลังเปิด…" : "เริ่มนับสต็อก"}</button>
          </div>
        )}
        <ErrorNotice error={start.error ?? counts.error} />
        <div className="mh-tablewrap">
          <table className="mh-table">
            <thead><tr><th>เลขที่</th><th>สาขา</th><th>สถานะ</th><th>วันที่</th></tr></thead>
            <tbody>
              {counts.data?.map((d) => (
                <tr key={d.number} className={d.number === open ? "sel" : ""} onClick={() => setOpen(d.number)} style={{ cursor: "pointer" }}>
                  <td><span className="mh-code">{d.number}</span></td>
                  <td>{d.to_branch ?? "—"}</td>
                  <td className="wrap">{d.status_label}</td>
                  <td className="xs">{formatThaiDate(d.created_at)}</td>
                </tr>
              ))}
              {counts.data?.length === 0 && <tr><td colSpan={4} className="ink-muted">ยังไม่มีการนับ</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
      <div style={{ display: "grid", gap: 16, minWidth: 0 }}>
        {detail.data?.kind === "count" ? <CountSheet doc={detail.data} onDone={refresh} onClose={() => setOpen(null)} /> : (
          <div className="apanel"><p className="ink-muted">เริ่มนับหรือเลือกใบนับจากรายการ</p></div>
        )}
      </div>
    </div>
  );
}

type CountDoc = NonNullable<Awaited<ReturnType<typeof getDoc>>>;

function CountSheet({ doc, onDone, onClose }: { doc: CountDoc; onDone: () => void; onClose: () => void }) {
  const { can } = useAuth();
  const approver = can("inventory.approve");
  const counting = doc.status === "counting";
  const [values, setValues] = useState<Record<number, string>>({});
  const [reason, setReason] = useState("");
  const [result, setResult] = useState<string | null>(null);
  const record = useMutation({
    mutationFn: async () => unwrap(await api.PUT("/api/admin/inventory/counts/{number}/lines", {
      params: { path: { number: doc.number } },
      body: { lines: Object.entries(values).filter(([, v]) => v.trim() !== "").map(([id, v]) => ({ line_id: Number(id), counted: v.trim() })) },
    })),
    onSuccess: () => { setResult("บันทึกการนับแล้ว"); onDone(); },
  });
  const submit = useMutation({
    mutationFn: async () => unwrap(await api.POST("/api/admin/inventory/counts/{number}/submit", { params: { path: { number: doc.number } } })),
    onSuccess: (d) => { setResult(d.status === "posted" ? "ปรับสต็อกตามที่นับแล้ว" : "ส่งให้ผู้จัดการอนุมัติ เพราะผลต่างเกิน 20 ชิ้น"); onDone(); },
  });
  const approve = useMutation({
    mutationFn: async () => unwrap(await api.POST("/api/admin/inventory/counts/{number}/approve", { params: { path: { number: doc.number } } })),
    onSuccess: () => { setResult("อนุมัติและปรับสต็อกแล้ว"); onDone(); },
  });
  const reject = useMutation({
    mutationFn: async () => unwrap(await api.POST("/api/admin/inventory/counts/{number}/reject", { params: { path: { number: doc.number } }, body: { reason } })),
    onSuccess: () => { setResult("ส่งกลับไปนับใหม่แล้ว"); setReason(""); onDone(); },
  });
  const pending = doc.status === "pending_approval";
  return (
    <section className="apanel">
      <div className="apanel-head"><h2>{doc.number}</h2><button type="button" className="mh-btn mh-btn--secondary mh-btn--sm" onClick={onClose}>ปิด</button></div>
      <p className="sm">{doc.to_branch} · <b>{doc.status_label}</b></p>
      {doc.review_note && <p className="xs">ส่งกลับเพราะ: {doc.review_note}</p>}
      <div className="mh-tablewrap" style={{ border: 0, maxHeight: 420, overflowY: "auto" }}>
        <table className="mh-table">
          <thead><tr><th>รายการ</th><th className="r">นับได้</th>{approver && <><th className="r">ระบบคิดว่ามี</th><th className="r">ต่าง</th></>}</tr></thead>
          <tbody>
            {doc.lines.map((l) => (
              <tr key={l.id}>
                <td className="wrap">{l.name} <span className="xs ink-muted">{l.unit}</span></td>
                <td className="r">
                  {counting ? (
                    <input className="mh-input num" aria-label={`นับ ${l.name}`} inputMode="decimal" style={{ width: 100 }}
                      placeholder={l.counted ?? ""} value={values[l.id] ?? ""} onChange={(e) => setValues({ ...values, [l.id]: e.target.value })} />
                  ) : (l.counted ?? "—")}
                </td>
                {approver && <><td className="r">{l.expected ?? "—"}</td><td className="r">{l.variance ?? "—"}</td></>}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {result && <div className="notice notice--ok" role="status"><p>{result}</p></div>}
      <ErrorNotice error={record.error ?? submit.error ?? approve.error ?? reject.error} />
      {counting && (
        <div className="mh-row" style={{ gap: 8, marginTop: 12 }}>
          <button className="mh-btn mh-btn--secondary mh-btn--sm" disabled={record.isPending || !Object.values(values).some((v) => v.trim())} onClick={() => record.mutate()}>บันทึกการนับ</button>
          <button className="mh-btn mh-btn--primary mh-btn--sm" disabled={submit.isPending} onClick={() => submit.mutate()}>ส่งตรวจ / ปิดการนับ</button>
        </div>
      )}
      {pending && approver && (
        <div style={{ display: "grid", gap: 8, marginTop: 12 }}>
          <button className="mh-btn mh-btn--primary" disabled={approve.isPending} onClick={() => approve.mutate()}>อนุมัติและปรับสต็อก</button>
          <div className="mh-row" style={{ gap: 8 }}>
            <input className="mh-input" aria-label="เหตุผลที่ส่งกลับไปนับ" placeholder="เหตุผลที่ส่งกลับไปนับใหม่" value={reason} onChange={(e) => setReason(e.target.value)} style={{ flex: 1 }} />
            <button className="mh-btn mh-btn--secondary" disabled={reject.isPending || !reason.trim()} onClick={() => reject.mutate()}>ส่งกลับไปนับ</button>
          </div>
        </div>
      )}
      {counting && <p className="xs ink-muted">ผลต่างรวมไม่เกิน 20 ชิ้นปรับให้ทันที มากกว่านั้นต้องให้ผู้จัดการอนุมัติ</p>}
    </section>
  );
}

// ---------------------------------------------------------------- counter day-close

function DayCloseTab() {
  const qc = useQueryClient();
  const branches = useBranches();
  const stock = useQuery({ queryKey: ["stock", "dayclose"], queryFn: async () => unwrap(await api.GET("/api/admin/inventory/stock", { params: { query: { tracked_only: true } } })) });
  const [branch, setBranch] = useState("");
  const [sold, setSold] = useState<Record<string, string>>({});
  const code = branch || branches.data?.[0]?.code || "";
  const rows = (stock.data ?? []).filter((r) => r.track_stock);
  const save = useMutation({
    mutationFn: async () => unwrap(await api.POST("/api/admin/inventory/branches/{code}/day-close", {
      params: { path: { code } },
      body: { branch: code, lines: Object.entries(sold).filter(([, v]) => Number(v) > 0).map(([sku, v]) => ({ sku, sold: Number(v) })) },
    })),
    onSuccess: () => { setSold({}); for (const k of ["stock", "report", "summary", "todo"]) void qc.invalidateQueries({ queryKey: [k] }); },
  });
  return (
    <form className="apanel" style={{ maxWidth: 820 }} onSubmit={(e: FormEvent) => { e.preventDefault(); save.mutate(); }}>
      <h2>ปิดยอดขายหน้าร้านประจำวัน</h2>
      <p className="sm ink-muted">กรอกจำนวนที่ขายหน้าร้านของแต่ละรายการวันนี้ ระบบจะตัดออกจากสต็อกของสาขานั้น คำสั่งซื้อออนไลน์ที่จองไว้แล้วจะไม่ถูกตัด</p>
      <div className="mh-field"><label className="mh-label" htmlFor="dcb">สาขา</label>
        <select className="mh-select" id="dcb" value={code} onChange={(e) => { setBranch(e.target.value); setSold({}); }}>
          {branches.data?.map((b) => <option key={b.code} value={b.code}>{b.name}</option>)}
        </select>
      </div>
      <div className="mh-tablewrap" style={{ maxHeight: 420, overflowY: "auto" }}>
        <table className="mh-table">
          <thead><tr><th>รายการ</th><th className="r">ว่าง (ขายได้)</th><th className="r">ขายหน้าร้านวันนี้</th></tr></thead>
          <tbody>
            {rows.map((r) => {
              const lvl = r.levels.find((l) => l.branch === code);
              return (
                <tr key={r.sku}>
                  <td className="wrap">{r.product_name} ({r.variant_label})</td>
                  <td className="r">{lvl?.available ?? 0}</td>
                  <td className="r"><input className="mh-input num" aria-label={`ขายหน้าร้าน ${r.product_name} ${r.variant_label}`} inputMode="numeric" style={{ width: 100 }}
                    value={sold[r.sku] ?? ""} onChange={(e) => setSold({ ...sold, [r.sku]: e.target.value })} /></td>
                </tr>
              );
            })}
            {rows.length === 0 && <tr><td colSpan={3} className="ink-muted">ยังไม่มีสินค้าที่เปิดนับสต็อก</td></tr>}
          </tbody>
        </table>
      </div>
      <ErrorNotice error={save.error} />
      {save.isSuccess && <div className="notice notice--ok" role="status"><p>ตัดยอดขายหน้าร้านแล้ว</p></div>}
      <button className="mh-btn mh-btn--primary" type="submit" disabled={save.isPending || !Object.values(sold).some((v) => Number(v) > 0)} style={{ marginTop: 12 }}>
        {save.isPending ? "กำลังบันทึก…" : "ปิดยอดวันนี้"}
      </button>
    </form>
  );
}
