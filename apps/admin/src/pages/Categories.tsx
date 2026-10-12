import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { ErrorNotice } from "../components/Notice";
import { api, unwrap, type AdminCategory } from "../lib/api";
import { useAuth } from "../lib/auth";

type Form = { id?: number; name: string; slug: string; sort_order: number; is_active: boolean };
const blank: Form = { name: "", slug: "", sort_order: 0, is_active: true };

export function Categories() {
  const qc = useQueryClient();
  const canEdit = useAuth().can("catalog.edit");
  const cats = useQuery({ queryKey: ["admin-categories"], queryFn: async () => unwrap(await api.GET("/api/admin/catalog/categories")) });
  const [form, setForm] = useState<Form | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<AdminCategory | null>(null);
  const refresh = () => { void qc.invalidateQueries({ queryKey: ["admin-categories"] }); void qc.invalidateQueries({ queryKey: ["admin-products"] }); };

  const save = useMutation({
    mutationFn: async (f: Form) => {
      const body = { name: f.name.trim(), slug: f.slug.trim(), sort_order: f.sort_order, is_active: f.is_active };
      if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(body.slug)) throw new Error("slug ใช้ตัวอักษรอังกฤษพิมพ์เล็ก ตัวเลข และขีดกลางเท่านั้น");
      return f.id
        ? unwrap(await api.PUT("/api/admin/catalog/categories/{category_id}", { params: { path: { category_id: f.id } }, body }))
        : unwrap(await api.POST("/api/admin/catalog/categories", { body }));
    },
    onSuccess: () => { setForm(null); refresh(); },
  });
  const toggle = useMutation({
    mutationFn: async (c: AdminCategory) => unwrap(await api.PUT("/api/admin/catalog/categories/{category_id}", { params: { path: { category_id: c.id } }, body: { name: c.name, slug: c.slug, sort_order: c.sort_order, is_active: !c.is_active } })),
    onSuccess: refresh,
  });
  const remove = useMutation({
    mutationFn: async (c: AdminCategory) => unwrap(await api.DELETE("/api/admin/catalog/categories/{category_id}", { params: { path: { category_id: c.id } } })),
    onSuccess: () => { setConfirmDelete(null); refresh(); },
  });
  const onSubmit = (e: FormEvent) => { e.preventDefault(); if (form) save.mutate(form); };

  return (
    <>
      <div className="topbar"><h1>หมวดหมู่สินค้า</h1>{canEdit && <button className="mh-btn mh-btn--primary mh-btn--sm" onClick={() => { save.reset(); setForm({ ...blank }); }}>เพิ่มหมวดหมู่</button>}</div>
      <p className="sm ink-muted">หมวดหมู่ที่ซ่อนจะหายจากหน้าร้านพร้อมสินค้าทั้งหมดในหมวด และลูกค้าสั่งสินค้าในหมวดนั้นไม่ได้ ลบได้เฉพาะหมวดที่ไม่มีสินค้า</p>
      <ErrorNotice error={cats.error ?? toggle.error ?? remove.error} />
      <div className="cols cols--2-1" style={{ alignItems: "start" }}>
        <div className="mh-tablewrap">
          <table className="mh-table">
            <thead><tr><th>ลำดับ</th><th>หมวดหมู่</th><th className="r">สินค้า</th><th>แสดงบนร้าน</th><th /></tr></thead>
            <tbody>
              {cats.data?.map((c) => (
                <tr key={c.id} className={form?.id === c.id ? "sel" : ""}>
                  <td className="num">{c.sort_order}</td>
                  <td><span className="bold">{c.name}</span><br /><span className="xs ink-muted">{c.slug}</span></td>
                  <td className="r">{c.product_count}</td>
                  <td><button className="mh-chip" style={{ minHeight: 32 }} aria-pressed={c.is_active} disabled={toggle.isPending || !canEdit} onClick={() => toggle.mutate(c)}>{c.is_active ? "แสดง" : "ซ่อน"}</button></td>
                  <td className="mh-row" style={{ gap: 8 }}>
                    {canEdit && <button className="mh-btn mh-btn--secondary mh-btn--sm" onClick={() => { save.reset(); setForm({ ...c }); }}>แก้ไข</button>}
                    {canEdit && c.product_count === 0 && <button className="mh-btn mh-btn--secondary mh-btn--sm" onClick={() => setConfirmDelete(c)}>ลบ</button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {confirmDelete && (
            <div className="notice notice--warn" role="alert" style={{ flexDirection: "column" }}>
              <p>ลบหมวดหมู่ “{confirmDelete.name}” ถาวร?</p>
              <div className="mh-row"><button className="mh-btn mh-btn--danger mh-btn--sm" disabled={remove.isPending} onClick={() => remove.mutate(confirmDelete)}>ลบ</button><button className="mh-btn mh-btn--secondary mh-btn--sm" onClick={() => setConfirmDelete(null)}>ไม่ลบ</button></div>
            </div>
          )}
          {form && (
            <form className="apanel" onSubmit={onSubmit}>
              <div className="apanel-head"><h2>{form.id ? "แก้ไขหมวดหมู่" : "เพิ่มหมวดหมู่"}</h2><button type="button" className="mh-btn mh-btn--secondary mh-btn--sm" onClick={() => setForm(null)}>ปิด</button></div>
              <div className="mh-field"><label className="mh-label" htmlFor="cn">ชื่อหมวดหมู่</label><input className="mh-input" id="cn" required maxLength={100} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
              <div className="mh-field"><label className="mh-label" htmlFor="cs">slug</label><input className="mh-input" id="cs" required maxLength={50} placeholder="gifts" value={form.slug} onChange={(e) => setForm({ ...form, slug: e.target.value })} /><span className="mh-help">ใช้ในลิงก์ /products?category=… เปลี่ยนแล้วลิงก์เดิมจะใช้ไม่ได้</span></div>
              <div className="mh-field"><label className="mh-label" htmlFor="co">ลำดับการแสดง</label><input className="mh-input num" id="co" inputMode="numeric" value={form.sort_order} onChange={(e) => setForm({ ...form, sort_order: Math.max(0, parseInt(e.target.value || "0", 10) || 0) })} /></div>
              <label className="mh-row" style={{ gap: 8 }}><input type="checkbox" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} style={{ width: 20, height: 20, accentColor: "var(--leaf)" }} /> แสดงบนหน้าร้าน</label>
              <ErrorNotice error={save.error} />
              <button className="mh-btn mh-btn--primary" type="submit" disabled={save.isPending}>{save.isPending ? "กำลังบันทึก…" : "บันทึก"}</button>
            </form>
          )}
        </div>
      </div>
    </>
  );
}
