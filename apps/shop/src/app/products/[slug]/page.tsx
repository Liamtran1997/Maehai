import { formatThaiDate } from "@maehai/ui";
import { Gallery } from "../../../components/Gallery";
import { AddToCart } from "../../../components/AddToCart";
import { notFound } from "next/navigation";
import { ShopHeader } from "../../../components/ShopHeader";
import { ProductGrid } from "../../../components/ProductGrid";
import { TrackOnMount } from "../../../components/Analytics";
import { BADGE_LABEL, getCategories, getProduct, getProducts, toBands } from "../../../lib/api";

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const p = await getProduct((await params).slug);
  return { title: p ? `${p.name} | ร้านหมูยอแม่ฮาย` : "ไม่พบสินค้า" };
}

export default async function ProductPage({ params }: { params: Promise<{ slug: string }> }) {
  const p = await getProduct((await params).slug);
  if (!p) notFound();
  const badge = p.in_stock === false ? { label: "หมด" } : BADGE_LABEL[p.badge];
  const [categories, inCategory] = await Promise.all([getCategories(), getProducts({ category: p.category.slug })]);
  const related = inCategory.filter((x) => x.slug !== p.slug).slice(0, 4);
  const ico = (d: string) => <svg className="ic" viewBox="0 0 24 24" aria-hidden="true"><path d={d} /></svg>;
  const chev = <svg className="ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 9l6 6 6-6" /></svg>;
  const info = [
    p.description && { title: "รายละเอียดสินค้า", body: p.description },
    p.ingredients && { title: "ส่วนผสม", body: p.ingredients },
    p.storage_note && { title: "การเก็บรักษา", body: p.storage_note },
    p.fda_number && { title: "เลข อย.", body: p.fda_number, num: true },
  ].filter((x): x is { title: string; body: string; num?: boolean } => !!x);

  return (
    <>
      <ShopHeader categories={categories} />
      <TrackOnMount kind="product_view" data={{ slug: p.slug }} />
      <div className="pdp">
        <nav className="crumbs" aria-label="เส้นทางหน้า">
          <a href="/">หน้าแรก</a> › <a href={`/products?category=${p.category.slug}`}>{p.category.name}</a> › <span aria-current="page">{p.name}</span>
        </nav>
        <div className="pdp-gallery">
          <Gallery images={p.images} name={p.name} bands={toBands(p.bands)} badge={badge?.label} />
        </div>
        <div className="pdp-info">
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {p.bands.length > 0 && (
              <span className="bandtag">
                {p.bands.map((b) => <span key={b} className="bandmark"><i className={`c-${b}`} /></span>)}
                {p.subtitle || "ยางสีบอกรส"}
              </span>
            )}
            <h1>{p.name}</h1>
            {p.subtitle && p.bands.length === 0 && <p className="ink-muted">{p.subtitle}</p>}
          </div>

          {p.promotion && (
            <div className="notice notice--warn" role="note">
              <p><b>{p.promotion.label}</b> · {p.promotion.name}{p.promotion.ends_at && ` ถึง ${formatThaiDate(p.promotion.ends_at)}`}</p>
            </div>
          )}
          <AddToCart slug={p.slug} productName={p.name} variants={p.variants} imageUrl={p.images[0]?.url ?? null} />

          <ul className="promise">
            <li>{ico("M12 3a9 9 0 100 18 9 9 0 000-18zM12 7v5l3 2")}<div><b>สั่งก่อน 13:00 น. รับของวันถัดไป</b><span>จัดส่งทุกวัน ยกเว้นวันอาทิตย์</span></div></li>
            <li>{ico("M3 7h11v9H3zM14 10h4l3 3v3h-7")}<div><b>รับที่ร้าน · ฝากขนส่ง · รถไฟ · พัสดุ</b><span>ค่าจัดส่งร้านจะแจ้งหลังรับคำสั่งซื้อ</span></div></li>
            <li>{ico("M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6zM9 12l2 2 4-4")}<div><b>กระทรวงสาธารณสุขรับรอง</b><span>ผลิตสดใหม่ทุกวัน จากวัตถุดิบคัดสรร</span></div></li>
          </ul>

          {info.length > 0 && (
            <div className="accordion">
              {info.map((x, i) => (
                <details key={x.title} open={i === 0}>
                  <summary>{x.title}{chev}</summary>
                  <p className={`acc-body${x.num ? " num" : ""}`}>{x.body}</p>
                </details>
              ))}
            </div>
          )}
        </div>
        {related.length > 0 && (
          <section className="pdp-rel" aria-labelledby="related">
            <h2 id="related">{p.category.name}รสอื่นที่คุณอาจชอบ</h2>
            <ProductGrid products={related} />
          </section>
        )}
      </div>
    </>
  );
}
