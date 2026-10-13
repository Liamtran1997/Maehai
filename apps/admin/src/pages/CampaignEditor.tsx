import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ErrorNotice } from "../components/Notice";
import { api, unwrap, uploadFile, type Campaign, type CampaignIn } from "../lib/api";
import { useAuth } from "../lib/auth";

/** Where the shop lives. In production it is the same site; in development the shop runs on its own port. */
const SHOP_URL = import.meta.env.VITE_SHOP_URL ?? "/";

const THEMES = [
  { v: "default", l: "ปกติ", c: "#1f6b43" },
  { v: "candle_festival", l: "แห่เทียนพรรษา", c: "#9a4a10" },
  { v: "songkran", l: "สงกรานต์", c: "#0b5d82" },
  { v: "new_year", l: "ปีใหม่", c: "#8a6d1d" },
];
const HERO = [
  { v: "none", l: "ใช้แบบปกติ" },
  { v: "image", l: "รูปภาพ" },
  { v: "animation", l: "ภาพเคลื่อนไหว (GIF)" },
  { v: "video", l: "วิดีโอ" },
];
const BKK = new Intl.DateTimeFormat("sv-SE", { timeZone: "Asia/Bangkok", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false });

/** A datetime-local value (Bangkok wall clock) for a stored instant. */
function toLocal(iso: string) {
  return BKK.format(new Date(iso)).replace(" ", "T");
}
/** The instant for a datetime-local value entered in Bangkok time. */
function toIso(local: string) {
  return `${local}:00+07:00`;
}

type Form = Omit<CampaignIn, "starts_at" | "ends_at"> & { starts_at: string; ends_at: string };

const blank = (): Form => {
  const start = new Date(Date.now() + 7 * 24 * 3600 * 1000);
  const end = new Date(start.getTime() + 7 * 24 * 3600 * 1000);
  return {
    name: "", theme: "default", accent_color: "", decorations: true,
    starts_at: toLocal(start.toISOString()), ends_at: toLocal(end.toISOString()),
    hero_kind: "none", hero_title: "", hero_subtitle: "", hero_cta_label: "", hero_cta_url: "",
    bar_enabled: false, bar_text: "", bar_url: "", collection_title: "", product_ids: [],
  };
};

const fromCampaign = (c: Campaign): Form => ({
  name: c.name, theme: c.theme, accent_color: c.accent_color, decorations: c.decorations,
  starts_at: toLocal(c.starts_at), ends_at: toLocal(c.ends_at),
  hero_kind: c.hero_kind, hero_title: c.hero_title, hero_subtitle: c.hero_subtitle,
  hero_cta_label: c.hero_cta_label, hero_cta_url: c.hero_cta_url,
  bar_enabled: c.bar_enabled, bar_text: c.bar_text, bar_url: c.bar_url, collection_title: c.collection_title,
  product_ids: c.products.map((p) => p.id),
});

function toBody(f: Form): CampaignIn {
  return { ...f, starts_at: toIso(f.starts_at), ends_at: toIso(f.ends_at), accent_color: f.accent_color.trim() };
}

export function CampaignEditor() {
  const { id } = useParams();
  const isNew = !id;
  const nav = useNavigate();
  const qc = useQueryClient();
  const { can } = useAuth();
  const canPublish = can("campaigns.publish");

  const existing = useQuery({
    queryKey: ["campaign", id], enabled: !isNew,
    queryFn: async () => unwrap(await api.GET("/api/admin/campaigns/{campaign_id}", { params: { path: { campaign_id: Number(id) } } })),
  });
  const products = useQuery({ queryKey: ["admin-products"], queryFn: async () => unwrap(await api.GET("/api/admin/catalog/products")) });

  return (
    <Editor
      key={existing.data?.id ?? "new"}
      campaign={existing.data ?? null}
      loading={!isNew && !existing.data}
      loadError={existing.error}
      products={products.data ?? []}
      canPublish={canPublish}
      onSaved={(c) => {
        qc.setQueryData(["campaign", String(c.id)], c);
        void qc.invalidateQueries({ queryKey: ["campaigns"] });
        if (isNew) nav(`/campaigns/${c.id}`, { replace: true });
      }}
      onLeave={() => nav("/campaigns")}
    />
  );
}

function Editor({ campaign, loading, loadError, products, canPublish, onSaved, onLeave }: {
  campaign: Campaign | null; loading: boolean; loadError: unknown; products: { id: number; name: string }[];
  canPublish: boolean; onSaved: (c: Campaign) => void; onLeave: () => void;
}) {
  const [f, setF] = useState<Form>(() => (campaign ? fromCampaign(campaign) : blank()));
  const [current, setCurrent] = useState<Campaign | null>(campaign);
  const [notice, setNotice] = useState<string | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const set = <K extends keyof Form>(k: K, v: Form[K]) => setF((x) => ({ ...x, [k]: v }));
  const readOnly = !!current && current.status !== "draft";
  const isLiveOrScheduled = current?.status === "live" || current?.status === "scheduled";

  const save = useMutation({
    mutationFn: async () => {
      const body = toBody(f);
      if (current) return unwrap(await api.PUT("/api/admin/campaigns/{campaign_id}", { params: { path: { campaign_id: current.id } }, body }));
      return unwrap(await api.POST("/api/admin/campaigns", { body }));
    },
    onSuccess: (c) => { setCurrent(c); setNotice("บันทึกร่างแล้ว"); onSaved(c); },
  });
  const publish = useMutation({
    mutationFn: async () => {
      const saved = await save.mutateAsync();
      return unwrap(await api.POST("/api/admin/campaigns/{campaign_id}/publish", { params: { path: { campaign_id: saved.id } } }));
    },
    onSuccess: (c) => { setCurrent(c); setNotice(`เผยแพร่แล้ว · ${c.status_label}`); onSaved(c); },
  });
  const remove = useMutation({
    mutationFn: async () => unwrap(await api.DELETE("/api/admin/campaigns/{campaign_id}", { params: { path: { campaign_id: current!.id } } })),
    onSuccess: onLeave,
  });
  const upload = useMutation({
    mutationFn: async (file: File) => {
      const saved = current ?? (await save.mutateAsync());
      return uploadFile<Campaign>(`/api/admin/campaigns/${saved.id}/hero`, "image", file);
    },
    onSuccess: (c) => {
      setCurrent(c); set("hero_kind", c.hero_kind as Form["hero_kind"]); setNotice("อัปโหลดส่วนหัวแล้ว"); onSaved(c);
    },
  });
  /** Video and poster uploads: each goes to its own endpoint, and the result becomes the current campaign. */
  const media = useMutation({
    mutationFn: async ({ path, field, file }: { path: (id: number) => string; field: string; file: File }) => {
      const saved = current ?? (await save.mutateAsync());
      return uploadFile<Campaign>(path(saved.id), field, file);
    },
    onSuccess: (c) => { setCurrent(c); set("hero_kind", c.hero_kind as Form["hero_kind"]); setNotice("อัปโหลดแล้ว"); onSaved(c); },
  });
  const previewMutation = useMutation({
    mutationFn: async () => {
      const saved = current ?? (await save.mutateAsync());
      return unwrap(await api.POST("/api/admin/campaigns/{campaign_id}/preview-token", { params: { path: { campaign_id: saved.id } } }));
    },
    onSuccess: ({ token }) => { setPreview(`${SHOP_URL.replace(/\/$/, "")}/?preview=${token}`); },
  });

  const onSubmit = (e: FormEvent) => { e.preventDefault(); setNotice(null); save.mutate(); };
  const toggleProduct = (pid: number) => set("product_ids", f.product_ids.includes(pid) ? f.product_ids.filter((x) => x !== pid) : [...f.product_ids, pid]);
  const error = save.error ?? publish.error ?? remove.error ?? upload.error ?? media.error ?? previewMutation.error ?? loadError;

  if (loading) return <p className="ink-muted">กำลังโหลด…</p>;
  return (
    <form className="product-editor" onSubmit={onSubmit}>
      <nav className="crumbs" aria-label="ตำแหน่ง"><Link to="/campaigns">แคมเปญ</Link><span aria-hidden="true"> › </span><span>{current ? current.name : "สร้างแคมเปญ"}</span></nav>
      <div className="page-head">
        <div>
          <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 12 }}>
            <h1>{current ? current.name : "สร้างแคมเปญใหม่"}</h1>
            {current && <span className="mh-status mh-status--wait" data-glyph="○">{current.status_label}</span>}
          </div>
          <p>{readOnly ? "แคมเปญนี้เผยแพร่แล้ว แก้ได้เฉพาะเมื่อมีสิทธิ์เผยแพร่" : "ลูกค้ายังไม่เห็นจนกว่าจะกดเผยแพร่"}</p>
        </div>
      </div>

      {isLiveOrScheduled && canPublish && <div className="notice notice--info" role="status"><p>แคมเปญนี้ถูกเผยแพร่แล้ว การบันทึกจะเปลี่ยนหน้าร้านทันที</p></div>}
      {notice && <div className="notice notice--ok" role="status"><p>{notice}</p></div>}
      {preview && <div className="notice notice--info" role="status"><p>เปิดหน้าตัวอย่างแล้ว <a href={preview} target="_blank" rel="noreferrer">เปิดอีกครั้ง</a> ลิงก์ใช้ได้ 30 นาที</p></div>}
      <ErrorNotice error={error} />

      <div className="editor-grid">
        <nav className="sectionnav" aria-label="หัวข้อในหน้านี้">
          <a href="#c-basic">ข้อมูลหลัก</a><a href="#c-look">หน้าตา</a><a href="#c-hero">ส่วนหัว</a><a href="#c-bar">แถบประกาศ</a><a href="#c-products">สินค้าของเทศกาล</a>
        </nav>
        <fieldset disabled={readOnly && !canPublish} style={{ border: 0, margin: 0, padding: 0, display: "contents" }}>
        <div className="editor-body">
          <section id="c-basic" className="panel">
            <h2>ข้อมูลหลัก</h2>
            <div className="mh-field"><label className="mh-label" htmlFor="cn">ชื่อแคมเปญ (ลูกค้าไม่เห็น)</label><input className="mh-input" id="cn" value={f.name} onChange={(e) => set("name", e.target.value)} required /></div>
            <div className="form-grid">
              <div className="mh-field"><label className="mh-label" htmlFor="cs">เริ่ม (เวลาไทย)</label><input className="mh-input" id="cs" type="datetime-local" value={f.starts_at} onChange={(e) => set("starts_at", e.target.value)} required /></div>
              <div className="mh-field"><label className="mh-label" htmlFor="ce">จบ (เวลาไทย)</label><input className="mh-input" id="ce" type="datetime-local" value={f.ends_at} onChange={(e) => set("ends_at", e.target.value)} required /></div>
            </div>
          </section>

          <section id="c-look" className="panel">
            <h2>หน้าตา</h2>
            <p className="small muted" style={{ margin: 0 }}>เปลี่ยนเฉพาะหน้าแรก ส่วนตะกร้า ชำระเงิน และ PromptPay คงสีประจำร้านเสมอ</p>
            <div role="radiogroup" aria-label="ธีม" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(150px, 1fr))", gap: 12 }}>
              {THEMES.map((t) => (
                <button key={t.v} type="button" role="radio" aria-checked={f.theme === t.v} onClick={() => set("theme", t.v)}
                  style={{ textAlign: "left", padding: 10, borderRadius: 12, cursor: "pointer", background: "var(--surface-200)", border: f.theme === t.v ? "2px solid var(--leaf)" : "1.5px solid var(--line)", font: "inherit", color: "var(--ink)" }}>
                  <span aria-hidden="true" style={{ display: "block", height: 48, borderRadius: 8, background: t.c }} />
                  <b style={{ display: "block", marginTop: 8, fontSize: 14 }}>{t.l}</b>
                </button>
              ))}
            </div>
            <div className="form-grid">
              <div className="mh-field">
                <label className="mh-label" htmlFor="ca">สีหลัก (เว้นว่าง = ใช้สีของธีม)</label>
                <input className="mh-input" id="ca" placeholder="#9A4A10" value={f.accent_color} onChange={(e) => set("accent_color", e.target.value)} style={{ maxWidth: 160 }} />
                <span className="mh-help">ต้องอ่านตัวอักษรขาวได้ชัด (อัตราส่วนความต่างอย่างน้อย 4.5 : 1)</span>
              </div>
              <label className="mh-row" style={{ gap: 10, alignItems: "flex-start", paddingTop: 24 }}>
                <input type="checkbox" checked={f.decorations} onChange={(e) => set("decorations", e.target.checked)} style={{ width: 20, height: 20, accentColor: "var(--leaf)" }} />
                <span><b style={{ fontSize: 14 }}>ลายตกแต่ง</b><br /><span className="small muted">ลายจาง ๆ ที่มุมส่วนหัว ไม่ขยับ</span></span>
              </label>
            </div>
          </section>

          <section id="c-hero" className="panel">
            <h2>ส่วนหัวหน้าแรก</h2>
            <div className="mh-chips" role="radiogroup" aria-label="ชนิดส่วนหัว">
              {HERO.map((h) => <button key={h.v} type="button" role="radio" className="mh-chip" aria-checked={f.hero_kind === h.v} aria-pressed={f.hero_kind === h.v} onClick={() => set("hero_kind", h.v as Form["hero_kind"])}>{h.l}</button>)}
            </div>
            {(f.hero_kind === "image" || f.hero_kind === "animation") && (
              <div className="mh-field">
                <span className="mh-label">{f.hero_kind === "animation" ? "ไฟล์ GIF หรือ WebP แบบเคลื่อนไหว (ไม่เกิน 8 MB)" : "ไฟล์รูป JPG, PNG หรือ WebP (ไม่เกิน 8 MB)"}</span>
                {current?.hero_image_url && (
                  <img src={current.hero_image_url} alt="ส่วนหัวปัจจุบัน" style={{ width: "100%", maxWidth: 480, aspectRatio: "16 / 7", objectFit: "cover", borderRadius: 12, border: "1px solid var(--line)" }} />
                )}
                <input type="file" accept={f.hero_kind === "animation" ? "image/gif,image/webp" : "image/jpeg,image/png,image/webp"} aria-label="เลือกไฟล์ส่วนหัว"
                  disabled={upload.isPending || readOnly} onChange={(e) => { const file = e.target.files?.[0]; if (file) upload.mutate(file); e.target.value = ""; }} />
                {upload.isPending && <span className="mh-help">กำลังอัปโหลด…</span>}
                {!current?.hero_image_url && <span className="mh-help" style={{ color: "var(--danger)" }}>ต้องมีไฟล์ส่วนหัวก่อนเผยแพร่</span>}
              </div>
            )}
            {f.hero_kind === "video" && (
              <div className="mh-field">
                <span className="mh-label">วิดีโอ MP4 หรือ WebM (ไม่เกิน 25 MB) เล่นเองแบบไม่มีเสียงและวนซ้ำ</span>
                {current?.hero_video_url && (
                  <video src={current.hero_video_url} poster={current.hero_poster_url ?? undefined} muted loop playsInline controls aria-label="วิดีโอส่วนหัวปัจจุบัน"
                    style={{ width: "100%", maxWidth: 480, aspectRatio: "16 / 7", objectFit: "cover", borderRadius: 12, border: "1px solid var(--line)", background: "#000" }} />
                )}
                <input type="file" accept="video/mp4,video/webm" aria-label="เลือกไฟล์วิดีโอ" disabled={media.isPending || readOnly}
                  onChange={(e) => { const file = e.target.files?.[0]; if (file) media.mutate({ path: (id) => `/api/admin/campaigns/${id}/hero-video`, field: "video", file }); e.target.value = ""; }} />
                <span className="mh-label" style={{ marginTop: 8 }}>วิดีโอแนวตั้งสำหรับมือถือ (ไม่บังคับ)</span>
                {current?.hero_video_mobile_url && <span className="small muted">มีไฟล์สำหรับมือถือแล้ว</span>}
                <input type="file" accept="video/mp4,video/webm" aria-label="เลือกวิดีโอสำหรับมือถือ" disabled={media.isPending || readOnly}
                  onChange={(e) => { const file = e.target.files?.[0]; if (file) media.mutate({ path: (id) => `/api/admin/campaigns/${id}/hero-video-mobile`, field: "video", file }); e.target.value = ""; }} />
                <span className="mh-label" style={{ marginTop: 8 }}>ภาพปกของวิดีโอ (JPG, PNG หรือ WebP)</span>
                {current?.hero_poster_url && <img src={current.hero_poster_url} alt="ภาพปกปัจจุบัน" style={{ width: 160, aspectRatio: "16 / 9", objectFit: "cover", borderRadius: 8 }} />}
                <input type="file" accept="image/jpeg,image/png,image/webp" aria-label="เลือกภาพปกของวิดีโอ" disabled={media.isPending || readOnly}
                  onChange={(e) => { const file = e.target.files?.[0]; if (file) media.mutate({ path: (id) => `/api/admin/campaigns/${id}/hero-poster`, field: "image", file }); e.target.value = ""; }} />
                {media.isPending && <span className="mh-help">กำลังอัปโหลด…</span>}
                {!current?.hero_video_url && <span className="mh-help" style={{ color: "var(--danger)" }}>ต้องมีไฟล์วิดีโอก่อนเผยแพร่</span>}
                {!current?.hero_poster_url && <span className="mh-help" style={{ color: "var(--danger)" }}>ต้องมีภาพปกก่อนเผยแพร่</span>}
              </div>
            )}
            <div className="form-grid">
              <div className="mh-field"><label className="mh-label" htmlFor="ht">หัวข้อ</label><input className="mh-input" id="ht" value={f.hero_title} onChange={(e) => set("hero_title", e.target.value)} /></div>
              <div className="mh-field"><label className="mh-label" htmlFor="hs">ข้อความรอง</label><input className="mh-input" id="hs" value={f.hero_subtitle} onChange={(e) => set("hero_subtitle", e.target.value)} /></div>
              <div className="mh-field"><label className="mh-label" htmlFor="hl">ปุ่ม: ข้อความ</label><input className="mh-input" id="hl" value={f.hero_cta_label} onChange={(e) => set("hero_cta_label", e.target.value)} /></div>
              <div className="mh-field"><label className="mh-label" htmlFor="hu">ปุ่ม: ลิงก์</label><input className="mh-input" id="hu" placeholder="/ หรือ https://…" value={f.hero_cta_url} onChange={(e) => set("hero_cta_url", e.target.value)} /></div>
            </div>
          </section>

          <section id="c-bar" className="panel">
            <div className="panel-head"><h2>แถบประกาศ</h2>
              <label className="mh-row" style={{ marginLeft: "auto", gap: 8, fontSize: 14 }}>
                <input type="checkbox" checked={f.bar_enabled} onChange={(e) => set("bar_enabled", e.target.checked)} style={{ width: 20, height: 20, accentColor: "var(--leaf)" }} />แสดง
              </label>
            </div>
            <div className="form-grid">
              <div className="mh-field"><label className="mh-label" htmlFor="bt">ข้อความ (ไม่เกิน 80 ตัวอักษร)</label><input className="mh-input" id="bt" maxLength={80} value={f.bar_text} onChange={(e) => set("bar_text", e.target.value)} /></div>
              <div className="mh-field"><label className="mh-label" htmlFor="bu">ลิงก์ (ถ้ามี)</label><input className="mh-input" id="bu" value={f.bar_url} onChange={(e) => set("bar_url", e.target.value)} /></div>
            </div>
          </section>

          <section id="c-products" className="panel">
            <h2>สินค้าของเทศกาล</h2>
            <div className="mh-field"><label className="mh-label" htmlFor="cc">ชื่อหมวดบนหน้าแรก</label><input className="mh-input" id="cc" value={f.collection_title} onChange={(e) => set("collection_title", e.target.value)} /></div>
            <div className="mh-chips" role="group" aria-label="เลือกสินค้า">
              {products.map((p) => (
                <button key={p.id} type="button" className="mh-chip" aria-pressed={f.product_ids.includes(p.id)} onClick={() => toggleProduct(p.id)}>{p.name}</button>
              ))}
            </div>
            <span className="mh-help">เลือกแล้ว {f.product_ids.length} รายการ ลูกค้าจะเห็นตามลำดับที่เลือก</span>
          </section>
        </div>
        </fieldset>
      </div>

      <div className="action-bar action-bar--wrap">
        <span className="grow">{current ? "บันทึกร่างไม่กระทบหน้าร้าน" : "บันทึกร่างก่อน จึงจะอัปโหลดส่วนหัวและเผยแพร่ได้"}</span>
        <button type="button" className="mh-btn mh-btn--secondary" onClick={onLeave}>กลับ</button>
        {current?.status === "draft" && <button type="button" className="mh-btn mh-btn--secondary" style={{ color: "var(--danger)" }} disabled={remove.isPending}
          onClick={() => { if (window.confirm("ลบร่างนี้ใช่หรือไม่")) remove.mutate(); }}>ลบร่าง</button>}
        <button type="button" className="mh-btn mh-btn--secondary" disabled={previewMutation.isPending} onClick={() => previewMutation.mutate()}>ดูตัวอย่าง</button>
        <button type="submit" className="mh-btn mh-btn--secondary" disabled={save.isPending || (readOnly && !canPublish)}>{save.isPending ? "กำลังบันทึก…" : "บันทึกร่าง"}</button>
        {canPublish && current?.status === "draft" && <button type="button" className="mh-btn mh-btn--primary" disabled={publish.isPending} onClick={() => publish.mutate()}>{publish.isPending ? "กำลังเผยแพร่…" : "เผยแพร่"}</button>}
      </div>
    </form>
  );
}
