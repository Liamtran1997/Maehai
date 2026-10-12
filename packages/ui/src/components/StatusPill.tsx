export type OrderStatus = "waiting" | "paid" | "packing" | "shipped" | "done" | "cancelled";

const META: Record<OrderStatus, { label: string; glyph: string; cls: string }> = {
  waiting: { label: "รอชำระเงิน", glyph: "○", cls: "wait" },
  paid: { label: "ชำระแล้ว", glyph: "●", cls: "paid" },
  packing: { label: "กำลังจัดเตรียม", glyph: "◐", cls: "pack" },
  shipped: { label: "จัดส่งแล้ว", glyph: "→", cls: "ship" },
  done: { label: "สำเร็จ", glyph: "✓", cls: "done" },
  cancelled: { label: "ยกเลิก", glyph: "✕", cls: "cancel" },
};

export function StatusPill({ status }: { status: OrderStatus }) {
  const m = META[status];
  return (
    <span className={`mh-status mh-status--${m.cls}`} data-glyph={m.glyph}>
      {m.label}
    </span>
  );
}
