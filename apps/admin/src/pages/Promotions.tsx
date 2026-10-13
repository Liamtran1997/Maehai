import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { ErrorNotice } from "../components/Notice";
import { api, bahtToSatang, unwrap, type Promotion, type PromotionIn } from "../lib/api";
import { useAuth } from "../lib/auth";

const STATE: Record<string, { label: string; cls: string; glyph: string }> = {
  running: { label: "กำลังใช้", cls: "done", glyph: "●" },
  scheduled: { label: "ตั้งเวลาไว้", cls: "paid", glyph: "○" },
  ended: { label: "หมดเวลาแล้ว", cls: "wait", glyph: "✓" },
  off: { label: "ปิดอยู่", cls: "cancel", glyph: "✕" },
};
const SCOPE_LABEL: Record<string, string> = { products: "สินค้าที่เลือก", categories: "ทั้งหมวดหมู่", all: "สินค้าทุกชิ้น" };

/** <input type="datetime-local"> works in the browser's local time (Thailand for the shop's staff). */
const toLocalInput = (iso?: string | null) => {
  if (!iso) return "";
  const d = new Date(iso);
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
};
const fromLocalInput = (v: string) => (v ? new Date(v).toISOString() : null);
const show = (iso?: string | null) => (iso ? new Date(iso).toLocaleString("th-TH", { dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Bangkok" }) : "ไม่กำหนด");

type Form = { id?: number; name: string; kind: string; value: string; scope: string; product_ids: number[]; category_ids: number[]; starts: string; ends: string; is_active: boolean };
const blank = (): Form => ({ name: "", kind: "percent", value: "", scope: "products", product_ids: [], category_ids: [], starts: toLocalInput(new Date().toISOString()), ends: "", is_active: true });
const fromPromo = (p: Promotion): Form => ({ id: p.id, name: p.name, kind: p.kind, value: p.kind === "percent" ? String(p.value) : String(p.value / 100), scope: p.scope,
  product_ids: p.product_ids, category_ids: p.category_ids, starts: toLocalInput(p.starts_at), ends: toLocalInput(p.ends_at), is_active: p.is_active });

function toPayload(f: Form): PromotionIn | string {
  if (!f.name.trim()) return "ตั้งชื่อโปรโมชัน (ลูกค้าเห็นชื่อนี้)";
  const value = f.kind === "percent" ? parseInt(f.value, 10) : bahtToSatang(f.value);
  if (f.kind === "percent" && !(Number.isInteger(value) && value! >= 1 && value! <= 90)) return "ลดได้ 1 ถึง 90 เปอร์เซ็นต์";
  if (f.kind === "amount" && (value === null || value === 0)) return "กรอกจำนวนเงินที่ลด";
  if (!f.starts) return "เลือกวันเริ่ม";
  if (f.ends && new Date(f.ends) <= new Date(f.starts)) return "วันสิ้นสุดต้องอยู่หลังวันเริ่ม";
  if (f.scope === "products" && f.product_ids.length === 0) return "เลือกสินค้าอย่างน้อย 1 รายการ";
  if (f.scope === "categories" && f.category_ids.length === 0) return "เลือกหมวดหมู่อย่างน้อย 1 หมวด";
  return { name: f.name.trim(), kind: f.kind, value: value!, scope: f.scope, product_ids: f.product_ids, category_ids: f.category_ids,
    starts_at: fromLocalInput(f.starts)!, ends_at: fromLocalInput(f.ends), is_active: f.is_active };
}

export function Promotions() {
  const qc = useQueryClient();
  const canManage = useAuth().can("pricing.manage");
  const promos = useQuery({ queryKey: ["promotions"], queryFn: async () => unwrap(await api.GET("/api/admin/catalog/promotions")) });
  const products = useQuery({ queryKey: ["admin-products"], queryFn: async () => unwrap(await api.GET("/api/admin/catalog/products")) });
  const cats = useQuery({ queryKey: ["admin-categories"], queryFn: async () => unwrap(await api.GET("/api/admin/catalog/categories")) });
  const [form, setForm] = useState<Form | null>(null);
  const [pq, setPq] = useState("");
  const refresh = () => { void qc.invalidateQueries({ queryKey: ["promotions"] }); void qc.invalidateQueries({ queryKey: ["admin-products"] }); };

  const save = useMutation({
    mutationFn: async (f: Form) => {
      const body = toPayload(f);
      if (typeof body === "string") throw new Error(body);
      return f.id
        ? unwrap(await api.PUT("/api/admin/catalog/promotions/{promotion_id}", { params: { path: { promotion_id: f.id } }, body }))
        : unwrap(await api.POST("/api/admin/catalog/promotions", { body }));
    },
    onSuccess: (p) => { setForm(fromPromo(p)); refresh(); },
  });
  const end = useMutation({
    mutationFn: async (id: number) => unwrap(await api.POST("/api/admin/catalog/promotions/{promotion_id}/end", { params: { path: { promotion_id: id } } })),
    onSuccess: refresh,
  });
  const saved = promos.data?.find((p) => p.id === form?.id);
  const nameOf = (ids: number[], list?: { id: number; name: string }[]) => ids.map((i) => list?.find((x) => x.id === i)?.name).filter(Boolean).join(", ");
  const onSubmit = (e: FormEvent) => { e.preventDefault(); if (form) save.mutate(form); };
  const toggleId = (k: "product_ids" | "category_ids", id: number) => setForm((f) => f && { ...f, [k]: f[k].includes(id) ? f[k].filter((x) => x !== id) : [...f[k], id] });

  return (
    <>
      <div className="page-head">
        <div><h1>โปรโมชัน</h1><p>ส่วนลดที่ตั้งจากราคาปกติ ตั้งช่วงเวลาและเงื่อนไขได้ที่นี่</p></div>
        {canManage && <div className="actions"><button className="mh-btn mh-btn--primary mh-btn--sm" onClick={() => { save.reset(); setForm(blank()); }}>สร้างโปรโมชัน</button></div>}
      </div>
      <p className="sm ink-muted">ส่วนลดไม่ซ้อนกัน ถ้าสินค้าอยู่ในหลายโปรโมชันพร้อมกัน ลูกค้าได้ส่วนลดที่มากที่สุดเพียงอันเดียว ราคาในคำสั่งซื้อจะถูกบันทึกตอนสั่ง ปิดโปรโมชันภายหลังไม่กระทบคำสั่งซื้อเก่า</p>
      <ErrorNotice error={promos.error ?? end.error} />
      <div className="cols cols--2-1" style={{ alignItems: "start" }}>
        <div className="mh-tablewrap">
          <table className="mh-table">
            <thead><tr><th>โปรโมชัน</th><th>ส่วนลด</th><th>ใช้กับ</th><th>ช่วงเวลา</th><th>สถานะ</th><th /></tr></thead>
            <tbody>
              {promos.data?.map((p) => (
                <tr key={p.id} className={form?.id === p.id ? "sel" : ""}>
                  <td className="bold" style={{ whiteSpace: "normal" }}>{p.name}</td>
                  <td>{p.label}</td>
                  <td style={{ whiteSpace: "normal", maxWidth: 220 }}>{p.scope === "all" ? "สินค้าทุกชิ้น" : p.scope === "products" ? nameOf(p.product_ids, products.data) : nameOf(p.category_ids, cats.data)}</td>
                  <td className="xs">{show(p.starts_at)}<br />ถึง {show(p.ends_at)}</td>
                  <td><span className={`mh-status mh-status--${STATE[p.state].cls}`} data-glyph={STATE[p.state].glyph}>{STATE[p.state].label}</span></td>
                  <td className="mh-row" style={{ gap: 8 }}>
                    {canManage && <button className="mh-btn mh-btn--secondary mh-btn--sm" onClick={() => { save.reset(); setForm(fromPromo(p)); }}>แก้ไข</button>}
                    {canManage && (p.state === "running" || p.state === "scheduled") && <button className="mh-btn mh-btn--secondary mh-btn--sm" disabled={end.isPending} onClick={() => end.mutate(p.id)}>ปิดตอนนี้</button>}
                  </td>
                </tr>
              ))}
              {promos.data?.length === 0 && <tr><td colSpan={6} className="ink-muted">ยังไม่มีโปรโมชัน</td></tr>}
            </tbody>
          </table>
        </div>

        {form && (
          <form className="apanel" onSubmit={onSubmit}>
            <div className="apanel-head"><h2>{form.id ? "แก้ไขโปรโมชัน" : "สร้างโปรโมชัน"}</h2><button type="button" className="mh-btn mh-btn--secondary mh-btn--sm" onClick={() => setForm(null)}>ปิด</button></div>
            <div className="mh-field"><label className="mh-label" htmlFor="mn">ชื่อโปรโมชัน</label><input className="mh-input" id="mn" maxLength={100} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="เช่น ลดรับสงกรานต์" /><span className="mh-help">ลูกค้าเห็นชื่อนี้บนหน้าสินค้า</span></div>
            <div className="form-grid">
              <div className="mh-field"><label className="mh-label" htmlFor="mk">ลดแบบ</label><select className="mh-select" id="mk" value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}><option value="percent">เปอร์เซ็นต์</option><option value="amount">จำนวนเงินต่อชิ้น</option></select></div>
              <div className="mh-field"><label className="mh-label" htmlFor="mv">{form.kind === "percent" ? "ลดกี่ % (1 ถึง 90)" : "ลดชิ้นละ (บาท)"}</label><input className="mh-input num" id="mv" inputMode="decimal" value={form.value} onChange={(e) => setForm({ ...form, value: e.target.value })} /></div>
            </div>
            <div className="mh-field"><label className="mh-label" htmlFor="msc">ใช้กับ</label><select className="mh-select" id="msc" value={form.scope} onChange={(e) => setForm({ ...form, scope: e.target.value })}>{Object.entries(SCOPE_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></div>
            {form.scope === "products" && (
              <fieldset className="mh-field" style={{ border: 0, margin: 0, padding: 0 }}>
                <legend className="mh-label" style={{ marginBottom: 8 }}>เลือกสินค้า ({form.product_ids.length})</legend>
                <input className="mh-input" aria-label="ค้นหาสินค้าในรายการ" placeholder="ค้นหาสินค้า" value={pq} onChange={(e) => setPq(e.target.value)} />
                <div style={{ maxHeight: 220, overflowY: "auto", border: "1px solid var(--line)", borderRadius: 8, padding: 8, display: "flex", flexDirection: "column", gap: 4 }}>
                  {products.data?.filter((p) => !pq || p.name.includes(pq)).map((p) => (
                    <label key={p.id} className="mh-row" style={{ gap: 8 }}><input type="checkbox" checked={form.product_ids.includes(p.id)} onChange={() => toggleId("product_ids", p.id)} style={{ width: 18, height: 18, accentColor: "var(--leaf)" }} />{p.name}{!p.is_active && <span className="xs ink-muted"> (ซ่อนอยู่)</span>}</label>
                  ))}
                </div>
              </fieldset>
            )}
            {form.scope === "categories" && (
              <fieldset className="mh-field" style={{ border: 0, margin: 0, padding: 0 }}>
                <legend className="mh-label" style={{ marginBottom: 8 }}>เลือกหมวดหมู่</legend>
                {cats.data?.map((c) => (
                  <label key={c.id} className="mh-row" style={{ gap: 8 }}><input type="checkbox" checked={form.category_ids.includes(c.id)} onChange={() => toggleId("category_ids", c.id)} style={{ width: 18, height: 18, accentColor: "var(--leaf)" }} />{c.name} <span className="xs ink-muted">({c.product_count} สินค้า)</span></label>
                ))}
              </fieldset>
            )}
            <div className="form-grid">
              <div className="mh-field"><label className="mh-label" htmlFor="ms">เริ่ม</label><input className="mh-input" id="ms" type="datetime-local" value={form.starts} onChange={(e) => setForm({ ...form, starts: e.target.value })} /></div>
              <div className="mh-field"><label className="mh-label" htmlFor="me">สิ้นสุด (ว่าง = จนกว่าจะปิด)</label><input className="mh-input" id="me" type="datetime-local" value={form.ends} onChange={(e) => setForm({ ...form, ends: e.target.value })} /></div>
            </div>
            <label className="mh-row" style={{ gap: 8 }}><input type="checkbox" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} style={{ width: 20, height: 20, accentColor: "var(--leaf)" }} /> เปิดใช้</label>
            {saved?.warnings.map((w) => <div key={w} className="notice notice--warn"><p>{w}</p></div>)}
            <ErrorNotice error={save.error} />
            {save.isSuccess && <div className="notice notice--ok" role="status"><p>บันทึกแล้ว</p></div>}
            <button className="mh-btn mh-btn--primary" type="submit" disabled={save.isPending}>{save.isPending ? "กำลังบันทึก…" : "บันทึก"}</button>
          </form>
        )}
      </div>
    </>
  );
}
