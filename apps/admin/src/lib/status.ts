import type { OrderStatus } from "@maehai/ui";

/** API order status -> pill. "Waiting for quote" and "waiting for payment" both show as waiting. */
export const PILL: Record<string, OrderStatus> = {
  pending_quote: "waiting", waiting_payment: "waiting", paid: "paid", packing: "packing", shipped: "shipped", done: "done", cancelled: "cancelled",
};

export const STATUS_TABS = [
  { key: "", label: "ทั้งหมด" },
  { key: "pending_quote", label: "รอแจ้งค่าส่ง" },
  { key: "waiting_payment", label: "รอชำระเงิน" },
  { key: "paid", label: "ชำระแล้ว" },
  { key: "packing", label: "กำลังจัดเตรียม" },
  { key: "shipped", label: "จัดส่งแล้ว" },
  { key: "done", label: "สำเร็จ" },
  { key: "cancelled", label: "ยกเลิก" },
] as const;

/** Staff-driven next steps. Money states move through the fee form and payment confirmation instead. */
export const NEXT_STATUS: Record<string, { to: string; label: string; askTracking?: boolean }[]> = {
  paid: [{ to: "packing", label: "เริ่มจัดเตรียม" }],
  packing: [{ to: "shipped", label: "ฝากขนส่งแล้ว", askTracking: true }, { to: "done", label: "ลูกค้ารับของแล้ว" }],
  shipped: [{ to: "done", label: "ลูกค้ารับของแล้ว" }],
};

export const CAN_CANCEL = new Set(["pending_quote", "waiting_payment", "paid", "packing"]);
