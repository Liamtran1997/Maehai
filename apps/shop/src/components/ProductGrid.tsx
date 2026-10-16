import { ProductCard } from "@maehai/ui";
import { BADGE_LABEL, toBands, type Product } from "../lib/api";

export function ProductGrid({ products, headingLevel, eagerCount = 0 }: { products: Product[]; headingLevel?: 2 | 3; eagerCount?: number }) {
  return (
    <div className="pgrid">
      {products.map((p, i) => (
        <ProductCard
          key={p.slug}
          name={p.name}
          subtitle={p.subtitle || undefined}
          priceSatang={p.price_from_satang}
          originalPriceSatang={p.original_price_from_satang}
          promotionLabel={p.promotion_label}
          badge={p.in_stock === false ? { label: "หมด", tone: "red" } : BADGE_LABEL[p.badge]}
          bands={toBands(p.bands)}
          bandDots={p.bands}
          imageSrc={p.image_url ?? undefined}
          thumbSrc={p.thumb_url ?? undefined}
          href={`/products/${p.slug}`}
          headingLevel={headingLevel}
          eager={i < eagerCount}
        />
      ))}
    </div>
  );
}
