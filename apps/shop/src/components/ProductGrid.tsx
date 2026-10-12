import { ProductCard } from "@maehai/ui";
import { BADGE_LABEL, toBands, type Product } from "../lib/api";

export function ProductGrid({ products }: { products: Product[] }) {
  return (
    <div className="pgrid">
      {products.map((p) => (
        <ProductCard
          key={p.slug}
          name={p.name}
          subtitle={p.subtitle || undefined}
          priceSatang={p.price_from_satang}
          badge={p.in_stock === false ? { label: "หมด", tone: "red" } : BADGE_LABEL[p.badge]}
          bands={toBands(p.bands)}
          imageSrc={p.image_url ?? undefined}
          href={`/products/${p.slug}`}
        />
      ))}
    </div>
  );
}
