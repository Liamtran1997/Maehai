import { LogMark, formatTHB } from "@maehai/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { ErrorNotice } from "../components/Notice";
import { api, bahtToSatang, unwrap, uploadFile, type AdminProduct, type ProductImage, type ProductIn } from "../lib/api";
import { useAuth } from "../lib/auth";
import { PriceHistory } from "../components/PriceHistory";

type VariantForm = { sku: string; label: string; price: string; weight: string; existing: boolean };
type Form = Omit<ProductIn, "variants"> & { variants: VariantForm[]; id?: number; images?: ProductImage[] };

const BANDS = [{ v: "yellow", l: "ยางเหลือง" }, { v: "red", l: "ยางแดง" }, { v: "green", l: "ยางเขียว" }];
const BADGES = [{ v: "", l: "ไม่มี" }, { v: "best_seller", l: "ขายดี" }, { v: "new", l: "ใหม่" }];
const STATUS = [{ v: "", l: "ทุกสถานะ" }, { v: "on", l: "แสดงบนร้าน" }, { v: "off", l: "ซ่อนอยู่" }, { v: "featured", l: "แสดงหน้าแรก" }, { v: "noimage", l: "ยังไม่มีรูป" }, { v: "promo", l: "มีโปรโมชัน" }];

const blankVariant = (): VariantForm => ({ sku: "", label: "", price: "", weight: "", existing: false });
const blank = (category: string): Form => ({
  category_slug: category, slug: "", name: "", name_en: "", subtitle: "", description: "", bands: [], badge: "",
  fda_number: "", storage_note: "", is_active: true, is_featured: false, sort_order: 0, variants: [blankVariant()],
});
const fromProduct = (p: AdminProduct): Form => ({
  id: p.id, images: p.images, category_slug: p.category.slug, slug: p.slug, name: p.name, name_en: p.name_en,
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
  const { id: _id, images: _imgs, variants: _v, ...rest } = f;
  return { ...rest, variants };
}

function priceRange(p: AdminProduct) {
  const prices = p.variants.map((v) => v.price_satang);
  if (!prices.length) return "—";
  const lo = Math.min(...prices), hi = Math.max(...prices), f = (n: number) => formatTHB(n, { hideZeroSatang: true });
  return lo === hi ? f(lo) : `${f(lo)} ถึง ${f(hi)}`;
}

/** One line under the product name: category, number of sizes, and the price range the shop shows. */
function formSummary(f: Form, categoryName: string) {
  const prices = f.variants.map((v) => bahtToSatang(v.price)).filter((n): n is number => n !== null && n > 0);
  const money = (n: number) => formatTHB(n, { hideZeroSatang: true });
  const lo = Math.min(...prices), hi = Math.max(...prices);
  const range = prices.length === 0 ? "ยังไม่มีราคา" : lo === hi ? money(lo) : `${money(lo)} ถึง ${money(hi)}`;
  return `หมวด ${categoryName} · ${f.variants.length} ขนาด · ${range}`;
}

export function Products() {
  const qc = useQueryClient();
  const { can } = useAuth();
  const canEdit = can("catalog.edit");
  const canPrice = can("pricing.manage");
  const products = useQuery({ queryKey: ["admin-products"], queryFn: async () => unwrap(await api.GET("/api/admin/catalog/products")) });
  const cats = useQuery({ queryKey: ["admin-categories"], queryFn: async () => unwrap(await api.GET("/api/admin/catalog/categories")) });
  const [form, setForm] = useState<Form | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [pending, setPending] = useState<File[]>([]);
  const [zoom, setZoom] = useState<string | null>(null);
  // Escape closes the enlarged photo, like clicking outside it.
  useEffect(() => {
    if (!zoom) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setZoom(null); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [zoom]);
  const previews = useMemo(() => pending.map((f) => URL.createObjectURL(f)), [pending]);
  useEffect(() => () => previews.forEach((u) => URL.revokeObjectURL(u)), [previews]);
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
    onSuccess: (p) => {
      setForm(fromProduct(p)); setFormError(null); refresh();
      // Photos picked before the product existed go up now that it has an id.
      if (pending.length) { upload.mutate({ id: p.id, files: pending }); setPending([]); }
    },
    onError: (e) => setFormError(e instanceof Error ? e.message : "บันทึกไม่สำเร็จ"),
  });
  // Gallery actions. Each returns the whole product, so the photo strip always matches the server.
  const applyImages = (p: AdminProduct) => { setForm((f) => (f ? { ...f, images: p.images } : f)); refresh(); };
  const upload = useMutation({
    mutationFn: async ({ id, files }: { id: number; files: File[] }) => {
      let last: AdminProduct | null = null;
      for (const file of files) last = await uploadFile<AdminProduct>(`/api/admin/catalog/products/${id}/images`, "image", file);
      return last!;
    },
    onSuccess: applyImages,
  });
  const removeImage = useMutation({
    mutationFn: async (imageId: number) => unwrap(await api.DELETE("/api/admin/catalog/products/{product_id}/images/{image_id}", { params: { path: { product_id: form!.id!, image_id: imageId } } })),
    onSuccess: applyImages,
  });
  const reorder = useMutation({
    mutationFn: async (ids: number[]) => unwrap(await api.PUT("/api/admin/catalog/products/{product_id}/image-order", { params: { path: { product_id: form!.id! } }, body: { ids } })),
    onSuccess: applyImages,
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
  const open = (f: Form) => { setFormError(null); save.reset(); upload.reset(); setPending([]); setForm(f); };

  return (
    <>
      {!form && <div className="page-head">
        <div><h1>สินค้า</h1><p>{products.data?.length ?? 0} รายการ · แก้ราคาปกติที่นี่ ส่วนลดตั้งที่โปรโมชัน</p></div>
        <div className="actions">
          <Link className="mh-btn mh-btn--secondary mh-btn--sm" to="/categories">จัดการหมวดหมู่</Link>
          <Link className="mh-btn mh-btn--secondary mh-btn--sm" to="/promotions">โปรโมชัน</Link>
          {canEdit && canPrice && <button className="mh-btn mh-btn--primary mh-btn--sm" onClick={() => open(blank(cats.data?.[0]?.slug ?? ""))}>เพิ่มสินค้า</button>}
        </div>
      </div>}
      {!form && <div className="seg" role="group" aria-label="กรองตามสถานะ" style={{ alignSelf: "flex-start" }}>
        {STATUS.map((s) => <button key={s.v} type="button" aria-pressed={status === s.v} onClick={() => setStatus(s.v)}>{s.l}</button>)}
      </div>}
      {!form && <div className="toolbar">
        <div className="searchbox">
          <svg className="ic" viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="M20 20l-4-4" /></svg>
          <label htmlFor="pq" style={{ position: "absolute", left: -9999 }}>ค้นหาสินค้า</label>
          <input className="mh-input" id="pq" value={q} onChange={(e) => setQ(e.target.value)} placeholder="ค้นหาชื่อ หรือ slug" />
        </div>
        <select className="mh-select" style={{ width: "auto" }} aria-label="หมวดหมู่" value={cat} onChange={(e) => setCat(e.target.value)}>
          <option value="">ทุกหมวดหมู่</option>{cats.data?.map((c) => <option key={c.slug} value={c.slug}>{c.name}</option>)}
        </select>
        <span className="sm ink-muted">{shown.length} จาก {products.data?.length ?? 0} รายการ</span>
      </div>}
      {!form && <ErrorNotice error={products.error ?? toggle.error} />}

      <div className="cols" style={{ alignItems: "start" }}>
        {!form && <div className="mh-tablewrap">
          <table className="mh-table">
            <thead><tr><th>สินค้า</th><th>หมวดหมู่</th><th className="r">ราคา (ก่อนลด)</th><th>แสดงบนร้าน</th><th><span style={{ position: "absolute", left: -9999 }}>แก้ไข</span></th></tr></thead>
            <tbody>
              {shown.map((p) => (
                <tr key={p.id}>
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
                  <td><button className="mh-chip" style={{ minHeight: 32 }} aria-pressed={p.is_active} disabled={toggle.isPending || !canEdit} onClick={() => toggle.mutate(p)}>{p.is_active ? "แสดง" : "ซ่อน"}</button></td>
                  <td><button className="mh-btn mh-btn--secondary mh-btn--sm" onClick={() => open(fromProduct(p))}>{canEdit ? "แก้ไข" : "ดู"}</button></td>
                </tr>
              ))}
              {products.data && shown.length === 0 && <tr><td colSpan={5} className="ink-muted">ไม่พบสินค้าตามที่กรอง</td></tr>}
            </tbody>
          </table>
        </div>}

        {form && (
          <form className="product-editor" onSubmit={onSubmit}>
            {!canEdit && <div className="notice notice--info"><p>ตำแหน่งของคุณดูสินค้าได้อย่างเดียว</p></div>}
            {canEdit && !canPrice && <div className="notice notice--info"><p>ตำแหน่งของคุณแก้ข้อมูลสินค้าได้ แต่แก้ราคาไม่ได้</p></div>}
            <fieldset disabled={!canEdit} style={{ border: 0, margin: 0, padding: 0, display: "contents" }}>
            <nav className="crumbs" aria-label="ตำแหน่ง"><button type="button" className="link-btn" onClick={() => setForm(null)}>สินค้า</button><span aria-hidden="true"> › </span><span>{form.id ? form.name || "แก้ไขสินค้า" : "เพิ่มสินค้า"}</span></nav>
            <div className="page-head">
              <div>
                <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 12 }}>
                  <h1>{form.id ? form.name || "แก้ไขสินค้า" : "เพิ่มสินค้าใหม่"}</h1>
                  {form.id && <span className={`mh-status ${form.is_active ? "mh-status--done" : "mh-status--paid"}`} data-glyph={form.is_active ? "✓" : "○"}>{form.is_active ? "แสดงบนหน้าร้าน" : "ซ่อนอยู่"}</span>}
                </div>
                <p>{form.id ? formSummary(form, cats.data?.find((c) => c.slug === form.category_slug)?.name ?? "—") : "บันทึกสินค้าก่อน แล้วจึงเพิ่มรูปและประวัติราคาได้"}</p>
              </div>
              {form.id && canEdit && (
                <div className="actions">
                  <button type="button" className="mh-btn mh-btn--secondary mh-btn--sm" onClick={() => set("is_active", !form.is_active)}>{form.is_active ? "ซ่อนจากหน้าร้าน" : "แสดงบนหน้าร้าน"}</button>
                </div>
              )}
            </div>
            <div className="editor-grid">
            <nav className="sectionnav" aria-label="หัวข้อในหน้านี้">
              <a href="#p-photos">รูปภาพ</a><a href="#p-basic">ข้อมูลหลัก</a><a href="#p-detail">รายละเอียด อย. การเก็บ</a><a href="#p-sizes">ขนาดและราคา</a>{form.id && <a href="#p-history">ประวัติราคา</a>}
            </nav>
            <div className="editor-body">
            <section id="p-photos" className="panel">
            <h2>รูปภาพ</h2>

            <div className="mh-field">
              <span className="mh-label">รูปสินค้า ({form.images?.length ?? 0}/10)</span>
              {form.id ? (
                <>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))", gap: 16 }}>
                    {form.images?.map((im, idx, all) => (
                      <div key={im.id} style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                        <div style={{ position: "relative" }}>
                          <button type="button" onClick={() => setZoom(im.url)} aria-label={`ดูรูปที่ ${idx + 1} ขนาดใหญ่`}
                            style={{ display: "block", width: "100%", padding: 0, border: 0, background: "var(--surface-300)", borderRadius: 8, cursor: "zoom-in" }}>
                            <img src={im.url} alt={`รูปที่ ${idx + 1}`} style={{ width: "100%", aspectRatio: "1", objectFit: "contain", borderRadius: 8, display: "block" }} />
                          </button>
                          {idx === 0 && <span className="mh-badge" style={{ position: "absolute", top: 6, left: 6, fontSize: 11, padding: "0 8px" }}>รูปหลัก</span>}
                        </div>
                        <div className="mh-row" style={{ gap: 4, justifyContent: "center", flexWrap: "nowrap" }}>
                          <button type="button" className="mh-btn mh-btn--secondary mh-btn--sm" aria-label="เลื่อนไปทางซ้าย" disabled={idx === 0 || reorder.isPending}
                            onClick={() => { const ids = all.map((x) => x.id); [ids[idx - 1], ids[idx]] = [ids[idx], ids[idx - 1]]; reorder.mutate(ids); }}>‹</button>
                          <button type="button" className="mh-btn mh-btn--secondary mh-btn--sm" aria-label="เลื่อนไปทางขวา" disabled={idx === all.length - 1 || reorder.isPending}
                            onClick={() => { const ids = all.map((x) => x.id); [ids[idx + 1], ids[idx]] = [ids[idx], ids[idx + 1]]; reorder.mutate(ids); }}>›</button>
                          <button type="button" className="mh-btn mh-btn--secondary mh-btn--sm" aria-label={`ลบรูปที่ ${idx + 1}`} disabled={removeImage.isPending}
                            onClick={() => removeImage.mutate(im.id)}>✕</button>
                        </div>
                      </div>
                    ))}
                    {(form.images?.length ?? 0) < 10 && (
                      <label htmlFor="pimg" className="drop" style={{ cursor: "pointer", minHeight: 104, alignContent: "center", padding: 8 }}>
                        <span className="bold" style={{ color: "var(--ink)" }}>{upload.isPending ? "กำลังอัปโหลด…" : "+ เพิ่มรูป"}</span>
                      </label>
                    )}
                  </div>
                  <input ref={fileRef} type="file" multiple accept="image/jpeg,image/png,image/webp" id="pimg" style={{ position: "absolute", left: -9999 }}
                    onChange={(e) => {
                      const room = 10 - (form.images?.length ?? 0);
                      const files = Array.from(e.target.files ?? []);
                      e.target.value = "";
                      if (files.length > room) setFormError(`เพิ่มได้อีก ${room} รูป (สูงสุด 10 รูปต่อสินค้า) ระบบจะอัปโหลดเฉพาะ ${room} รูปแรก`);
                      if (room > 0 && files.length > 0) upload.mutate({ id: form.id!, files: files.slice(0, room) });
                    }} />
                  <span className="mh-help">ลากเลือกได้หลายรูปพร้อมกัน รูปแรกคือรูปที่ลูกค้าเห็นในหน้าร้าน ลำดับเลื่อนด้วยปุ่ม ‹ ›. JPG, PNG หรือ WebP ไม่เกิน 5 MB ต่อรูป</span>
                </>
              ) : (
                <>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))", gap: 16 }}>
                    {pending.map((f, idx) => (
                      <div key={`${f.name}-${idx}`} style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                        <div style={{ position: "relative" }}>
                          <img src={previews[idx]} alt={`รูปที่ ${idx + 1}`} style={{ width: "100%", aspectRatio: "1", objectFit: "cover", borderRadius: 8, display: "block" }} />
                          {idx === 0 && <span className="mh-badge" style={{ position: "absolute", top: 6, left: 6, fontSize: 11, padding: "0 8px" }}>รูปหลัก</span>}
                        </div>
                        <div className="mh-row" style={{ gap: 4, justifyContent: "center", flexWrap: "nowrap" }}>
                          <button type="button" className="mh-btn mh-btn--secondary mh-btn--sm" aria-label={`เอารูปที่ ${idx + 1} ออก`} onClick={() => setPending(pending.filter((_, j) => j !== idx))}>✕</button>
                        </div>
                      </div>
                    ))}
                    {pending.length < 10 && (
                      <label htmlFor="pimg-new" className="drop" style={{ cursor: "pointer", minHeight: 104, alignContent: "center", padding: 8 }}>
                        <span className="bold" style={{ color: "var(--ink)" }}>+ เพิ่มรูป</span>
                      </label>
                    )}
                  </div>
                  <input type="file" multiple accept="image/jpeg,image/png,image/webp" id="pimg-new" style={{ position: "absolute", left: -9999 }}
                    onChange={(e) => {
                      const room = 10 - pending.length;
                      const files = Array.from(e.target.files ?? []);
                      e.target.value = "";
                      if (files.length > room) setFormError(`เพิ่มได้อีก ${room} รูป (สูงสุด 10 รูปต่อสินค้า)`);
                      if (room > 0 && files.length > 0) setPending([...pending, ...files.slice(0, room)]);
                    }} />
                  <span className="mh-help">รูปจะถูกอัปโหลดเมื่อกดบันทึกสินค้า รูปแรกคือรูปหลัก</span>
                </>
              )}
              <ErrorNotice error={upload.error ?? removeImage.error ?? reorder.error} />
            </div>

            </section>
            <section id="p-basic" className="panel">
            <h2>ข้อมูลหลัก</h2>
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
            </section>
            <section id="p-detail" className="panel">
            <h2>รายละเอียดและการเก็บ</h2>
            <div className="mh-field"><label className="mh-label" htmlFor="psub">คำบรรยายสั้น</label><input className="mh-input" id="psub" value={form.subtitle} onChange={(e) => set("subtitle", e.target.value)} /></div>
            <div className="mh-field"><label className="mh-label" htmlFor="pd">รายละเอียด</label><textarea className="mh-textarea" id="pd" value={form.description} onChange={(e) => set("description", e.target.value)} /></div>
            <div className="form-grid">
              <div className="mh-field"><label className="mh-label" htmlFor="pf">เลข อย.</label><input className="mh-input" id="pf" value={form.fda_number} onChange={(e) => set("fda_number", e.target.value)} /></div>
              <div className="mh-field"><label className="mh-label" htmlFor="pst">การเก็บรักษา</label><input className="mh-input" id="pst" value={form.storage_note} onChange={(e) => set("storage_note", e.target.value)} /></div>
            </div>

            </section>
            <section id="p-sizes" className="panel">
            <h2>ขนาดและราคา</h2>
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
                        <td><input className="mh-input num" aria-label="ราคา" style={{ minWidth: 90, textAlign: "right" }} inputMode="decimal" disabled={!canPrice || !canEdit} title={canPrice ? undefined : "ต้องมีสิทธิ์แก้ราคา"} value={v.price} onChange={(e) => setVariant(i, { price: e.target.value })} /></td>
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

            </section>
            {form.id && <section id="p-history" className="panel"><h2>ประวัติราคา</h2><PriceHistory productId={form.id} /></section>}
            </div>
            </div>
            </fieldset>
            {formError && <div className="notice notice--warn" role="alert"><p>{formError}</p></div>}
            {save.isSuccess && !formError && <div className="notice notice--ok" role="status"><p>บันทึกแล้ว</p></div>}
            <div className="action-bar">
              <span className="grow">{canEdit ? "บันทึกแล้วจะแสดงตามที่ตั้งไว้ทันที" : "ดูอย่างเดียว"}</span>
              <button type="button" className="mh-btn mh-btn--secondary" onClick={() => setForm(null)}>ยกเลิก</button>
              {canEdit && <button type="submit" className="mh-btn mh-btn--primary" disabled={save.isPending}>{save.isPending ? "กำลังบันทึก…" : "บันทึก"}</button>}
            </div>
          </form>
        )}
      </div>
      {zoom && (
        <div role="dialog" aria-modal="true" aria-label="รูปสินค้า" onClick={() => setZoom(null)}
          style={{ position: "fixed", inset: 0, zIndex: 50, background: "rgba(20, 18, 14, 0.85)", display: "grid", placeItems: "center", padding: 16 }}>
          <button type="button" className="mh-btn mh-btn--secondary mh-btn--sm" onClick={() => setZoom(null)}
            style={{ position: "absolute", top: 16, right: 16, background: "var(--surface-200)" }}>ปิด</button>
          <img src={zoom} alt="" onClick={(e) => e.stopPropagation()}
            style={{ maxWidth: "100%", maxHeight: "90vh", objectFit: "contain", borderRadius: 8, background: "#fff" }} />
        </div>
      )}
    </>
  );
}
