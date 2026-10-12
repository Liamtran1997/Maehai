import { formatTHB } from "@maehai/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { ErrorNotice } from "../components/Notice";
import { api, bahtToSatang, unwrap, type Coupon, type CouponIn } from "../lib/api";
import { useAuth } from "../lib/auth";

const STATE: Record<string, { label: string; cls: string; glyph: string }> = {
  running: { label: "ใช้ได้", cls: "done", glyph: "●" },
  scheduled: { label: "ตั้งเวลาไว้", cls: "paid", glyph: "○" },
  ended: { label: "หมดเวลาแล้ว", cls: "wait", glyph: "✓" },
  exhausted: { label: "ใช้ครบแล้ว", cls: "wait", glyph: "◐" },
  off: { label: "ปิดอยู่", cls: "cancel", glyph: "✕" },
};

const toLocalInput = (iso?: string | null) => {
  if (!iso) return "";
  const d = new Date(iso);
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
};
const fromLocalInput = (v: string) => (v ? new Date(v).toISOString() : null);
const show = (iso?: string | null) => (iso ? new Date(iso).toLocaleString("th-TH", { dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Bangkok" }) : "ไม่กำหนด");
const baht = (satang: number) => String(satang / 100);

type Form = {
  id?: number; code: string; name: string; kind: string; value: string; max_discount: string; min_subtotal: string;
  exclude_discounted_items: boolean; usage_limit: string; per_phone_limit: string; starts: string; ends: string; is_active: boolean;
};

const randomCode = () => {
  const chars = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"; // no look-alikes (0/O, 1/I/L)
  const buf = new Uint32Array(6);
  crypto.getRandomValues(buf);
  return Array.from(buf, (n) => chars[n % chars.length]).join("");
};
const blank = (): Form => ({ code: "", name: "", kind: "percent", value: "", max_discount: "", min_subtotal: "", exclude_discounted_items: false,
  usage_limit: "", per_phone_limit: "1", starts: toLocalInput(new Date().toISOString()), ends: "", is_active: true });
const fromCoupon = (c: Coupon): Form => ({ id: c.id, code: c.code, name: c.name, kind: c.kind, value: c.kind === "percent" ? String(c.value) : baht(c.value),
  max_discount: c.max_discount_satang ? baht(c.max_discount_satang) : "", min_subtotal: c.min_subtotal_satang ? baht(c.min_subtotal_satang) : "",
  exclude_discounted_items: c.exclude_discounted_items, usage_limit: c.usage_limit ? String(c.usage_limit) : "",
  per_phone_limit: c.per_phone_limit ? String(c.per_phone_limit) : "", starts: toLocalInput(c.starts_at), ends: toLocalInput(c.ends_at), is_active: c.is_active });

const posInt = (t: string) => (/^\d+$/.test(t.trim()) && parseInt(t, 10) > 0 ? parseInt(t, 10) : null);

function toPayload(f: Form): CouponIn | string {
  const code = f.code.trim().toUpperCase();
  if (!/^[A-Z0-9][A-Z0-9-]{1,23}$/.test(code)) return "โค้ดใช้ตัวอักษร A-Z ตัวเลข และขีดกลาง ยาว 2 ถึง 24 ตัว";
  if (!f.name.trim()) return "ตั้งชื่อโค้ด (สำหรับจำภายในร้าน)";
  const value = f.kind === "free_shipping" ? 1 : f.kind === "percent" ? posInt(f.value) : bahtToSatang(f.value);
  if (f.kind === "percent" && (value === null || value > 90)) return "ลดได้ 1 ถึง 90 เปอร์เซ็นต์";
  if (f.kind === "amount" && (value === null || value === 0)) return "กรอกจำนวนเงินที่ลด";
  const max = f.max_discount.trim() ? bahtToSatang(f.max_discount) : null;
  if (f.kind === "percent" && f.max_discount.trim() && (max === null || max === 0)) return "เพดานส่วนลดต้องเป็นจำนวนเงิน";
  const min = f.min_subtotal.trim() ? bahtToSatang(f.min_subtotal) : 0;
  if (min === null) return "ยอดขั้นต่ำต้องเป็นจำนวนเงิน";
  const usage = f.usage_limit.trim() ? posInt(f.usage_limit) : null;
  if (f.usage_limit.trim() && usage === null) return "จำนวนครั้งรวมต้องเป็นตัวเลขมากกว่า 0";
  const perPhone = f.per_phone_limit.trim() ? posInt(f.per_phone_limit) : null;
  if (f.per_phone_limit.trim() && perPhone === null) return "จำนวนครั้งต่อเบอร์ต้องเป็นตัวเลขมากกว่า 0";
  if (!f.starts) return "เลือกวันเริ่ม";
  if (f.ends && new Date(f.ends) <= new Date(f.starts)) return "วันสิ้นสุดต้องอยู่หลังวันเริ่ม";
  return { code, name: f.name.trim(), kind: f.kind, value: value!, max_discount_satang: f.kind === "percent" ? max : null, min_subtotal_satang: min,
    exclude_discounted_items: f.exclude_discounted_items, usage_limit: usage, per_phone_limit: perPhone, starts_at: fromLocalInput(f.starts)!,
    ends_at: fromLocalInput(f.ends), is_active: f.is_active };
}

export function Coupons() {
  const qc = useQueryClient();
  const canManage = useAuth().can("pricing.manage");
  const list = useQuery({ queryKey: ["coupons"], queryFn: async () => unwrap(await api.GET("/api/admin/coupons")) });
  const [form, setForm] = useState<Form | null>(null);
  const [historyOf, setHistoryOf] = useState<Coupon | null>(null);
  const history = useQuery({ queryKey: ["coupon-uses", historyOf?.id], enabled: !!historyOf,
    queryFn: async () => unwrap(await api.GET("/api/admin/coupons/{coupon_id}/redemptions", { params: { path: { coupon_id: historyOf!.id } } })) });
  const refresh = () => void qc.invalidateQueries({ queryKey: ["coupons"] });

  const save = useMutation({
    mutationFn: async (f: Form) => {
      const body = toPayload(f);
      if (typeof body === "string") throw new Error(body);
      return f.id
        ? unwrap(await api.PUT("/api/admin/coupons/{coupon_id}", { params: { path: { coupon_id: f.id } }, body }))
        : unwrap(await api.POST("/api/admin/coupons", { body }));
    },
    onSuccess: (c) => { setForm(fromCoupon(c)); refresh(); },
  });
  const end = useMutation({
    mutationFn: async (id: number) => unwrap(await api.POST("/api/admin/coupons/{coupon_id}/end", { params: { path: { coupon_id: id } } })),
    onSuccess: refresh,
  });
  const remove = useMutation({
    mutationFn: async (id: number) => unwrap(await api.DELETE("/api/admin/coupons/{coupon_id}", { params: { path: { coupon_id: id } } })),
    onSuccess: () => { setForm(null); refresh(); },
  });
  const set = <K extends keyof Form>(k: K, v: Form[K]) => setForm((f) => (f ? { ...f, [k]: v } : f));
  const onSubmit = (e: FormEvent) => { e.preventDefault(); if (form) save.mutate(form); };
  const open = (f: Form) => { save.reset(); remove.reset(); setForm(f); };
  const editing = list.data?.find((c) => c.id === form?.id);

  return (
    <>
      <div className="topbar"><h1>โค้ดส่วนลด</h1>{canManage && <button className="mh-btn mh-btn--primary mh-btn--sm" onClick={() => open({ ...blank(), code: randomCode() })}>สร้างโค้ด</button>}</div>
      <p className="sm ink-muted">ลูกค้ากรอกโค้ดตอนสั่งซื้อ ส่วนลดคิดจากยอดสินค้าหลังหักโปรโมชันรายสินค้าแล้ว ไม่รวมค่าจัดส่ง ใช้ร่วมกับโปรโมชันรายสินค้าได้ (หรือเลือกไม่ให้ใช้กับสินค้าที่ลดอยู่แล้ว) ยกเลิกคำสั่งซื้อจะคืนสิทธิ์การใช้โค้ด</p>
      <ErrorNotice error={list.error ?? end.error} />
      <div className="cols cols--2-1" style={{ alignItems: "start" }}>
        <div className="mh-tablewrap">
          <table className="mh-table">
            <thead><tr><th>โค้ด</th><th>ส่วนลด</th><th className="r">ใช้แล้ว</th><th className="r">ลดไปแล้ว</th><th>ช่วงเวลา</th><th>สถานะ</th><th /></tr></thead>
            <tbody>
              {list.data?.map((c) => (
                <tr key={c.id} className={form?.id === c.id ? "sel" : ""}>
                  <td><span className="mh-code bold">{c.code}</span><br /><span className="xs ink-muted">{c.name}</span></td>
                  <td>{c.label}{c.min_subtotal_satang > 0 && <><br /><span className="xs ink-muted">ขั้นต่ำ {formatTHB(c.min_subtotal_satang, { hideZeroSatang: true })}</span></>}</td>
                  <td className="r">{c.used_count}{c.usage_limit ? ` / ${c.usage_limit}` : ""}</td>
                  <td className="r">{formatTHB(c.discount_given_satang, { hideZeroSatang: true })}</td>
                  <td className="xs">{show(c.starts_at)}<br />ถึง {show(c.ends_at)}</td>
                  <td><span className={`mh-status mh-status--${STATE[c.state].cls}`} data-glyph={STATE[c.state].glyph}>{STATE[c.state].label}</span></td>
                  <td className="mh-row" style={{ gap: 8 }}>
                    {canManage && <button className="mh-btn mh-btn--secondary mh-btn--sm" onClick={() => open(fromCoupon(c))}>แก้ไข</button>}
                    {c.used_count > 0 && <button className="mh-btn mh-btn--secondary mh-btn--sm" onClick={() => setHistoryOf(c)}>ประวัติ</button>}
                  </td>
                </tr>
              ))}
              {list.data?.length === 0 && <tr><td colSpan={7} className="ink-muted">ยังไม่มีโค้ดส่วนลด</td></tr>}
            </tbody>
          </table>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 16, minWidth: 0 }}>
          {form && (
            <form className="apanel" onSubmit={onSubmit}>
              <div className="apanel-head"><h2>{form.id ? "แก้ไขโค้ด" : "สร้างโค้ดส่วนลด"}</h2><button type="button" className="mh-btn mh-btn--secondary mh-btn--sm" onClick={() => setForm(null)}>ปิด</button></div>
              <div className="mh-field">
                <label className="mh-label" htmlFor="cc">โค้ด</label>
                <div className="mh-row" style={{ gap: 8, flexWrap: "nowrap" }}>
                  <input className="mh-input mh-code" id="cc" style={{ textTransform: "uppercase" }} maxLength={24} value={form.code} onChange={(e) => set("code", e.target.value)} disabled={!!editing && editing.used_count > 0} />
                  {!form.id && <button type="button" className="mh-btn mh-btn--secondary mh-btn--sm" style={{ whiteSpace: "nowrap" }} onClick={() => set("code", randomCode())}>สุ่มใหม่</button>}
                </div>
                <span className="mh-help">{editing && editing.used_count > 0 ? "โค้ดที่ถูกใช้แล้วเปลี่ยนตัวโค้ดไม่ได้" : "ลูกค้าพิมพ์ตัวเล็กตัวใหญ่ก็ได้ ตัวอักษร A-Z ตัวเลข และขีดกลาง"}</span>
              </div>
              <div className="mh-field"><label className="mh-label" htmlFor="cn">ชื่อ (ใช้ภายในร้าน)</label><input className="mh-input" id="cn" maxLength={100} value={form.name} onChange={(e) => set("name", e.target.value)} placeholder="เช่น แจกลูกค้าเก่า ต.ค." /></div>
              <div className="form-grid">
                <div className="mh-field"><label className="mh-label" htmlFor="ck">ลดแบบ</label><select className="mh-select" id="ck" value={form.kind} onChange={(e) => set("kind", e.target.value)}><option value="percent">เปอร์เซ็นต์</option><option value="amount">จำนวนเงินต่อออเดอร์</option><option value="free_shipping">ส่งฟรี (ยกเว้นค่าจัดส่ง)</option></select></div>
                {form.kind !== "free_shipping" && <div className="mh-field"><label className="mh-label" htmlFor="cv">{form.kind === "percent" ? "ลดกี่ % (1 ถึง 90)" : "ลดกี่บาท"}</label><input className="mh-input num" id="cv" inputMode="decimal" value={form.value} onChange={(e) => set("value", e.target.value)} /></div>}
              </div>
              {form.kind === "percent" && <div className="mh-field"><label className="mh-label" htmlFor="cm">ลดสูงสุดไม่เกิน (บาท, ไม่บังคับ)</label><input className="mh-input num" id="cm" inputMode="decimal" value={form.max_discount} onChange={(e) => set("max_discount", e.target.value)} placeholder="เช่น 100" /></div>}
              <div className="mh-field"><label className="mh-label" htmlFor="cmin">ยอดสินค้าขั้นต่ำ (บาท)</label><input className="mh-input num" id="cmin" inputMode="decimal" value={form.min_subtotal} onChange={(e) => set("min_subtotal", e.target.value)} placeholder="ไม่มีขั้นต่ำ" /><span className="mh-help">นับจากยอดสินค้าหลังโปรโมชัน ไม่รวมค่าจัดส่ง</span></div>
              <label className="mh-row" style={{ gap: 8 }}><input type="checkbox" checked={form.exclude_discounted_items} onChange={(e) => set("exclude_discounted_items", e.target.checked)} style={{ width: 20, height: 20, accentColor: "var(--leaf)" }} /> ไม่ใช้กับสินค้าที่ลดราคาอยู่แล้ว</label>
              <div className="form-grid">
                <div className="mh-field"><label className="mh-label" htmlFor="cu">ใช้ได้รวมกี่ครั้ง</label><input className="mh-input num" id="cu" inputMode="numeric" value={form.usage_limit} onChange={(e) => set("usage_limit", e.target.value)} placeholder="ไม่จำกัด" /></div>
                <div className="mh-field"><label className="mh-label" htmlFor="cp">ต่อเบอร์โทรกี่ครั้ง</label><input className="mh-input num" id="cp" inputMode="numeric" value={form.per_phone_limit} onChange={(e) => set("per_phone_limit", e.target.value)} placeholder="ไม่จำกัด" /></div>
              </div>
              <div className="form-grid">
                <div className="mh-field"><label className="mh-label" htmlFor="cs">เริ่ม</label><input className="mh-input" id="cs" type="datetime-local" value={form.starts} onChange={(e) => set("starts", e.target.value)} /></div>
                <div className="mh-field"><label className="mh-label" htmlFor="ce">สิ้นสุด (ว่าง = จนกว่าจะปิด)</label><input className="mh-input" id="ce" type="datetime-local" value={form.ends} onChange={(e) => set("ends", e.target.value)} /></div>
              </div>
              <label className="mh-row" style={{ gap: 8 }}><input type="checkbox" checked={form.is_active} onChange={(e) => set("is_active", e.target.checked)} style={{ width: 20, height: 20, accentColor: "var(--leaf)" }} /> เปิดใช้</label>
              <ErrorNotice error={save.error ?? remove.error} />
              {save.isSuccess && <div className="notice notice--ok" role="status"><p>บันทึกแล้ว</p></div>}
              <button className="mh-btn mh-btn--primary" type="submit" disabled={save.isPending}>{save.isPending ? "กำลังบันทึก…" : "บันทึก"}</button>
              {editing && (
                <div className="mh-row" style={{ gap: 8 }}>
                  {(editing.state === "running" || editing.state === "scheduled") && <button type="button" className="mh-btn mh-btn--secondary mh-btn--sm" disabled={end.isPending} onClick={() => end.mutate(editing.id)}>ปิดโค้ดตอนนี้</button>}
                  {editing.used_count === 0 && <button type="button" className="mh-btn mh-btn--secondary mh-btn--sm" disabled={remove.isPending} onClick={() => remove.mutate(editing.id)}>ลบโค้ด</button>}
                </div>
              )}
            </form>
          )}

          {historyOf && (
            <section className="apanel">
              <div className="apanel-head"><h2>ประวัติการใช้ {historyOf.code}</h2><button className="mh-btn mh-btn--secondary mh-btn--sm" onClick={() => setHistoryOf(null)}>ปิด</button></div>
              <div className="mh-tablewrap" style={{ border: 0 }}>
                <table className="mh-table">
                  <thead><tr><th>คำสั่งซื้อ</th><th>เบอร์โทร</th><th className="r">ลด</th><th>เมื่อ</th></tr></thead>
                  <tbody>
                    {history.data?.map((r) => (
                      <tr key={r.order_number}>
                        <td><a className="mh-code" href={`${import.meta.env.BASE_URL}orders/${r.order_number}`}>{r.order_number}</a>{r.released && <><br /><span className="xs ink-muted">ยกเลิก คืนสิทธิ์แล้ว</span></>}</td>
                        <td className="num">{r.phone}</td><td className="r">{formatTHB(r.discount_satang)}</td><td className="xs">{show(r.created_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}
        </div>
      </div>
    </>
  );
}
