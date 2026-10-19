import { ShopHeader } from "../../components/ShopHeader";
import { ProductGrid } from "../../components/ProductGrid";
import { TrackOnMount } from "../../components/Analytics";
import { getCategories, getProducts } from "../../lib/api";

export const metadata = { title: "สินค้าของเรา | ร้านหมูยอแม่ฮาย" };

const chip = { display: "inline-flex", alignItems: "center" } as const;

export default async function Catalog({ searchParams }: { searchParams: Promise<{ category?: string; q?: string }> }) {
  const { category, q } = await searchParams;
  const [categories, products] = await Promise.all([getCategories(), getProducts({ category, q })]);

  return (
    <>
      <ShopHeader categories={categories} />
      {q && <TrackOnMount key={`${q}-${products.length}`} kind="search" data={{ name: q.slice(0, 40), value: products.length }} />}
      <section className="sec sec--tight catalog-head" style={{ paddingTop: 24 }}>
        <h1 style={{ font: "500 32px/1.4 var(--font-display)" }}>สินค้าของเรา</h1>
        <form className="searchbox" action="/products" role="search">
          <svg className="ic" viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="M20 20l-4-4" /></svg>
          <label className="mh-label" htmlFor="q" style={{ position: "absolute", left: -9999 }}>ค้นหาสินค้า</label>
          <input className="mh-input" id="q" name="q" defaultValue={q} placeholder="ค้นหา เช่น หมูยอ แหนม" />
          {category && <input type="hidden" name="category" value={category} />}
        </form>
        <div className="scroll-x" role="group" aria-label="ประเภทสินค้า">
          <a className="mh-chip btn-link" style={chip} href="/products" aria-current={!category ? "true" : undefined}>ทั้งหมด</a>
          {categories.map((c) => (
            <a key={c.slug} className="mh-chip btn-link" style={chip} href={`/products?category=${c.slug}`} aria-current={category === c.slug ? "true" : undefined}>{c.name}</a>
          ))}
        </div>
        <p className="sm ink-muted">{products.length} รายการ</p>
      </section>
      <section className="sec" style={{ paddingTop: 0 }}>
        {products.length === 0 ? (
          <p className="ink-muted">ไม่พบสินค้าที่ตรงกับที่ค้นหา</p>
        ) : (
          <ProductGrid products={products} headingLevel={2} eagerCount={4} />
        )}
      </section>
    </>
  );
}
