import { formatThaiDate } from "@maehai/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { ErrorNotice } from "../../components/Notice";
import { api, unwrap } from "../../lib/api";

export function useBranches() {
  return useQuery({ queryKey: ["branches"], queryFn: async () => unwrap(await api.GET("/api/admin/inventory/branches")) });
}

export function useStockItems() {
  return useQuery({ queryKey: ["stock", ""], queryFn: async () => unwrap(await api.GET("/api/admin/inventory/stock", { params: { query: {} } })) });
}

export function useMaterials() {
  return useQuery({ queryKey: ["materials"], queryFn: async () => unwrap(await api.GET("/api/admin/inventory/materials", { params: { query: {} } })) });
}

export function useSources() {
  return useQuery({ queryKey: ["sources"], queryFn: async () => unwrap(await api.GET("/api/admin/inventory/sources", { params: { query: { include_hidden: true } } })) });
}

/** Lines of a slip: a tracked size or a material, a quantity, and (receipts only) a unit cost. */
export function LineBuilder({ lines, onChange, items, withCost }: {
  lines: Line[]; onChange: (l: Line[]) => void; items: { value: string; label: string }[]; withCost?: boolean;
}) {
  const set = (i: number, patch: Partial<Line>) => onChange(lines.map((l, j) => (j === i ? { ...l, ...patch } : l)));
  return (
    <div style={{ display: "grid", gap: 8 }}>
      {lines.map((l, i) => (
        <div key={i} className="mh-row" style={{ gap: 8, flexWrap: "nowrap" }}>
          <select className="mh-select" aria-label={`รายการที่ ${i + 1}`} style={{ flex: 1, minWidth: 0 }} value={l.item} onChange={(e) => set(i, { item: e.target.value })}>
            <option value="">— เลือกรายการ —</option>
            {items.map((it) => <option key={it.value} value={it.value}>{it.label}</option>)}
          </select>
          <input className="mh-input num" aria-label={`จำนวนที่ ${i + 1}`} inputMode="decimal" placeholder="จำนวน" style={{ width: 110 }} value={l.quantity} onChange={(e) => set(i, { quantity: e.target.value })} />
          {withCost && <input className="mh-input num" aria-label={`ราคาต่อหน่วย (สตางค์) ${i + 1}`} inputMode="numeric" placeholder="ราคา/หน่วย" style={{ width: 120 }} value={l.cost} onChange={(e) => set(i, { cost: e.target.value })} />}
          <button type="button" className="mh-btn mh-btn--secondary mh-btn--sm" onClick={() => onChange(lines.filter((_, j) => j !== i))}>ลบ</button>
        </div>
      ))}
      <button type="button" className="mh-btn mh-btn--secondary mh-btn--sm" style={{ justifySelf: "start" }} onClick={() => onChange([...lines, { item: "", quantity: "", cost: "" }])}>+ เพิ่มรายการ</button>
    </div>
  );
}

/** Turn the builder's lines into the API shape. Sizes are sent by SKU, materials by code. */
export function toApiLines(lines: Line[], withCost: boolean) {
  return lines.filter((l) => l.item).map((l) => {
    const [kind, key] = [l.item.slice(0, 2), l.item.slice(2)];
    return {
      sku: kind === "p:" ? key : null,
      material_code: kind === "m:" ? key : null,
      quantity: l.quantity.trim(),
      unit_cost_satang: withCost && l.cost.trim() ? Number(l.cost) : null,
    };
  });
}

export function itemOptions(stock: StockRow[] | undefined, mats: MatRow[] | undefined) {
  return [
    ...(stock ?? []).filter((r) => r.track_stock).map((r) => ({ value: `p:${r.sku}`, label: `${r.product_name} (${r.variant_label})` })),
    ...(mats ?? []).map((m) => ({ value: `m:${m.code}`, label: `${m.name} · ${m.unit}` })),
  ];
}

export function Created({ number }: { number: string | null }) {
  if (!number) return null;
  return <div className="notice notice--ok" role="status"><p>บันทึกแล้ว เลขที่ {number}</p></div>;
}

export const REFUSE = [
  { v: "damaged", l: "ชำรุด" },
  { v: "wrong", l: "ไม่ตรงรายการ" },
  { v: "other", l: "อื่นๆ" },
  { v: "missing", l: "ขาด (หายระหว่างทาง)" },
];

export const today = () => new Date().toISOString().slice(0, 10);

export type StockRow = { sku: string; product_name: string; variant_label: string; track_stock: boolean };

export type MatRow = { code: string; name: string; kind: string; kind_label: string; unit: string; low_stock_threshold: string | null; note: string; is_active: boolean; in_use: boolean };

export type Line = { item: string; quantity: string; cost: string };

export type DocLine = { id: number; name: string; unit: string; sent: string; received: string | null; refused: string; missing: string; refuse_reason: string; refuse_note: string };

export type FullDoc = NonNullable<Awaited<ReturnType<typeof getDoc>>>;

export async function getDoc(number: string) {
  return unwrap(await api.GET("/api/admin/inventory/documents/{number}", { params: { path: { number } } }));
}
