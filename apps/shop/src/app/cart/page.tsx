"use client";
import { formatTHB } from "@maehai/ui";
import { ShopHeader } from "../../components/ShopHeader";
import { Stepper } from "../../components/Stepper";
import { TrackOnMount } from "../../components/Analytics";
import { useCart } from "../../lib/cart";

export default function CartPage() {
  const cart = useCart();
  return (
    <>
      <ShopHeader />
      <section className="sec sec--tight" style={{ paddingTop: 24 }}>
        <h1 style={{ font: "500 32px/1.4 var(--font-display)" }}>ตะกร้าสินค้า</h1>

        {cart.ready && cart.lines.length === 0 && (
          <div className="panel" style={{ textAlign: "center", padding: 32 }}>
            <p className="ink-muted">ยังไม่มีสินค้าในตะกร้า</p>
            <div><a className="mh-btn mh-btn--accent btn-link" href="/products">เลือกสินค้า</a></div>
          </div>
        )}

        {cart.lines.length > 0 && <TrackOnMount kind="cart_view" data={{ value: cart.subtotalSatang }} />}
        {cart.lines.length > 0 && (
          <div className="cart-grid">
            <div className="panel cart-lines">
              {cart.lines.map((l, i) => (
                <div key={l.sku}>
                  {i > 0 && <hr className="hr" />}
                  <div className="cartline">
                    <a className="thumb thumb--photo" href={`/products/${l.slug}`} aria-hidden="true" tabIndex={-1}>
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      {l.imageUrl ? <img src={l.imageUrl} alt="" /> : null}
                    </a>
                    <div className="grow">
                      <a className="bold" style={{ color: "var(--ink)", textDecoration: "none" }} href={`/products/${l.slug}`}>{l.productName}</a>
                      <p className="sm ink-muted">{l.variantLabel} · {formatTHB(l.unitPriceSatang, { hideZeroSatang: true })}</p>
                      <p className="sm num bold">{formatTHB(l.unitPriceSatang * l.quantity, { hideZeroSatang: true })}</p>
                    </div>
                    <Stepper small value={l.quantity} onChange={(n) => cart.setQty(l.sku, n)} />
                  </div>
                </div>
              ))}
            </div>
            <aside className="cart-side">
              <div className="panel">
                <h2 style={{ font: "600 18px/1.6 var(--font-sans)" }}>สรุปตะกร้า</h2>
                <div className="rowline"><span>ยอดสินค้า</span><span className="mh-price num">{formatTHB(cart.subtotalSatang, { hideZeroSatang: true })}</span></div>
                <p className="sm ink-muted">ค่าจัดส่งร้านจะแจ้งหลังรับคำสั่งซื้อ (รับที่ร้านไม่มีค่าจัดส่ง) ราคาสุดท้ายคิดจากร้านอีกครั้งตอนยืนยัน</p>
                <a className="mh-btn mh-btn--accent btn-block btn-link" href="/checkout">ไปหน้าสั่งซื้อ</a>
              </div>
              <p className="sm ink-muted" style={{ textAlign: "center" }}><b>สั่งก่อน 13:00 น.</b> รับของวันถัดไป</p>
            </aside>
          </div>
        )}
      </section>
    </>
  );
}
