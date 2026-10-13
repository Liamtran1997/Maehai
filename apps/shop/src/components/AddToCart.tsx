"use client";
import { formatTHB } from "@maehai/ui";
import { useState } from "react";
import { useCart } from "../lib/cart";
import { Stepper } from "./Stepper";

type Variant = {
  sku: string; label: string; price_satang: number; weight_grams: number | null; available?: number | null;
  original_price_satang?: number | null; restock_alert_url?: string | null;
};

const soldOut = (v: Variant) => v.available === 0;

export function AddToCart({ slug, productName, variants }: { slug: string; productName: string; variants: Variant[] }) {
  const cart = useCart();
  const firstOk = variants.filter((v) => !soldOut(v));
  const [sku, setSku] = useState((firstOk[Math.min(1, firstOk.length - 1)] ?? variants[0])?.sku ?? "");
  const [qty, setQty] = useState(1);
  const [added, setAdded] = useState(false);
  const v = variants.find((x) => x.sku === sku);
  if (!v) return null;
  const max = v.available ?? 99;           // null = not counted
  const low = v.available != null && v.available > 0 && v.available <= 5;

  const addToCart = () => {
    cart.add({ sku: v.sku, slug, productName, variantLabel: v.label, unitPriceSatang: v.price_satang, quantity: qty });
    setAdded(true);
  };
  const total = formatTHB(v.price_satang * qty, { hideZeroSatang: true });

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div>
        <p className={`pdp-price num${v.original_price_satang ? " mh-price--sale" : ""}`} style={v.original_price_satang ? { color: "var(--band-red)" } : undefined}>
          {formatTHB(v.price_satang, { hideZeroSatang: true })}
          {v.original_price_satang ? <s className="sm ink-muted" style={{ marginLeft: 8, font: "400 15px/1.4 var(--font-sans)" }}>{formatTHB(v.original_price_satang, { hideZeroSatang: true })}</s> : null}
          {" "}<small>/ ขนาด{v.label}</small>
        </p>
      </div>
      <div className="mh-field">
        <span className="mh-label" id="sz">ขนาด</span>
        <div className="sizes" role="radiogroup" aria-labelledby="sz">
          {variants.map((x) => (
            <button key={x.sku} type="button" role="radio" aria-checked={x.sku === sku} className="size" disabled={soldOut(x)}
              onClick={() => { setSku(x.sku); setQty(1); setAdded(false); }}>
              <b>{x.label}</b>
              {x.weight_grams ? <small>{x.weight_grams.toLocaleString("en-US")} ก.</small> : null}
              <span className="p">{soldOut(x) ? "หมด" : formatTHB(x.price_satang, { hideZeroSatang: true })}</span>
            </button>
          ))}
        </div>
      </div>
      {low && <p className="sm" style={{ color: "var(--warning)" }} role="status">เหลือ {v.available} ชิ้น</p>}
      <div className="buyrow">
        <Stepper value={qty} onChange={(n) => setQty(Math.max(1, Math.min(max, n)))} />
        <button className="mh-btn mh-btn--accent" type="button" disabled={soldOut(v)} onClick={addToCart}>
          <svg className="ic ic--sm" viewBox="0 0 24 24" aria-hidden="true"><path d="M3 4h2l2.5 11h10L20 7H6.5" /><circle cx="9" cy="19" r="1.5" /><circle cx="17" cy="19" r="1.5" /></svg>
          เพิ่มลงตะกร้า · {total}
        </button>
      </div>
      {variants.filter((x) => soldOut(x) && x.restock_alert_url).map((x) => (
        <div key={x.sku} className="notice notice--info">
          <p>ขนาด{x.label}หมดชั่วคราว <a className="bold" href={x.restock_alert_url!} target="_blank" rel="noreferrer">ให้ร้านแจ้งทาง LINE เมื่อมีของ</a></p>
        </div>
      ))}
      <div aria-live="polite">
        {added && (
          <div className="notice notice--ok">
            <p>เพิ่ม {productName} ({v.label}) × {qty} ลงตะกร้าแล้ว <a href="/cart" className="bold">ดูตะกร้า</a></p>
          </div>
        )}
      </div>
      {/* Phone: the buy button stays at the bottom edge while the customer reads the rest of the page. */}
      <div className="buybar">
        <span className="tot"><small>รวม {qty} · ขนาด{v.label}</small><b>{total}</b></span>
        <button className="mh-btn mh-btn--accent" type="button" disabled={soldOut(v)} onClick={addToCart}>เพิ่มลงตะกร้า</button>
      </div>
    </div>
  );
}
