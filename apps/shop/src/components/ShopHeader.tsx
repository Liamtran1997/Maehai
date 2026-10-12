import { LogMark } from "@maehai/ui";
import { CartLink } from "./CartLink";

export function ShopHeader() {
  return (
    <header className="m-hdr">
      <a className="brand" href="/">
        <LogMark />
        แม่ฮาย
      </a>
      <a className="icon-btn" href="/products" aria-label="ค้นหาสินค้า">
        <svg className="ic" viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="M20 20l-4-4" /></svg>
      </a>
      <a className="icon-btn" href="/track" aria-label="ติดตามคำสั่งซื้อ">
        <svg className="ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M3 7h11v9H3zM14 10h4l3 3v3h-7" /><circle cx="7" cy="17" r="1.5" /><circle cx="17" cy="17" r="1.5" /></svg>
      </a>
      <CartLink />
    </header>
  );
}
