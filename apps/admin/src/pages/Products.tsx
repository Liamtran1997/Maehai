import { LogMark, formatTHB } from "@maehai/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { ErrorNotice } from "../components/Notice";
import { api, bahtToSatang, unwrap, uploadFile, type AdminProduct, type ProductIn } from "../lib/api";

type VariantForm = { sku: string; label: string; price: string; weight: string; existing: boolean };
type Form = Omit<ProductIn, "variants"> & { variants: VariantForm[]; id?: number; image_url?: string | null };

const BANDS = [{ v: "yellow", l: "ยางเหลือง" }, { v: "red", l: "ยางแดง" }, { v: "green", l: "ยางเขียว" }];
const BADGES = [{ v: "", l: "ไม่มี" }, { v: "best_seller", l: "ขายดี" }, { v: "new", l: "ใหม่" }];
const STATUS = [{ v: "", l: "ทุกสถานะ" }, { v: "on", l: "แสดงบนร้าน" }, { v: "off", l: "ซ่อนอยู่" }, { v: "featured", l: "แสดงหน้าแรก" }, { v: "noimage", l: "ยังไม่มีรูป" }, { v: "promo", l: "มีโปรโมชัน" }];

const blankVariant = (): VariantForm => ({ sku: "", label: "", price: "", weight: "", existing: false });
const blank = (category: string): Form => ({
  category_slug: category, slug: "", name: "", name_en: "", subtitle: "", description: "", bands: [], badge: "",
  fda_number: "", storage_note: "", is_active: true, is_featured: false, sort_order: 0, variants: [blankVariant()],
});
const fromProduct = (p: AdminProduct): Form => ({
  id: p.id, image_url: p.image_url, category_slug: p.category.slug, slug: p.slug, name: p.name, name_en: p.name_en,
  subtitle: p.subtitle, description: p.description, bands: p.bands, badge: p.badge, fda_number: p.fda_number,
  storage_note: p.storage_note, is_active: p.is_active, is_featured: p.is_featured, sort_order: p.sort_order,
  variants: p.variants.map((v) => ({ sku: v.sku, label: v.label, price: String(v.price_satang / 100), weight: v.weight_grams ? String(v.weight_grams) : "", existing: true })),
});

/** Validates the form and builds the API payload, or returns a message for staff. */
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
  const { id: _id, image_url: _img, variants: _v, ...rest } = f;
  return { ...rest, variants };
}

function priceRange(p: AdminProduct) {
  const prices = p.variants.map((v) => v.price_satang);
  if (!prices.length) return "—";
  const lo = Math.min(...prices), hi = Math.max(...prices), f = (n: number) => formatTHB(n, { hideZeroSatang: true });
  return lo === hi ? f(lo) : `${f(lo)} ถึง ${f(hi)}`;
}

export function Products() {
  const qc = useQueryClient();
  const products = useQuery({ queryKey: ["admin-products"], queryFn: async () => unwrap(await api.GET("/api/admin/catalog/products")) });
  const cats = useQuery({ queryKey: ["admin-categories"], queryFn: async () => unwrap(await api.GET("/api/admin/catalog/categories")) });
  const [form, setForm] = useState<Form | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [cat, setCat] = useState("");
  const [status, setStatus] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const refresh = () => void qc.invalidateQueries({ queryKey: ["admin-products"] });

  const shown = useMemo(() => (products.data ?? []).filter((p) => {
    if (q && !`${p.name} ${p.name_en} ${p.slug}`.toLowerCase().includes(q.toLowerCase())) return false;
    if (cat && p.category.slug !== cat) return false;
    return status === "" || (status === "on" && p.is_active) || (status === "off" && !p.is_active)
      || (status === "featured" && p.is_featured) || (status === "noimage" && !p.image_url) || (status === "promo" && !!p.promotion_label);
  }), [products.data, q, cat, status]);

  const save = useMutation({
    mutationFn: async (f: Form) => {
      const body = toPayload(f);
      if (typeof body === "string") throw new Error(body);
      return f.id
        ? unwrap(await api.PUT("/api/admin/catalog/products/{product_id}", { params: { path: { product_id: f.id } }, body }))
        : unwrap(await api.POST("/api/admin/catalog/products", { body }));
    },
    // Keep the panel open on the saved product so a new product can get its photo straight away.
    onSuccess: (p) => { setForm(fromProduct(p)); setFormError(null); refresh(); },
    onError: (e) => setFormError(e instanceof Error ? e.message : "บันทึกไม่สำเร็จ"),
  });
  const upload = useMutation({
    mutationFn: async (file: File) => uploadFile<AdminProduct>(`/api/admin/catalog/products/${form!.id}/image`, "image", file),
    onSuccess: (p) => { setForm((f) => (f ? { ...f, image_url: p.image_url } : f)); refresh(); },
  });
  const removeImage = useMutation({
    mutationFn: async () => unwrap(await api.DELETE("/api/admin/catalog/products/{product_id}/image", { params: { path: { product_id: form!.id! } } })),
    onSuccess: () => { setForm((f) => (f ? { ...f, image_url: null } : f)); refresh(); },
  });
  const toggle = useMutation({
    mutationFn: async (p: AdminProduct) => {
      const body = toPayload({ ...fromProduct(p), is_active: !p.is_active });
      if (typeof body === "string") throw new Error(body);
      return unwrap(await api.PUT("/api/admin/catalog/products/{product_id}", { params: { path: { product_id: p.id } }, body }));
    },
    onSuccess: refresh,
  });

  const set = <K extends keyof Form>(k: K, v: Form[K]) => setForm((f) => (f ? { ...f, [k]: v } : f));
  const setVariant = (i: number, patch: Partial<VariantForm>) => setForm((f) => f && { ...f, variants: f.variants.map((v, j) => (j === i ? { ...v, ...patch } : v)) });
  const onSubmit = (e: FormEvent) => { e.preventDefault(); setFormError(null); if (form) save.mutate(form); };
  const open = (f: Form) => { setFormError(null); save.reset(); upload.reset(); setForm(f); };

  return (
    <>
      <div className="topbar">
        <h1>สินค้า</h1>
        <Link className="mh-btn mh-btn--secondary mh-btn--sm btn-link" to="/categories">จัดการหมวดหมู่</Link>
        <Link className="mh-btn mh-btn--secondary mh-btn--sm btn-link" to="/promotions">โปรโมชัน</Link>
        <button className="mh-btn mh-btn--primary mh-btn--sm" onClick={() => open(blank(cats.data?.[0]?.slug ?? ""))}>เพิ่มสินค้า</button>
      </div>
      <div className="toolbar">
        <div className="searchbox">
          <svg className="ic" viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="M20 20l-4-4" /></svg>
          <label htmlFor="pq" style={{ position: "absolute", left: -9999 }}>ค้นหาสินค้า</label>
          <input className="mh-input" id="pq" value={q} onChange={(e) => setQ(e.target.value)} placeholder="ค้นหาชื่อ หรือ slug" />
        </div>
        <select className="mh-select" style={{ width: "auto" }} aria-label="หมวดหมู่" value={cat} onChange={(e) => setCat(e.target.value)}>
          <option value="">ทุกหมวดหมู่</option>{cats.data?.map((c) => <option key={c.slug} value={c.slug}>{c.name}</option>)}
        </select>
        <select className="mh-select" style={{ width: "auto" }} aria-label="สถานะ" value={status} onChange={(e) => setStatus(e.target.value)}>
          {STATUS.map((s) => <option key={s.v} value={s.v}>{s.l}</option>)}
        </select>
        <span className="sm ink-muted">{shown.length} จาก {products.data?.length ?? 0} รายการ</span>
      </div>
      <ErrorNotice error={products.error ?? toggle.error} />

      <div className="cols cols--2-1" style={{ alignItems: "start" }}>
        <div className="mh-tablewrap">
          <table className="mh-table">
            <thead><tr><th>สินค้า</th><th>หมวดหมู่</th><th className="r">ราคา (ก่อนลด)</th><th>แสดงบนร้าน</th><th><span style={{ position: "absolute", left: -9999 }}>แก้ไข</span></th></tr></thead>
            <tbody>
              {shown.map((p) => (
                <tr key={p.id} className={form?.id === p.id ? "sel" : ""}>
                  <td>
                    <div className="name">
                      <span className="thumb-s">{p.image_url ? <img src={p.image_url} alt="" style={{ width: "100%", aspectRatio: "1", objectFit: "cover", borderRadius: 6 }} /> : <LogMark />}</span>
                      <span><span className="bold">{p.name}</span><br />
                        <span className="xs ink-muted">{p.variants.length} ขนาด{p.is_featured && " · หน้าแรก"}{!p.image_url && " · ไม่มีรูป"}</span>
                        {p.promotion_label && <><br /><span className="mh-status mh-status--cancel" data-glyph="%" style={{ fontSize: 12 }}>{p.promotion_label}</span></>}
                      </span>
                    </div>
                  </td>
                  <td>{p.category.name}</td>
                  <td className="r">{priceRange(p)}</td>
                  <td><button className="mh-chip" style={{ minHeight: 32 }} aria-pressed={p.is_active} disabled={toggle.isPending} onClick={() => toggle.mutate(p)}>{p.is_active ? "แสดง" : "ซ่อน"}</button></td>
                  <td><button className="mh-btn mh-btn--secondary mh-btn--sm" onClick={() => open(fromProduct(p))}>แก้ไข</button></td>
                </tr>
              ))}
              {products.data && shown.length === 0 && <tr><td colSpan={5} className="ink-muted">ไม่พบสินค้าตามที่กรอง</td></tr>}
            </tbody>
          </table>
        </div>

        {form && (
          <form className="apanel" onSubmit={onSubmit}>
            <div className="apanel-head"><h2>{form.id ? "แก้ไขสินค้า" : "เพิ่มสินค้า"}</h2><button type="button" className="mh-btn mh-btn--secondary mh-btn--sm" onClick={() => setForm(null)}>ปิด</button></div>

            <div className="mh-field">
              <span className="mh-label">รูปสินค้า</span>
              {form.id ? (
                <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
                  <div className="thumb-s" style={{ width: 96 }}>{form.image_url ? <img src={form.image_url} alt="รูปสินค้าปัจจุบัน" style={{ width: "100%", aspectRatio: "1", objectFit: "cover", borderRadius: 8 }} /> : <LogMark />}</div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                    <input ref={fileRef} type="file" accept="image/jpeg,image/png,image/webp" style={{ position: "absolute", left: -9999 }} id="pimg"
                      onChange={(e) => { const f = e.target.files?.[0]; if (f) upload.mutate(f); e.target.value = ""; }} />
                    <label htmlFor="pimg" className="mh-btn mh-btn--secondary mh-btn--sm" style={{ cursor: "pointer" }}>{upload.isPending ? "กำลังอัปโหลด…" : form.image_url ? "เปลี่ยนรูป" : "อัปโหลดรูป"}</label>
                    {form.image_url && <button type="button" className="mh-btn mh-btn--secondary mh-btn--sm" disabled={removeImage.isPending} onClick={() => removeImage.mutate()}>ลบรูป</button>}
                  </div>
                </div>
              ) : <span className="mh-help">บันทึกสินค้าก่อน แล้วจึงอัปโหลดรูปได้</span>}
              <span className="mh-help">JPG, PNG หรือ WebP ไม่เกิน 5 MB รูปสี่เหลี่ยมจัตุรัส พื้นหลังเรียบ</span>
              <ErrorNotice error={upload.error ?? removeImage.error} />
            </div>

            <div className="mh-field"><label className="mh-label" htmlFor="pn">ชื่อสินค้า</label><input className="mh-input" id="pn" value={form.name} onChange={(e) => set("name", e.target.value)} required /></div>
            <div className="mh-field"><label className="mh-label" htmlFor="pen">ชื่อภาษาอังกฤษ (ถ้ามี)</label><input className="mh-input" id="pen" value={form.name_en} onChange={(e) => set("name_en", e.target.value)} /></div>
            <div className="mh-field"><label className="mh-label" htmlFor="ps">slug (ที่อยู่หน้าสินค้า)</label><input className="mh-input" id="ps" value={form.slug} onChange={(e) => set("slug", e.target.value)} placeholder="moo-yo-garlic" required /><span className="mh-help">{form.id ? "เปลี่ยนแล้วลิงก์เดิมของสินค้านี้จะใช้ไม่ได้" : "ตั้งครั้งเดียว ใช้อักษรอังกฤษพิมพ์เล็กและขีดกลาง"}</span></div>
            <div className="form-grid">
              <div className="mh-field"><label className="mh-label" htmlFor="pc">หมวดหมู่</label><select className="mh-select" id="pc" value={form.category_slug} onChange={(e) => set("category_slug", e.target.value)}>{cats.data?.map((c) => <option key={c.slug} value={c.slug}>{c.name}{c.is_active ? "" : " (ซ่อนอยู่)"}</option>)}</select></div>
              <div className="mh-field"><label className="mh-label" htmlFor="pb">ป้าย</label><select className="mh-select" id="pb" value={form.badge} onChange={(e) => set("badge", e.target.value)}>{BADGES.map((b) => <option key={b.v} value={b.v}>{b.l}</option>)}</select></div>
              <div className="mh-field"><label className="mh-label" htmlFor="pso">ลำดับการแสดง</label><input className="mh-input num" id="pso" inputMode="numeric" value={form.sort_order} onChange={(e) => set("sort_order", Math.max(0, parseInt(e.target.value || "0", 10) || 0))} /><span className="mh-help">เลขน้อยแสดงก่อน</span></div>
            </div>
            <label className="mh-row" style={{ gap: 8 }}><input type="checkbox" checked={form.is_featured} onChange={(e) => set("is_featured", e.target.checked)} style={{ width: 20, height: 20, accentColor: "var(--leaf)" }} /> แสดงในแถว “รสยอดนิยม” หน้าแรก</label>
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
              <p className="mh-label" style={{ marginBottom: 8 }}>ขนาดและราคา (ราคาปกติก่อนลด)</p>
              <div className="mh-tablewrap">
                <table className="mh-table">
                  <thead><tr><th>ขนาด</th><th>SKU</th><th className="r">ราคา (บาท)</th><th className="r">น้ำหนัก (กรัม)</th><th /></tr></thead>
                  <tbody>
                    {form.variants.map((v, i) => (
                      <tr key={i}>
                        <td><input className="mh-input" aria-label="ชื่อขนาด" style={{ minWidth: 90 }} value={v.label} onChange={(e) => setVariant(i, { label: e.target.value })} /></td>
                        <td><input className="mh-input" aria-label="SKU" style={{ minWidth: 120 }} value={v.sku} disabled={v.existing} title={v.existing ? "SKU ของขนาดที่มีอยู่แล้วแก้ไม่ได้ เพราะผูกกับคำสั่งซื้อและสต็อก" : undefined} onChange={(e) => setVariant(i, { sku: e.target.value })} /></td>
                        <td><input className="mh-input num" aria-label="ราคา" style={{ minWidth: 90, textAlign: "right" }} inputMode="decimal" value={v.price} onChange={(e) => setVariant(i, { price: e.target.value })} /></td>
                        <td><input className="mh-input num" aria-label="น้ำหนัก" style={{ minWidth: 90, textAlign: "right" }} inputMode="numeric" value={v.weight} onChange={(e) => setVariant(i, { weight: e.target.value })} /></td>
                        <td><button type="button" className="mh-btn mh-btn--secondary mh-btn--sm" disabled={form.variants.length === 1} aria-label={`ลบขนาด ${v.label}`} onClick={() => set("variants", form.variants.filter((_, j) => j !== i))}>ลบ</button></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <button type="button" className="mh-btn mh-btn--secondary mh-btn--sm" style={{ marginTop: 8 }} onClick={() => set("variants", [...form.variants, blankVariant()])}>เพิ่มขนาด</button>
              <p className="xs ink-muted" style={{ marginTop: 8 }}>ใส่ราคาปกติเสมอ ส่วนลดตั้งที่หน้า “โปรโมชัน” ขนาดที่ลบออกจะหยุดขาย แต่ไม่หายจากคำสั่งซื้อเก่า สต็อกจัดการที่หน้า “สต็อก”</p>
            </div>

            {formError && <div className="notice notice--warn" role="alert"><p>{formError}</p></div>}
            {save.isSuccess && !formError && <div className="notice notice--ok" role="status"><p>บันทึกแล้ว</p></div>}
            <div className="mh-row" style={{ justifyContent: "flex-end" }}>
              <button type="button" className="mh-btn mh-btn--secondary mh-btn--sm" onClick={() => setForm(null)}>ปิด</button>
              <button type="submit" className="mh-btn mh-btn--primary mh-btn--sm" disabled={save.isPending}>{save.isPending ? "กำลังบันทึก…" : "บันทึก"}</button>
            </div>
          </form>
        )}
      </div>
    </>
  );
}
