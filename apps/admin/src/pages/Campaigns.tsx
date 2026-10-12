import { formatThaiDate, formatTHB } from "@maehai/ui";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { ErrorNotice } from "../components/Notice";
import { api, unwrap } from "../lib/api";

const RANGES = [7, 30, 90];
const SCOPE: Record<string, string> = { products: "สินค้าที่เลือก", categories: "ทั้งหมวดหมู่", all: "ทุกสินค้า" };

function lift(p: number | null) {
  if (p === null) return <span className="ink-muted">ไม่มีข้อมูลช่วงก่อน</span>;
  return <span className={p >= 0 ? "bold" : ""} style={{ color: p >= 0 ? "var(--success)" : "var(--danger)" }}>{p >= 0 ? "▲" : "▼"} {Math.abs(p)}%</span>;
}

export function Campaigns() {
  const [days, setDays] = useState(30);
  const q = useQuery({ queryKey: ["campaigns", days], queryFn: async () => unwrap(await api.GET("/api/admin/reports/campaigns", { params: { query: { days } } })) });

  return (
    <>
      <div className="topbar">
        <h1>รายงานโปรโมชันและโค้ด</h1>
        <div className="seg" role="group" aria-label="ช่วงเวลา">
          {RANGES.map((d) => <button key={d} aria-pressed={days === d} onClick={() => setDays(d)}>{d} วัน</button>)}
        </div>
      </div>
      <p className="sm ink-muted">นับเฉพาะออเดอร์ที่ชำระเงินแล้วและไม่ถูกยกเลิก “เพิ่มขึ้น” เทียบอัตราการขายต่อวันของสินค้าเดียวกันในช่วงเท่ากันก่อนโปรโมชันเริ่ม</p>
      <ErrorNotice error={q.error} />

      <section className="apanel">
        <h2>โปรโมชันรายสินค้า</h2>
        {q.data?.promotions.length === 0 && <p className="ink-muted">ไม่มีโปรโมชันที่ทำงานในช่วงนี้</p>}
        {q.data && q.data.promotions.length > 0 && (
          <div className="mh-tablewrap" style={{ border: 0 }}>
            <table className="mh-table">
              <thead><tr><th>โปรโมชัน</th><th>ใช้กับ</th><th className="r">ออเดอร์</th><th className="r">ชิ้น</th><th className="r">ยอดขาย</th><th className="r">ส่วนลดที่ให้</th><th className="r">ต่อวัน (ก่อน → ตอนนี้)</th><th>ผล</th></tr></thead>
              <tbody>
                {q.data.promotions.map((p) => (
                  <tr key={p.id}>
                    <td><span className="bold">{p.name}</span><br /><span className="xs ink-muted">{p.label} · {formatThaiDate(p.starts_at)}{p.ends_at ? ` ถึง ${formatThaiDate(p.ends_at)}` : ""}</span></td>
                    <td className="xs">{SCOPE[p.scope]}</td>
                    <td className="r">{p.orders}</td><td className="r">{p.units}</td>
                    <td className="r">{formatTHB(p.revenue_satang, { hideZeroSatang: true })}</td>
                    <td className="r">{formatTHB(p.discount_satang, { hideZeroSatang: true })}</td>
                    <td className="r num">{p.units_per_day_before} → {p.units_per_day}</td>
                    <td>{lift(p.lift_percent)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="apanel">
        <h2>โค้ดส่วนลด</h2>
        {q.data?.coupons.length === 0 && <p className="ink-muted">ไม่มีการใช้โค้ดในช่วงนี้</p>}
        {q.data && q.data.coupons.length > 0 && (
          <div className="mh-tablewrap" style={{ border: 0 }}>
            <table className="mh-table">
              <thead><tr><th>โค้ด</th><th className="r">ใช้แล้ว</th><th className="r">ยกเลิก (คืนสิทธิ์)</th><th className="r">ออเดอร์</th><th className="r">ยอดขายที่ได้</th><th className="r">ส่วนลดที่ให้</th><th className="r">เฉลี่ยต่อออเดอร์</th><th className="r">ส่งฟรี</th></tr></thead>
              <tbody>
                {q.data.coupons.map((c) => (
                  <tr key={c.id}>
                    <td><span className="mh-code bold">{c.code}</span><br /><span className="xs ink-muted">{c.label}</span></td>
                    <td className="r">{c.uses}</td><td className="r">{c.cancelled}</td><td className="r">{c.orders}</td>
                    <td className="r">{formatTHB(c.revenue_satang, { hideZeroSatang: true })}</td>
                    <td className="r">{formatTHB(c.discount_satang, { hideZeroSatang: true })}</td>
                    <td className="r">{formatTHB(c.average_discount_satang, { hideZeroSatang: true })}</td>
                    <td className="r">{c.free_shipping_orders}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
