import { formatTHB } from "@maehai/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { ErrorNotice } from "../components/Notice";
import { api, bahtToSatang, unwrap, type AdminProduct, type ProductIn } from "../lib/api";

type VariantForm = { sku: string; label: string; price: string; weight: string; is_active: boolean };
type Form = Omit<ProductIn, "variants" | "bands"> & { bands: string[]; variants: VariantForm[]; id?: number };

const BANDS = [{ v: "yellow", l: "ยางเหลือง" }, { v: "red", l: "ยางแดง" }, { v: "green", l: "ยางเขียว" }];
const BADGES = [{ v: "", l: "ไม่มี" }, { v: "best_seller", l: "ขายดี" }, { v: "new", l: "ใหม่" }];

const blank = (category: string): Form => ({
  category_slug: category, slug: "", name: "", name_en: "", subtitle: "", description: "", bands: [], badge: "",
  fda_number: "", storage_note: "", is_active: true, variants: [{ sku: "", label: "", price: "", weight: "", is_active: true }],
});

const fromProduct = (p: AdminProduct): Form => ({
  id: p.id, category_slug: p.category.slug, slug: p.slug, name: p.name, name_en: "", subtitle: p.subtitle, description: p.description,
  bands: p.bands, badge: p.badge, fda_number: p.fda_number, storage_note: p.storage_note, is_active: p.is_active,
  variants: p.variants.map((v) => ({ sku: v.sku, label: v.label, price: String(v.price_satang / 100), weight: v.weight_grams ? String(v.weight_grams) : "", is_active: true })),
});

/** Validates the form and builds the API payload, or returns a Thai error. */
function toPayload(f: Form): ProductIn | string {
  if (!f.name.trim()) return "กรอกชื่อสินค้า";
  if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(f.slug)) return "slug ใช้ตัวอักษรอังกฤษพิมพ์เล็ก ตัวเลข และขีดกลางเท่านั้น เช่น moo-yo-garlic";
  const variants: ProductIn["variants"] = [];
  for (const v of f.variants) {
    const price = bahtToSatang(v.price);
    if (!v.label.trim() || !v.sku.trim()) return "ทุกขนาดต้องมีชื่อขนาดและรหัส SKU";
    if (price === null || price === 0) return `ราคาของขนาด “${v.label}” ไม่ถูกต้อง`;
    const w = v.weight.trim() ? parseInt(v.weight, 10) : null;
    if (w !== null && (!Number.isFinite(w) || w <= 0)) return `น้ำหนักของขนาด “${v.label}” ไม่ถูกต้อง`;
    variants.push({ label: v.label.trim(), sku: v.sku.trim(), price_satang: price, weight_grams: w, is_active: true });
  }
  const { id: _id, variants: _v, ...rest } = f;
  return { ...rest, variants };
}

export function Products() {
  const qc = useQueryClient();
  const products = useQuery({ queryKey: ["admin-products"], queryFn: async () => unwrap(await api.GET("/api/admin/catalog/products")) });
  const cats = useQuery({ queryKey: ["admin-categories"], queryFn: async () => unwrap(await api.GET("/api/admin/catalog/categories")) });
  const [form, setForm] = useState<Form | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: async (f: Form) => {
      const body = toPayload(f);
      if (typeof body === "string") throw new Error(body);
      return f.id
        ? unwrap(await api.PUT("/api/admin/catalog/products/{product_id}", { params: { path: { product_id: f.id } }, body }))
        : unwrap(await api.POST("/api/admin/catalog/products", { body }));
    },
    onSuccess: () => { setForm(null); setFormError(null); void qc.invalidateQueries({ queryKey: ["admin-products"] }); },
    onError: (e) => setFormError(e instanceof Error ? e.message : "บันทึกไม่สำเร็จ"),
  });
  const toggle = useMutation({
    mutationFn: async (p: AdminProduct) => {
      const f = fromProduct(p);
      const body = toPayload({ ...f, is_active: !p.is_active });
      if (typeof body === "string") throw new Error(body);
      return unwrap(await api.PUT("/api/admin/catalog/products/{product_id}", { params: { path: { product_id: p.id } }, body }));
    },
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["admin-products"] }),
  });

  const set = <K extends keyof Form>(k: K, v: Form[K]) => setForm((f) => (f ? { ...f, [k]: v } : f));
  const setVariant = (i: number, patch: Partial<VariantForm>) => setForm((f) => f && { ...f, variants: f.variants.map((v, j) => (j === i ? { ...v, ...patch } : v)) });
  const onSubmit = (e: FormEvent) => { e.preventDefault(); setFormError(null); if (form) save.mutate(form); };

  return (
    <>
      <div className="topbar">
        <h1>สินค้า</h1>
        <button className="mh-btn mh-btn--primary mh-btn--sm" onClick={() => { setFormError(null); setForm(blank(cats.data?.[0]?.slug ?? "")); }}>เพิ่มสินค้า</button>
      </div>
      <ErrorNotice error={products.error ?? toggle.error} />
      <div className="cols cols--2-1" style={{ alignItems: "start" }}>
        <div className="mh-tablewrap">
          <table className="mh-table">
            <thead><tr><th>สินค้า</th><th>หมวดหมู่</th><th className="r">ราคา</th><th>แสดงบนร้าน</th><th><span style={{ position: "absolute", left: -9999 }}>แก้ไข</span></th></tr></thead>
            <tbody>
              {products.data?.map((p) => {
                const prices = p.variants.map((v) => v.price_satang);
                const lo = Math.min(...prices), hi = Math.max(...prices);
                return (
                  <tr key={p.id} className={form?.id === p.id ? "sel" : ""}>
                    <td><span className="bold">{p.name}</span><br /><span className="xs ink-muted">{p.subtitle || p.slug} · {p.variants.length} ขนาด</span></td>
                    <td>{p.category.name}</td>
                    <td className="r">{prices.length === 0 ? "—" : lo === hi ? formatTHB(lo, { hideZeroSatang: true }) : `${formatTHB(lo, { hideZeroSatang: true })} ถึง ${formatTHB(hi, { hideZeroSatang: true })}`}</td>
                    <td><button className="mh-chip" style={{ minHeight: 32 }} aria-pressed={p.is_active} disabled={toggle.isPending} onClick={() => toggle.mutate(p)}>{p.is_active ? "แสดง" : "ซ่อน"}</button></td>
                    <td><button className="mh-btn mh-btn--secondary mh-btn--sm" onClick={() => { setFormError(null); setForm(fromProduct(p)); }}>แก้ไข</button></td>
                  </tr>
                );
              })}
              {products.data?.length === 0 && <tr><td colSpan={5} className="ink-muted">ยังไม่มีสินค้า</td></tr>}
            </tbody>
          </table>
        </div>

        {form && (
          <form className="apanel" onSubmit={onSubmit}>
            <div className="apanel-head"><h2>{form.id ? "แก้ไขสินค้า" : "เพิ่มสินค้า"}</h2><button type="button" className="mh-btn mh-btn--secondary mh-btn--sm" onClick={() => setForm(null)}>ปิด</button></div>
            <div className="mh-field"><label className="mh-label" htmlFor="pn">ชื่อสินค้า</label><input className="mh-input" id="pn" value={form.name} onChange={(e) => set("name", e.target.value)} required /></div>
            <div className="mh-field"><label className="mh-label" htmlFor="ps">slug (ที่อยู่หน้าสินค้า)</label><input className="mh-input" id="ps" value={form.slug} onChange={(e) => set("slug", e.target.value)} placeholder="moo-yo-garlic" required /><span className="mh-help">{form.id ? "เปลี่ยนแล้วลิงก์เดิมของสินค้านี้จะใช้ไม่ได้" : "ตั้งครั้งเดียว ใช้อักษรอังกฤษพิมพ์เล็กและขีดกลาง"}</span></div>
            <div className="form-grid">
              <div className="mh-field"><label className="mh-label" htmlFor="pc">หมวดหมู่</label><select className="mh-select" id="pc" value={form.category_slug} onChange={(e) => set("category_slug", e.target.value)}>{cats.data?.map((c) => <option key={c.slug} value={c.slug}>{c.name}</option>)}</select></div>
              <div className="mh-field"><label className="mh-label" htmlFor="pb">ป้าย</label><select className="mh-select" id="pb" value={form.badge} onChange={(e) => set("badge", e.target.value)}>{BADGES.map((b) => <option key={b.v} value={b.v}>{b.l}</option>)}</select></div>
            </div>
            <fieldset style={{ border: 0, margin: 0, padding: 0 }}>
              <legend className="mh-label" style={{ marginBottom: 8 }}>สีของยางรัด</legend>
              <div className="mh-chips">{BANDS.map((b) => <button type="button" key={b.v} className="mh-chip" aria-pressed={form.bands.includes(b.v)} onClick={() => set("bands", form.bands.includes(b.v) ? form.bands.filter((x) => x !== b.v) : [...form.bands, b.v])}>{b.l}</button>)}</div>
            </fieldset>
            <div className="mh-field"><label className="mh-label" htmlFor="psub">คำบรรยายสั้น</label><input className="mh-input" id="psub" value={form.subtitle} onChange={(e) => set("subtitle", e.target.value)} /></div>
            <div className="mh-field"><label className="mh-label" htmlFor="pd">รายละเอียด</label><textarea className="mh-textarea" id="pd" value={form.description} onChange={(e) => set("description", e.target.value)} /></div>
            <div className="form-grid">
              <div className="mh-field"><label className="mh-label" htmlFor="pf">เลข อย.</label><input className="mh-input" id="pf" value={form.fda_number} onChange={(e) => set("fda_number", e.target.value)} /></div>
              <div className="mh-field"><label className="mh-label" htmlFor="pst">การเก็บรักษา</label><input className="mh-input" id="pst" value={form.storage_note} onChange={(e) => set("storage_note", e.target.value)} /></div>
            </div>

            <div>
              <p className="mh-label" style={{ marginBottom: 8 }}>ขนาดและราคา</p>
              <div className="mh-tablewrap">
                <table className="mh-table">
                  <thead><tr><th>ขนาด</th><th>SKU</th><th className="r">ราคา (บาท)</th><th className="r">น้ำหนัก (กรัม)</th><th /></tr></thead>
                  <tbody>
                    {form.variants.map((v, i) => (
                      <tr key={i}>
                        <td><input className="mh-input" aria-label="ชื่อขนาด" style={{ minWidth: 90 }} value={v.label} onChange={(e) => setVariant(i, { label: e.target.value })} /></td>
                        <td><input className="mh-input" aria-label="SKU" style={{ minWidth: 120 }} value={v.sku} disabled={!!form.id && !!v.sku && products.data?.some((p) => p.id === form.id && p.variants.some((x) => x.sku === v.sku))} onChange={(e) => setVariant(i, { sku: e.target.value })} /></td>
                        <td><input className="mh-input num" aria-label="ราคา" style={{ minWidth: 90, textAlign: "right" }} inputMode="decimal" value={v.price} onChange={(e) => setVariant(i, { price: e.target.value })} /></td>
                        <td><input className="mh-input num" aria-label="น้ำหนัก" style={{ minWidth: 90, textAlign: "right" }} inputMode="numeric" value={v.weight} onChange={(e) => setVariant(i, { weight: e.target.value })} /></td>
                        <td><button type="button" className="mh-btn mh-btn--secondary mh-btn--sm" disabled={form.variants.length === 1} aria-label={`ลบขนาด ${v.label}`} onClick={() => set("variants", form.variants.filter((_, j) => j !== i))}>ลบ</button></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <button type="button" className="mh-btn mh-btn--secondary mh-btn--sm" style={{ marginTop: 8 }} onClick={() => set("variants", [...form.variants, { sku: "", label: "", price: "", weight: "", is_active: true }])}>เพิ่มขนาด</button>
              <p className="xs ink-muted" style={{ marginTop: 8 }}>ขนาดที่ลบออกจะหยุดขาย แต่ไม่หายจากคำสั่งซื้อเก่า</p>
            </div>

            {formError && <div className="notice notice--warn" role="alert"><p>{formError}</p></div>}
            <div className="mh-row" style={{ justifyContent: "flex-end" }}>
              <button type="button" className="mh-btn mh-btn--secondary mh-btn--sm" onClick={() => setForm(null)}>ยกเลิก</button>
              <button type="submit" className="mh-btn mh-btn--primary mh-btn--sm" disabled={save.isPending}>{save.isPending ? "กำลังบันทึก…" : "บันทึก"}</button>
            </div>
          </form>
        )}
      </div>
    </>
  );
}
