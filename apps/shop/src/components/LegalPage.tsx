import type { ReactNode } from "react";
import { ShopHeader } from "./ShopHeader";

/** Layout for policy pages. Text marked [ระบุ] must be completed by the shop owner. */
export function LegalPage({ title, updated, children }: { title: string; updated: string; children: ReactNode }) {
  return (
    <>
      <ShopHeader />
      <article className="sec sec--tight" style={{ paddingTop: 24, gap: 16, maxWidth: 720, marginInline: "auto" }}>
        <div className="notice notice--info" role="note">
          <p>ฉบับร่าง รอเจ้าของร้านกรอกข้อมูลในช่อง [ระบุ] และให้ที่ปรึกษากฎหมายตรวจก่อนเปิดใช้งาน</p>
        </div>
        <h1 style={{ font: "500 30px/1.4 var(--font-display)" }}>{title}</h1>
        <p className="xs ink-muted">ปรับปรุงล่าสุด {updated}</p>
        <div style={{ display: "flex", flexDirection: "column", gap: 12, lineHeight: 1.8 }}>{children}</div>
      </article>
    </>
  );
}
