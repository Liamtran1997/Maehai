"use client";
import { useCart } from "../lib/cart";

export function CartLink() {
  const { count } = useCart();
  return (
    <a className="icon-btn" href="/cart" aria-label={`ตะกร้า (${count} รายการ)`}>
      <svg className="ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M3 4h2l2.5 11h10L20 7H6.5" /><circle cx="9" cy="19" r="1.5" /><circle cx="17" cy="19" r="1.5" /></svg>
      <span className="lbl" aria-hidden="true">ตะกร้า</span>
      {count > 0 && <span className="count">{count}</span>}
    </a>
  );
}
