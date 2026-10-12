"use client";
import { formatTHB } from "@maehai/ui";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { ShopHeader } from "../../components/ShopHeader";
import { api, errorText, type ShippingMethod } from "../../lib/client-api";
import { useCart } from "../../lib/cart";

const ORDERS_KEY = "maehai.orders.v1";

export default function CheckoutPage() {
  const cart = useCart();
  const [methods, setMethods] = useState<ShippingMethod[]>([]);
  const [earliest, setEarliest] = useState("");
  const [method, setMethod] = useState("");
  const [loadError, setLoadError] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [couponInput, setCouponInput] = useState("");
  const [coupon, setCoupon] = useState<{ code: string; label: string; discount: number; goodsTotal: number } | null>(null);
  const [couponError, setCouponError] = useState<string | null>(null);
  const [couponBusy, setCouponBusy] = useState(false);
  const phoneRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    (async () => {
      try {
        const [m, s] = await Promise.all([api.GET("/api/shipping/methods"), api.GET("/api/shipping/schedule")]);
        if (!m.data || !s.data) throw new Error();
        setMethods(m.data);
        setMethod(m.data[0]?.code ?? "");
        setEarliest(s.data.earliest_date);
      } catch {
        setLoadError(true);
      }
    })();
  }, []);

  const chosen = methods.find((m) => m.code === method);
  const cartKey = cart.lines.map((l) => `${l.sku}:${l.quantity}`).join(",");
  useEffect(() => { setCoupon(null); }, [cartKey]);

  async function applyCoupon() {
    const code = couponInput.trim();
    if (!code) return;
    setCouponBusy(true); setCouponError(null);
    const res = await api.POST("/api/coupons/validate", {
      body: { code, items: cart.lines.map((l) => ({ sku: l.sku, quantity: l.quantity })), phone: phoneRef.current?.value ?? "" },
    }).catch(() => null);
    setCouponBusy(false);
    if (res?.data) setCoupon({ code: res.data.code, label: res.data.label, discount: res.data.discount_satang, goodsTotal: res.data.goods_total_satang });
    else { setCoupon(null); setCouponError(res ? errorText(res.error) : "เชื่อมต่อไม่ได้ ลองใหม่อีกครั้ง"); }
  }

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    const f = new FormData(e.currentTarget);
    const str = (k: string) => String(f.get(k) ?? "").trim();
    setBusy(true);
    const res = await api.POST("/api/orders", {
      body: {
        items: cart.lines.map((l) => ({ sku: l.sku, quantity: l.quantity })),
        customer_name: str("name"), phone: str("phone"), shipping_method: method, requested_date: str("date"), note: str("note"),
        coupon_code: coupon?.code ?? "",
        address: { address_line: str("address_line"), subdistrict: str("subdistrict"), district: str("district"), province: str("province"), postal_code: str("postal_code") },
      },
    }).catch(() => null);
    setBusy(false);
    if (!res || !res.data) {
      setError(res ? errorText(res.error) : "เชื่อมต่อร้านไม่ได้ ลองใหม่อีกครั้ง");
      return;
    }
    try {
      const prev = JSON.parse(localStorage.getItem(ORDERS_KEY) ?? "[]") as { number: string; token: string }[];
      localStorage.setItem(ORDERS_KEY, JSON.stringify([{ number: res.data.number, token: res.data.token }, ...prev].slice(0, 20)));
    } catch {}
    cart.clear();
    window.location.href = `/orders/${res.data.number}?t=${encodeURIComponent(res.data.token)}`;
  }

  if (cart.ready && cart.lines.length === 0) {
    return (
      <>
        <ShopHeader />
        <section className="sec" style={{ textAlign: "center" }}>
          <p className="ink-muted">ตะกร้าว่างอยู่</p>
          <div><a className="mh-btn mh-btn--accent btn-link" href="/products">เลือกสินค้า</a></div>
        </section>
      </>
    );
  }

  return (
    <>
      <ShopHeader />
      <ol className="progress" aria-label="ขั้นตอนการสั่งซื้อ">
        <li className="done"><span className="dot">✓</span>ตะกร้า</li><li className="bar" aria-hidden="true" />
        <li className="on"><span className="dot">2</span>จัดส่ง</li><li className="bar" aria-hidden="true" />
        <li><span className="dot">3</span>ชำระเงิน</li>
      </ol>

      {loadError ? (
        <section className="sec"><div className="notice notice--warn"><p>โหลดข้อมูลการจัดส่งไม่ได้ ลองรีเฟรชหน้านี้ หรือสั่งทาง LINE @maehai</p></div></section>
      ) : (
        <form className="sec sec--tight" style={{ gap: 20 }} onSubmit={onSubmit}>
          <fieldset className="panel" style={{ border: "1px solid var(--line)", margin: 0 }}>
            <legend className="bold" style={{ font: "600 18px/1.6 var(--font-sans)", padding: "0 4px" }}>วิธีรับสินค้า</legend>
            {methods.map((m) => (
              <label key={m.code} className={`deliv${m.code === method ? " deliv--on" : ""}`}>
                <input type="radio" name="method" value={m.code} checked={m.code === method} onChange={() => setMethod(m.code)} />
                <span><span className="bold" style={{ display: "block" }}>{m.name}</span><span className="sm ink-muted">{m.description}{m.fee_is_quoted ? " · ร้านแจ้งค่าจัดส่งภายหลัง" : " · ไม่มีค่าจัดส่ง"}</span></span>
              </label>
            ))}
          </fieldset>

          <div className="panel">
            <h2 style={{ font: "600 18px/1.6 var(--font-sans)" }}>ข้อมูลผู้รับ</h2>
            <div className="mh-field">
              <label className="mh-label" htmlFor="date">วันที่ต้องการรับของ</label>
              <input className="mh-input" id="date" name="date" type="date" required min={earliest} defaultValue={earliest} />
              <span className="mh-help">สั่งก่อน 13:00 น. เลือกได้ตั้งแต่พรุ่งนี้ ไม่มีรอบส่งวันอาทิตย์และวันหยุดนักขัตฤกษ์</span>
            </div>
            <div className="mh-field"><label className="mh-label" htmlFor="name">ชื่อผู้รับ</label><input className="mh-input" id="name" name="name" required maxLength={120} autoComplete="name" /></div>
            <div className="mh-field"><label className="mh-label" htmlFor="phone">เบอร์โทรศัพท์</label><input className="mh-input" id="phone" name="phone" required inputMode="tel" autoComplete="tel" placeholder="081-234-5678" ref={phoneRef} /></div>
            {chosen?.requires_address && (
              <>
                <div className="mh-field"><label className="mh-label" htmlFor="address_line">บ้านเลขที่ ซอย ถนน</label><textarea className="mh-textarea" id="address_line" name="address_line" required maxLength={300} /></div>
                <div className="form-grid">
                  <div className="mh-field"><label className="mh-label" htmlFor="subdistrict">ตำบล/แขวง</label><input className="mh-input" id="subdistrict" name="subdistrict" /></div>
                  <div className="mh-field"><label className="mh-label" htmlFor="district">อำเภอ/เขต</label><input className="mh-input" id="district" name="district" /></div>
                  <div className="mh-field"><label className="mh-label" htmlFor="province">จังหวัด</label><input className="mh-input" id="province" name="province" required /></div>
                  <div className="mh-field"><label className="mh-label" htmlFor="postal_code">รหัสไปรษณีย์</label><input className="mh-input" id="postal_code" name="postal_code" required inputMode="numeric" pattern="\d{5}" maxLength={5} title="ตัวเลข 5 หลัก" /></div>
                </div>
              </>
            )}
            <div className="mh-field"><label className="mh-label" htmlFor="note">หมายเหตุถึงร้าน (ถ้ามี)</label><input className="mh-input" id="note" name="note" maxLength={300} /></div>
          </div>

          <div className="panel">
            <h2 style={{ font: "600 18px/1.6 var(--font-sans)" }}>โค้ดส่วนลด</h2>
            {coupon ? (
              <div className="notice notice--ok" role="status" style={{ justifyContent: "space-between", alignItems: "center" }}>
                <p><b className="mh-code">{coupon.code}</b> {coupon.label} · ลด {formatTHB(coupon.discount)}</p>
                <button type="button" className="mh-btn mh-btn--secondary mh-btn--sm" onClick={() => { setCoupon(null); setCouponInput(""); }}>เอาออก</button>
              </div>
            ) : (
              <div className="mh-field">
                <label className="mh-label" htmlFor="coupon">มีโค้ดส่วนลดไหม</label>
                <div className="mh-row" style={{ gap: 8, flexWrap: "nowrap" }}>
                  <input className="mh-input" id="coupon" value={couponInput} autoCapitalize="characters" autoComplete="off" maxLength={24}
                    onChange={(e) => setCouponInput(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); void applyCoupon(); } }} />
                  <button type="button" className="mh-btn mh-btn--secondary" disabled={couponBusy || !couponInput.trim()} onClick={() => void applyCoupon()}>{couponBusy ? "กำลังตรวจ…" : "ใช้โค้ด"}</button>
                </div>
                {couponError && <span className="mh-help" role="alert" style={{ color: "var(--danger)" }}>{couponError}</span>}
              </div>
            )}
          </div>

          <div className="panel">
            <h2 style={{ font: "600 18px/1.6 var(--font-sans)" }}>สรุปคำสั่งซื้อ</h2>
            {cart.lines.map((l) => (
              <div key={l.sku} className="rowline"><span>{l.productName} ({l.variantLabel}) × {l.quantity}</span><span className="num">{formatTHB(l.unitPriceSatang * l.quantity, { hideZeroSatang: true })}</span></div>
            ))}
            <hr className="hr" />
            {coupon && <div className="rowline"><span>ส่วนลดโค้ด {coupon.code}</span><span className="num" style={{ color: "var(--band-red)" }}>−{formatTHB(coupon.discount)}</span></div>}
            <div className="rowline"><span>ค่าจัดส่ง</span><span className="ink-muted">{chosen?.fee_is_quoted ? "ร้านแจ้งภายหลัง" : "ไม่มี"}</span></div>
            <div className="rowline"><span className="bold">ยอดสินค้า</span><span className="mh-price num">{coupon ? formatTHB(coupon.goodsTotal) : formatTHB(cart.subtotalSatang, { hideZeroSatang: true })}</span></div>
          </div>

          {error && <div className="notice notice--warn" role="alert"><p>{error}</p></div>}
          <button className="mh-btn mh-btn--primary btn-block" type="submit" disabled={busy || !chosen}>{busy ? "กำลังส่งคำสั่งซื้อ…" : "ยืนยันคำสั่งซื้อ"}</button>
        </form>
      )}
    </>
  );
}
