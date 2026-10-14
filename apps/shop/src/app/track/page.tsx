"use client";
import { useState, type FormEvent } from "react";
import { ShopHeader } from "../../components/ShopHeader";
import { api, errorText } from "../../lib/client-api";

export default function TrackPage() {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setBusy(true); setError(null);
    const res = await api.POST("/api/orders/lookup", { body: { number: String(f.get("number")), phone: String(f.get("phone")) } }).catch(() => null);
    setBusy(false);
    if (res?.data) window.location.href = `/orders/${res.data.number}?t=${encodeURIComponent(res.data.token)}`;
    else setError(res ? errorText(res.error) : "เชื่อมต่อไม่ได้ ลองใหม่อีกครั้ง");
  }

  return (
    <>
      <ShopHeader />
      <form className="sec sec--tight sec--narrow" style={{ paddingTop: 24 }} onSubmit={onSubmit}>
        <div className="track-head">
          <span className="track-ic" aria-hidden="true"><svg className="ic" viewBox="0 0 24 24"><path d="M3 7h11v9H3zM14 10h4l3 3v3h-7" /><circle cx="7" cy="17" r="1.5" /><circle cx="17" cy="17" r="1.5" /></svg></span>
          <div>
            <h1 style={{ font: "500 32px/1.4 var(--font-display)" }}>ติดตามคำสั่งซื้อ</h1>
            <p className="ink-muted">กรอกเลขที่สั่งซื้อและเบอร์โทรที่ใช้สั่ง ไม่ต้องเข้าสู่ระบบ</p>
          </div>
        </div>
        <div className="panel" style={{ gap: 16 }}>
          <div className="mh-field"><label className="mh-label" htmlFor="number">เลขที่สั่งซื้อ</label><input className="mh-input" id="number" name="number" required placeholder="MH-2569-001284" autoCapitalize="characters" /></div>
          <div className="mh-field"><label className="mh-label" htmlFor="phone">เบอร์โทรศัพท์ที่ใช้สั่ง</label><input className="mh-input" id="phone" name="phone" required inputMode="tel" placeholder="081-234-5678" /></div>
          {error && <div className="notice notice--warn" role="alert"><p>{error}</p></div>}
          <button className="mh-btn mh-btn--primary btn-block" type="submit" disabled={busy}>{busy ? "กำลังค้นหา…" : "ค้นหา"}</button>
        </div>
        <p className="sm ink-muted" style={{ textAlign: "center" }}>หาเลขที่สั่งซื้อไม่เจอ ถามร้านทาง LINE @maehai หรือโทร 081-878-5474</p>
      </form>
    </>
  );
}
