import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { ErrorNotice } from "../components/Notice";
import { api, unwrap, type StaffMember } from "../lib/api";
import { useAuth } from "../lib/auth";

const when = (iso?: string | null) => (iso ? new Date(iso).toLocaleString("th-TH", { dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Bangkok" }) : "ยังไม่เคยเข้า");

const ACTION_LABEL: Record<string, string> = {
  "staff.create": "เพิ่มพนักงาน", "staff.update": "แก้ไขพนักงาน", "staff.reset_password": "รีเซ็ตรหัสผ่าน", "password.change": "เปลี่ยนรหัสผ่านตัวเอง",
  "price.change": "แก้ราคา", "product.create": "เพิ่มสินค้า", "promotion.create": "สร้างโปรโมชัน", "promotion.update": "แก้โปรโมชัน",
  "promotion.end": "ปิดโปรโมชัน", "promotion.delete": "ลบโปรโมชัน", "coupon.create": "สร้างโค้ด", "coupon.update": "แก้โค้ด",
  "coupon.end": "ปิดโค้ด", "inventory.import": "นำเข้าสต็อกจากไฟล์", "inventory.level_settings": "ตั้งโควตาออนไลน์/จุดเตือนสต็อก", "coupon.delete": "ลบโค้ด", "order.cancel_paid": "ยกเลิกคำสั่งซื้อที่ชำระแล้ว",
};

type Form = { id?: number; username: string; display_name: string; role: string; password: string; is_active: boolean; branch_codes: string[] };

// Roles that work with particular places. Owners and managers see every place, so no branch is picked for them.
const PLACE_ROLES = ["branch_manager", "warehouse", "sales"];

export function Staff() {
  const qc = useQueryClient();
  const { user } = useAuth();
  const [tab, setTab] = useState<"people" | "roles" | "audit">("people");
  const staff = useQuery({ queryKey: ["staff"], queryFn: async () => unwrap(await api.GET("/api/admin/staff")) });
  const roles = useQuery({ queryKey: ["roles"], queryFn: async () => unwrap(await api.GET("/api/admin/roles")) });
  const branches = useQuery({ queryKey: ["branches"], queryFn: async () => unwrap(await api.GET("/api/admin/inventory/branches")) });
  const audit = useQuery({ queryKey: ["audit"], enabled: tab === "audit", queryFn: async () => unwrap(await api.GET("/api/admin/audit", { params: { query: { limit: 200 } } })) });
  const [form, setForm] = useState<Form | null>(null);
  const [resetFor, setResetFor] = useState<StaffMember | null>(null);
  const [resetPw, setResetPw] = useState("");
  const refresh = () => { void qc.invalidateQueries({ queryKey: ["staff"] }); void qc.invalidateQueries({ queryKey: ["audit"] }); };

  const save = useMutation({
    mutationFn: async (f: Form) => f.id
      ? unwrap(await api.PUT("/api/admin/staff/{user_id}", { params: { path: { user_id: f.id } }, body: { display_name: f.display_name, role: f.role, is_active: f.is_active, branch_codes: f.branch_codes } }))
      : unwrap(await api.POST("/api/admin/staff", { body: { username: f.username, display_name: f.display_name, role: f.role, password: f.password, branch_codes: f.branch_codes } })),
    onSuccess: () => { setForm(null); refresh(); },
  });
  const reset = useMutation({
    mutationFn: async () => unwrap(await api.POST("/api/admin/staff/{user_id}/reset-password", { params: { path: { user_id: resetFor!.id } }, body: { password: resetPw } })),
    onSuccess: () => { setResetFor(null); setResetPw(""); refresh(); },
  });
  const onSubmit = (e: FormEvent) => { e.preventDefault(); if (form) save.mutate(form); };
  const open = (f: Form) => { save.reset(); setForm(f); };
  const roleDesc = roles.data?.roles.find((r) => r.key === form?.role)?.description;

  return (
    <>
      <div className="topbar">
        <h1>พนักงานและสิทธิ์</h1>
        <button className="mh-btn mh-btn--primary mh-btn--sm" onClick={() => open({ username: "", display_name: "", role: "sales", password: "", is_active: true, branch_codes: [] })}>เพิ่มพนักงาน</button>
      </div>
      <div className="seg" role="group" aria-label="หัวข้อ" style={{ alignSelf: "flex-start" }}>
        <button aria-pressed={tab === "people"} onClick={() => setTab("people")}>พนักงาน</button>
        <button aria-pressed={tab === "roles"} onClick={() => setTab("roles")}>ตารางสิทธิ์</button>
        <button aria-pressed={tab === "audit"} onClick={() => setTab("audit")}>ประวัติการใช้งาน</button>
      </div>
      <ErrorNotice error={staff.error ?? reset.error} />

      {tab === "people" && (
        <div className="cols cols--2-1" style={{ alignItems: "start" }}>
          <div className="mh-tablewrap">
            <table className="mh-table">
              <thead><tr><th>พนักงาน</th><th>ตำแหน่ง</th><th>เข้าล่าสุด</th><th>สถานะ</th><th /></tr></thead>
              <tbody>
                {staff.data?.map((s) => (
                  <tr key={s.id} className={form?.id === s.id ? "sel" : ""}>
                    <td><span className="bold">{s.display_name || s.username}</span><br /><span className="xs ink-muted">{s.username}{s.username === user?.username ? " (คุณ)" : ""}</span></td>
                    <td>{s.role_label}{s.branch_codes.length > 0 && <><br /><span className="xs ink-muted">{s.branch_codes.map((c) => branches.data?.find((b) => b.code === c)?.name ?? c).join(", ")}</span></>}</td>
                    <td className="xs">{when(s.last_login)}</td>
                    <td>
                      {!s.is_active ? <span className="mh-status mh-status--cancel" data-glyph="✕">ปิดบัญชี</span>
                        : s.must_change_password ? <span className="mh-status mh-status--wait" data-glyph="○">รอตั้งรหัสผ่าน</span>
                        : <span className="mh-status mh-status--done" data-glyph="●">ใช้งานอยู่</span>}
                    </td>
                    <td className="mh-row" style={{ gap: 8 }}>
                      <button className="mh-btn mh-btn--secondary mh-btn--sm" onClick={() => open({ id: s.id, username: s.username, display_name: s.display_name, role: s.role, password: "", is_active: s.is_active, branch_codes: s.branch_codes })}>แก้ไข</button>
                      {s.username !== user?.username && <button className="mh-btn mh-btn--secondary mh-btn--sm" onClick={() => { reset.reset(); setResetFor(s); setResetPw(""); }}>รีเซ็ตรหัสผ่าน</button>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 16, minWidth: 0 }}>
            {resetFor && (
              <form className="apanel" onSubmit={(e) => { e.preventDefault(); reset.mutate(); }}>
                <div className="apanel-head"><h2>รีเซ็ตรหัสผ่าน {resetFor.username}</h2><button type="button" className="mh-btn mh-btn--secondary mh-btn--sm" onClick={() => setResetFor(null)}>ปิด</button></div>
                <div className="mh-field"><label className="mh-label" htmlFor="rp">รหัสผ่านชั่วคราวใหม่</label><input className="mh-input" id="rp" type="text" autoComplete="off" value={resetPw} onChange={(e) => setResetPw(e.target.value)} required minLength={10} /><span className="mh-help">ส่งให้พนักงานทางช่องทางส่วนตัว เขาจะถูกออกจากระบบทุกอุปกรณ์และต้องตั้งรหัสใหม่ตอนเข้าครั้งหน้า</span></div>
                <ErrorNotice error={reset.error} />
                <button className="mh-btn mh-btn--primary" type="submit" disabled={reset.isPending}>รีเซ็ต</button>
              </form>
            )}
            {form && (
              <form className="apanel" onSubmit={onSubmit}>
                <div className="apanel-head"><h2>{form.id ? "แก้ไขพนักงาน" : "เพิ่มพนักงาน"}</h2><button type="button" className="mh-btn mh-btn--secondary mh-btn--sm" onClick={() => setForm(null)}>ปิด</button></div>
                <div className="mh-field"><label className="mh-label" htmlFor="su">ชื่อผู้ใช้</label><input className="mh-input" id="su" value={form.username} disabled={!!form.id} onChange={(e) => setForm({ ...form, username: e.target.value })} required minLength={3} maxLength={30} autoCapitalize="none" /><span className="mh-help">a-z ตัวเลข จุด ขีดกลาง ขีดล่าง ตั้งแล้วเปลี่ยนไม่ได้</span></div>
                <div className="mh-field"><label className="mh-label" htmlFor="sd">ชื่อที่แสดง</label><input className="mh-input" id="sd" value={form.display_name} maxLength={80} onChange={(e) => setForm({ ...form, display_name: e.target.value })} /></div>
                <div className="mh-field">
                  <label className="mh-label" htmlFor="sr">ตำแหน่ง</label>
                  <select className="mh-select" id="sr" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>{roles.data?.roles.map((r) => <option key={r.key} value={r.key}>{r.label}</option>)}</select>
                  {roleDesc && <span className="mh-help">{roleDesc}</span>}
                </div>
                {PLACE_ROLES.includes(form.role) && (
                  <div className="mh-field">
                    <span className="mh-label">{form.role === "branch_manager" ? "สาขาที่ดูแล (เลือกหนึ่งสาขา)" : "สาขาที่ทำงาน"}</span>
                    {branches.data?.filter((b) => form.role !== "branch_manager" || b.kind === "store").map((b) => (
                      <label key={b.code} className="mh-row" style={{ gap: 8 }}>
                        <input type={form.role === "branch_manager" ? "radio" : "checkbox"} name="sb" checked={form.branch_codes.includes(b.code)}
                          onChange={(e) => setForm({ ...form, branch_codes: form.role === "branch_manager" ? [b.code] : e.target.checked ? [...form.branch_codes, b.code] : form.branch_codes.filter((c) => c !== b.code) })} />
                        {b.name}{b.kind === "central" ? " (คลังกลาง)" : ""}
                      </label>
                    ))}
                    <span className="mh-help">{form.role === "branch_manager" ? "ผู้จัดการสาขารับของเข้าสาขาและดูแลสาขานี้เท่านั้น" : "เห็นและทำรายการเฉพาะสาขาที่เลือก"}</span>
                  </div>
                )}
                {!form.id && <div className="mh-field"><label className="mh-label" htmlFor="sp">รหัสผ่านชั่วคราว</label><input className="mh-input" id="sp" type="text" autoComplete="off" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required minLength={10} /><span className="mh-help">อย่างน้อย 10 ตัวอักษร พนักงานต้องตั้งรหัสใหม่ตอนเข้าครั้งแรก</span></div>}
                {form.id && <label className="mh-row" style={{ gap: 8 }}><input type="checkbox" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} style={{ width: 20, height: 20, accentColor: "var(--leaf)" }} /> เปิดใช้งานบัญชี</label>}
                {form.id && !form.is_active && <div className="notice notice--warn"><p>ปิดบัญชีแล้ว พนักงานจะถูกออกจากระบบทันที ประวัติที่เขาทำไว้ยังอยู่</p></div>}
                <ErrorNotice error={save.error} />
                <button className="mh-btn mh-btn--primary" type="submit" disabled={save.isPending}>{save.isPending ? "กำลังบันทึก…" : "บันทึก"}</button>
              </form>
            )}
          </div>
        </div>
      )}

      {tab === "roles" && roles.data && (
        <div className="mh-tablewrap">
          <table className="mh-table">
            <thead>
              <tr><th>สิทธิ์</th>{roles.data.roles.map((r) => <th key={r.key} style={{ textAlign: "center" }}>{r.label}</th>)}</tr>
            </thead>
            <tbody>
              {roles.data.permissions.map((p) => (
                <tr key={p.key}>
                  <td style={{ whiteSpace: "normal", minWidth: 260 }}>{p.label}</td>
                  {roles.data.roles.map((r) => {
                    const yes = r.permissions.includes(p.key);
                    return <td key={r.key} style={{ textAlign: "center", color: yes ? "var(--success)" : "var(--ink-muted)" }}><span aria-label={yes ? "ทำได้" : "ทำไม่ได้"}>{yes ? "✓" : "—"}</span></td>;
                  })}
                </tr>
              ))}
              <tr><td className="bold">ภาพรวม</td>{roles.data.roles.map((r) => <td key={r.key} className="xs ink-muted" style={{ whiteSpace: "normal", minWidth: 150 }}>{r.description}</td>)}</tr>
            </tbody>
          </table>
        </div>
      )}

      {tab === "audit" && (
        <div className="mh-tablewrap">
          <table className="mh-table">
            <thead><tr><th>เมื่อ</th><th>ใคร</th><th>ทำอะไร</th><th>รายการ</th><th>รายละเอียด</th><th>IP</th></tr></thead>
            <tbody>
              {audit.data?.map((a, i) => (
                <tr key={i}>
                  <td className="xs">{when(a.created_at)}</td><td>{a.actor}</td><td>{ACTION_LABEL[a.action] ?? a.action}</td>
                  <td className="mh-code">{a.target}</td><td style={{ whiteSpace: "normal", maxWidth: 320 }}>{a.detail}</td><td className="xs ink-muted">{a.ip}</td>
                </tr>
              ))}
              {audit.data?.length === 0 && <tr><td colSpan={6} className="ink-muted">ยังไม่มีประวัติ</td></tr>}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
