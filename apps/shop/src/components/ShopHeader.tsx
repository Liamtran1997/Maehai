import { BrandLogo } from "@maehai/ui";
import { CartLink } from "./CartLink";

type NavCategory = { slug: string; name: string };

// Used by pages that run in the browser (cart, checkout, track) and so cannot load categories themselves.
const DEFAULT_NAV: NavCategory[] = [
  { slug: "moo-yo", name: "หมูยอ" }, { slug: "naem", name: "แหนม" }, { slug: "isan-sausage", name: "ไส้กรอกอีสาน" },
];

/** The shop header. Server pages pass their categories in; it must stay a plain component because client pages render it too. */
export function ShopHeader({ categories = DEFAULT_NAV }: { categories?: NavCategory[] }) {

  return (
    <header className="m-hdr">
      <a className="brand" href="/" aria-label="หน้าแรก หมูยอแม่ฮาย">
        <BrandLogo height={40} />
      </a>
      <nav className="hdr-nav" aria-label="หมวดสินค้า">
        <a href="/products">สินค้าทั้งหมด</a>
        {categories.slice(0, 4).map((c) => <a key={c.slug} href={`/products?category=${c.slug}`}>{c.name}</a>)}
        <a href="/#branches">สาขา</a>
      </nav>
      <form className="hdr-search" action="/products" role="search">
        <svg className="ic" viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="M20 20l-4-4" /></svg>
        <label htmlFor="hdr-q" style={{ position: "absolute", left: -9999 }}>ค้นหาสินค้า</label>
        <input id="hdr-q" name="q" type="search" placeholder="ค้นหา เช่น หมูยอ แหนม" />
      </form>
      <a className="icon-btn icon-btn--search" href="/products" aria-label="ค้นหาสินค้า">
        <svg className="ic" viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="M20 20l-4-4" /></svg>
      </a>
      <a className="icon-btn" href="/track" aria-label="ติดตามคำสั่งซื้อ">
        <svg className="ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M3 7h11v9H3zM14 10h4l3 3v3h-7" /><circle cx="7" cy="17" r="1.5" /><circle cx="17" cy="17" r="1.5" /></svg>
        <span className="lbl" aria-hidden="true">ติดตาม</span>
      </a>
      <CartLink />
    </header>
  );
}
