"use client";
import { usePathname } from "next/navigation";
import { useCart } from "../lib/cart";

const icon = (d: string) => <svg className="ic" viewBox="0 0 24 24" aria-hidden="true"><path d={d} /></svg>;

/** Phone-only bottom navigation. Hidden from 900px up, where the header carries the same links. */
export function TabBar() {
  const path = usePathname();
  const { count } = useCart();
  const cur = (href: string) => (href === "/" ? path === "/" : path.startsWith(href)) ? "page" : undefined;
  return (
    <nav className="tabbar" aria-label="เมนูหลัก">
      <a href="/" aria-current={cur("/")}>{icon("M4 11l8-7 8 7v9H4z")}หน้าแรก</a>
      <a href="/products" aria-current={cur("/products")}>{icon("M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z")}สินค้า</a>
      <a href="/track" aria-current={cur("/track")}>{icon("M3 7h11v9H3zM14 10h4l3 3v3h-7")}ติดตาม</a>
      <a href="/cart" aria-current={cur("/cart")} aria-label={`ตะกร้า (${count} รายการ)`}>
        {icon("M3 4h2l2.5 11h10L20 7H6.5")}ตะกร้า
        {count > 0 && <span className="count" aria-hidden="true">{count}</span>}
      </a>
    </nav>
  );
}
