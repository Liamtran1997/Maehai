import { formatThaiDate } from "@maehai/ui";
import { Gallery } from "../../../components/Gallery";
import { AddToCart } from "../../../components/AddToCart";
import { notFound } from "next/navigation";
import { ShopHeader } from "../../../components/ShopHeader";
import { BADGE_LABEL, getProduct, toBands } from "../../../lib/api";

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const p = await getProduct((await params).slug);
  return { title: p ? `${p.name} | ร้านหมูยอแม่ฮาย` : "ไม่พบสินค้า" };
}

export default async function ProductPage({ params }: { params: Promise<{ slug: string }> }) {
  const p = await getProduct((await params).slug);
  if (!p) notFound();
  const badge = p.in_stock === false ? { label: "หมด" } : BADGE_LABEL[p.badge];

  return (
    <>
      <ShopHeader />
      <p className="crumbs" style={{ padding: "12px 16px" }}>สินค้า › {p.category.name}</p>
      <Gallery images={p.images} name={p.name} bands={toBands(p.bands)} badge={badge?.label} />
      <section className="sec" style={{ gap: 20 }}>
        <div>
          <h1 style={{ font: "500 32px/1.4 var(--font-display)" }}>{p.name}</h1>
          {p.subtitle && <p className="ink-muted">{p.subtitle}</p>}
        </div>

        {p.promotion && (
          <div className="notice notice--warn" role="note">
            <p><b>{p.promotion.label}</b> · {p.promotion.name}{p.promotion.ends_at && ` ถึง ${formatThaiDate(p.promotion.ends_at)}`}</p>
          </div>
        )}
        <AddToCart slug={p.slug} productName={p.name} variants={p.variants} />

        {p.description && <p>{p.description}</p>}
        <dl className="panel" style={{ gap: 8 }}>
          <div className="rowline"><dt className="sm ink-muted">เลข อย.</dt><dd className="sm num">{p.fda_number || "อยู่ระหว่างระบุ"}</dd></div>
          {p.storage_note && <><hr className="hr" /><div className="rowline"><dt className="sm ink-muted">การเก็บรักษา</dt><dd className="sm">{p.storage_note}</dd></div></>}
        </dl>
        <div className="notice notice--warn"><p>สั่งก่อน 13:00 น. รับของวันถัดไป ค่าจัดส่งร้านจะแจ้งหลังรับคำสั่งซื้อ</p></div>
      </section>
    </>
  );
}
