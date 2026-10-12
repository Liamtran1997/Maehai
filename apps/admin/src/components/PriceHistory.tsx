import { formatThaiDate, formatTHB } from "@maehai/ui";
import { useQuery } from "@tanstack/react-query";
import { api, unwrap } from "../lib/api";

/** Every price change of a product's sizes: who, when, from what to what. Pricing managers only. */
export function PriceHistory({ productId }: { productId: number }) {
  const rows = useQuery({
    queryKey: ["price-history", productId],
    queryFn: async () => unwrap(await api.GET("/api/admin/catalog/products/{product_id}/price-history", { params: { path: { product_id: productId } } })),
    retry: false,
  });
  if (rows.error) return null;                          // no permission to see prices: show nothing
  return (
    <section style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <p className="mh-label">ประวัติการเปลี่ยนราคา</p>
      {rows.data?.length === 0 && <p className="xs ink-muted">ยังไม่เคยเปลี่ยนราคา</p>}
      <ol className="tl" style={{ maxHeight: 240, overflowY: "auto" }}>
        {rows.data?.map((r, i) => (
          <li key={i} className="done">
            <span className="pt" />
            <div>
              <h3>{r.label} · {r.old_price_satang === null ? `ตั้งราคาเริ่มต้น ${formatTHB(r.new_price_satang)}` : `${formatTHB(r.old_price_satang)} → ${formatTHB(r.new_price_satang)}`}</h3>
              <p className="xs ink-muted">{formatThaiDate(r.created_at)} · {r.actor}</p>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
