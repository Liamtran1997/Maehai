import { formatThaiDate } from "@maehai/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ErrorNotice } from "../components/Notice";
import { api, unwrap } from "../lib/api";
import { useAuth } from "../lib/auth";
import { Inventory } from "./Inventory";
import { REFUSE, today, useBranches, useMaterials, useSources, useStockItems, type MatRow, type FullDoc, getDoc } from "./warehouse/shared";

type CountDoc = FullDoc;

// Sections of the warehouse page. The tab is kept in the address (?tab=) so links can open a section directly.
const TABS = [
  { key: "stock", label: "สต็อก", perm: "inventory.view" },
  { key: "docs", label: "เอกสาร", perm: "inventory.view" },
  { key: "counts", label: "นับสต็อก", perm: "inventory.adjust" },
  { key: "dayclose", label: "ปิดยอดหน้าร้าน", perm: "inventory.adjust" },
  { key: "report", label: "รายงาน", perm: "inventory.view" },
  { key: "settings", label: "ตั้งค่า", perm: "inventory.receive" },
] as const;

const NEW_SLIPS = [
  { to: "/warehouse/new/receipt", title: "รับของเข้าคลังกลาง", sub: "จากแหล่งสินค้า · IN-", perm: "inventory.receive" },
  { to: "/warehouse/new/transfer", title: "ส่งของไปสาขา", sub: "จากคลังกลาง · TR-", perm: "inventory.transfer" },
  { to: "/warehouse/new/return", title: "สาขาส่งคืนคลัง", sub: "ของเกินหรือใกล้หมดอายุ · RT-", perm: "inventory.adjust" },
] as const;

export function Warehouse() {
  const { can } = useAuth();
  const [params, setParams] = useSearchParams();
  const visible = TABS.filter((t) => can(t.perm));
  const requested = params.get("tab");
  const tab = visible.find((t) => t.key === requested)?.key ?? visible[0]?.key ?? "stock";
  const [menuOpen, setMenuOpen] = useState(false);
  const newSlips = NEW_SLIPS.filter((n) => can(n.perm));
  return (
    <>
      <div className="topbar">
        <h1>คลังสินค้า</h1>
        {newSlips.length > 0 && (
          <div style={{ position: "relative" }}>
            <button type="button" className="mh-btn mh-btn--primary mh-btn--sm" aria-haspopup="menu" aria-expanded={menuOpen} onClick={() => setMenuOpen((o) => !o)}>สร้างเอกสาร ▾</button>
            {menuOpen && (
              <div role="menu" style={{ position: "absolute", right: 0, top: 44, zIndex: 5, width: 280, padding: 6, background: "var(--surface-200)", border: "1px solid var(--line)", borderRadius: 12, boxShadow: "var(--shadow-pop)", display: "flex", flexDirection: "column" }}>
                {newSlips.map((n) => (
                  <Link key={n.to} role="menuitem" to={n.to} className="nav" onClick={() => setMenuOpen(false)} style={{ minHeight: 52 }}>
                    <span><b style={{ display: "block", fontSize: 14 }}>{n.title}</b><span className="small muted">{n.sub}</span></span>
                  </Link>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
      <div className="list-tabs" role="tablist" aria-label="ส่วนของคลัง">
        {visible.map((t) => (
          <button key={t.key} type="button" className="tab" role="tab" aria-selected={tab === t.key} aria-pressed={tab === t.key} onClick={() => setParams({ tab: t.key })}>{t.label}</button>
        ))}
      </div>
      {tab === "stock" && <Inventory />}
      {tab === "docs" && <DocumentsTab />}
      {tab === "counts" && <CountsTab />}
      {tab === "dayclose" && <DayCloseTab />}
      {tab === "report" && <ReportTab />}
      {tab === "settings" && <SettingsTab />}
    </>
  );
}

const SETTINGS_PARTS = [
  { key: "materials", label: "วัตถุดิบ" },
  { key: "adjust", label: "ตัดของเสีย / เบิกใช้ / นับ" },
  { key: "sources", label: "แหล่งสินค้า" },
  { key: "places", label: "จุดเก็บและไลน์" },
] as const;

/** Settings in three parts, one at a time, so each screen stays short. */
function SettingsTab() {
  const [part, setPart] = useState<(typeof SETTINGS_PARTS)[number]["key"]>("materials");
  return (
    <div style={{ display: "grid", gap: 24 }}>
      <div className="list-tabs" role="tablist" aria-label="ส่วนของการตั้งค่า">
        {SETTINGS_PARTS.map((p) => (
          <button key={p.key} type="button" role="tab" className="tab" aria-selected={part === p.key} aria-pressed={part === p.key} onClick={() => setPart(p.key)}>{p.label}</button>
        ))}
      </div>
      {part === "materials" && <MaterialsTab />}
      {part === "adjust" && <AdjustTab />}
      {part === "sources" && <SourcesTab />}
      {part === "places" && <PlacesTab />}
    </div>
  );
}

/** Every slip, newest first. Opening one goes to its own page. */
function DocumentsTab() {
  const [kind, setKind] = useState("");
  const [status, setStatus] = useState("");
  const docs = useQuery({
    queryKey: ["documents", kind, status],
    queryFn: async () => unwrap(await api.GET("/api/admin/inventory/documents", { params: { query: { kind: kind || undefined, status: status || undefined, limit: 100 } } })),
  });
  return (
    <div style={{ display: "grid", gap: 12 }}>
      <div className="toolbar">
        <select className="mh-select" aria-label="ประเภทเอกสาร" style={{ width: "auto" }} value={kind} onChange={(e) => setKind(e.target.value)}>
          <option value="">ทุกประเภท</option><option value="receipt">ใบรับสินค้า (IN)</option><option value="transfer">ใบส่งสินค้า (TR)</option><option value="return">ใบคืนสินค้า (RT)</option><option value="count">ใบนับสต็อก (CNT)</option>
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
              <tr key={d.number}>
                <td><Link className="mh-code link" to={`/warehouse/documents/${d.number}`}>{d.number}</Link>{d.overdue && <span className="mh-status mh-status--wait" data-glyph="!" style={{ marginLeft: 8 }}>ค้างเกิน 24 ชม.</span>}</td>
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
  );
}

export function MaterialsTab() {
  const qc = useQueryClient();
  const { can } = useAuth();
  const mats = useMaterials();
  const branches = useBranches();
  const [editing, setEditing] = useState<MatRow | null>(null);
  const [form, setForm] = useState({ code: "", name: "", kind: "material", unit: "", low: "", note: "" });
  const refresh = () => { for (const k of ["materials", "stock", "report"]) void qc.invalidateQueries({ queryKey: [k] }); };
  const save = useMutation({
    mutationFn: async () => {
      const body = { name: form.name, kind: form.kind, low_stock_threshold: form.low.trim() || null, note: form.note, is_active: true };
      if (editing) return unwrap(await api.PUT("/api/admin/inventory/materials/{code}", { params: { path: { code: editing.code } }, body: { ...body, is_active: editing.is_active } }));
      return unwrap(await api.POST("/api/admin/inventory/materials", { body: { ...body, code: form.code, unit: form.unit, low_stock_threshold: body.low_stock_threshold } }));
    },
    onSuccess: () => { setEditing(null); setForm({ code: "", name: "", kind: "material", unit: "", low: "", note: "" }); refresh(); },
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
      </div>
    </div>
  );
}

/** Write-offs, withdrawals and counts of materials, on their own so the materials page stays short. */
export function AdjustTab() {
  const qc = useQueryClient();
  const { can } = useAuth();
  const mats = useMaterials();
  const branches = useBranches();
  const [adj, setAdj] = useState({ branch: "", material: "", reason: "waste", quantity: "", note: "" });
  const refresh = () => { for (const k of ["materials", "stock", "report"]) void qc.invalidateQueries({ queryKey: [k] }); };
  const adjust = useMutation({
    mutationFn: async () => unwrap(await api.POST("/api/admin/inventory/materials/adjust", {
      body: { branch: adj.branch || branches.data?.[0]?.code || "", material_code: adj.material, reason: adj.reason, quantity: adj.quantity.trim(), note: adj.note },
    })),
    onSuccess: () => { setAdj({ ...adj, quantity: "", note: "" }); refresh(); },
  });
  if (!can("inventory.adjust")) return <p className="ink-muted">ตำแหน่งของคุณไม่มีสิทธิ์ตัดหรือนับวัตถุดิบ</p>;
  return (
    <div style={{ maxWidth: 560 }}>
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
    </div>
  );
}

export function SourcesTab() {
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

export function PlacesTab() {
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

export function ReportTab() {
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

export function CountsTab() {
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

export function CountSheet({ doc, onDone, onClose }: { doc: CountDoc; onDone: () => void; onClose: () => void }) {
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

export function DayCloseTab() {
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
