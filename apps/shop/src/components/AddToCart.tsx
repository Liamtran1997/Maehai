"use client";
import { formatTHB } from "@maehai/ui";
import { useState } from "react";
import { useCart } from "../lib/cart";
import { Stepper } from "./Stepper";

type Variant = { sku: string; label: string; price_satang: number; weight_grams: number | null; available?: number | null };

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

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div className="mh-field">
        <span className="mh-label" id="sz">ขนาด</span>
        <div className="mh-chips" role="radiogroup" aria-labelledby="sz">
          {variants.map((x) => (
            <button key={x.sku} type="button" role="radio" aria-checked={x.sku === sku} className="mh-chip" style={{ minHeight: 44 }} disabled={soldOut(x)}
              aria-pressed={x.sku === sku} onClick={() => { setSku(x.sku); setQty(1); setAdded(false); }}>
              {x.label} · {soldOut(x) ? "หมด" : formatTHB(x.price_satang, { hideZeroSatang: true })}
            </button>
          ))}
        </div>
      </div>
      <div className="rowline" style={{ alignItems: "center" }}>
        <span className="mh-label">จำนวน</span>
        <Stepper value={qty} onChange={(n) => setQty(Math.max(1, Math.min(max, n)))} />
      </div>
      {low && <p className="sm" style={{ color: "var(--warning)" }} role="status">เหลือ {v.available} ชิ้น</p>}
      <div className="rowline">
        <span className="ink-muted">รวม</span>
        <span className="mh-price num">{formatTHB(v.price_satang * qty, { hideZeroSatang: true })}</span>
      </div>
      <button className="mh-btn mh-btn--accent btn-block" type="button" disabled={soldOut(v)}
        onClick={() => { cart.add({ sku: v.sku, slug, productName, variantLabel: v.label, unitPriceSatang: v.price_satang, quantity: qty }); setAdded(true); }}>
        เพิ่มลงตะกร้า
      </button>
      <div aria-live="polite">
        {added && (
          <div className="notice notice--ok">
            <p>เพิ่ม {productName} ({v.label}) × {qty} ลงตะกร้าแล้ว <a href="/cart" className="bold">ดูตะกร้า</a></p>
          </div>
        )}
      </div>
    </div>
  );
}
