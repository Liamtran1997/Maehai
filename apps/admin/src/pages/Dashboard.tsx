import { StatTile, StatusPill, formatThaiDate, formatTHB } from "@maehai/ui";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { ErrorNotice } from "../components/Notice";
import { RevenueChart } from "../components/RevenueChart";
import { api, unwrap } from "../lib/api";
import { useAuth } from "../lib/auth";
import { PILL } from "../lib/status";

const RANGES = [{ days: 1, label: "วันนี้" }, { days: 7, label: "7 วัน" }, { days: 30, label: "30 วัน" }];

function delta(cur: number, prev: number, higherIsBetter = true) {
  if (prev === 0) return undefined;
  const pct = ((cur - prev) / prev) * 100;
  if (Math.abs(pct) < 0.05) return undefined;
  const up = pct > 0;
  return { text: `${Math.abs(pct).toFixed(1)}%`, direction: (up === higherIsBetter ? "up" : "down") as "up" | "down", note: "จากช่วงก่อนหน้า" };
}

export function Dashboard() {
  const { can } = useAuth();
  const [days, setDays] = useState(7);
  const showMoney = can("reports.view");
  const todoOnly = useQuery({ queryKey: ["todo"], enabled: !showMoney, queryFn: async () => unwrap(await api.GET("/api/admin/reports/todo")) });
  const q = useQuery({ queryKey: ["summary", days], enabled: showMoney, queryFn: async () => unwrap(await api.GET("/api/admin/reports/summary", { params: { query: { days } } })) });
  const recent = useQuery({ queryKey: ["orders", "recent"], enabled: can("orders.view"), queryFn: async () => unwrap(await api.GET("/api/admin/orders", { params: { query: { limit: 5 } } })) });
  const s = q.data;
  const maxQty = Math.max(1, ...(s?.top_products.map((p) => p.quantity) ?? [1]));
  const maxShip = Math.max(1, ...(s?.by_shipping.map((p) => p.revenue_satang) ?? [1]));

  return (
    <>
      <div className="topbar">
        <h1>ภาพรวม</h1>
        {showMoney && <div className="seg" role="group" aria-label="ช่วงเวลา">
          {RANGES.map((r) => <button key={r.days} aria-pressed={days === r.days} onClick={() => setDays(r.days)}>{r.label}</button>)}
        </div>}
      </div>
      {!showMoney && todoOnly.data && (
        <section className="apanel">
          <h2>ต้องจัดการ</h2>
          <ul className="todo">
            {can("payments.review") && <li><span className="n num">{todoOnly.data.slips_to_check}</span><span className="grow">สลิปรอตรวจ</span></li>}
            {can("orders.quote") && <li><span className="n num">{todoOnly.data.pending_quote}</span><span className="grow">รอร้านแจ้งค่าจัดส่ง</span></li>}
            {can("orders.fulfil") && <li><span className="n num">{todoOnly.data.to_pack}</span><span className="grow">ชำระแล้ว รอจัดเตรียม</span></li>}
            {can("inventory.view") && <li><span className="n num">{todoOnly.data.low_stock}</span><span className="grow">สินค้าใกล้หมด (ตามสาขา)</span></li>}
            {can("inventory.view") && <li><span className="n num">{todoOnly.data.slips_to_receive}</span><span className="grow">ใบส่ง/คืนสินค้ารอสาขายืนยัน</span></li>}
          </ul>
        </section>
      )}
      <ErrorNotice error={q.error} />
      {q.isLoading && <p className="ink-muted">กำลังโหลด…</p>}
      {s && (
        <>
          <p className="sm ink-muted">นับยอดขายตามวันที่ยืนยันการชำระเงิน เวลาประเทศไทย ไม่รวมคำสั่งซื้อที่ยกเลิกหรือยังไม่ชำระ</p>
          <div className="tiles">
            <StatTile label="ยอดขาย" value={formatTHB(s.current.revenue_satang, { hideZeroSatang: true })} delta={delta(s.current.revenue_satang, s.previous.revenue_satang)} series={s.daily.map((d) => d.revenue_satang)} />
            <StatTile label="คำสั่งซื้อที่ชำระแล้ว" value={String(s.current.paid_orders)} delta={delta(s.current.paid_orders, s.previous.paid_orders)} />
            <StatTile label="ยอดเฉลี่ยต่อคำสั่งซื้อ" value={formatTHB(s.current.avg_order_satang, { hideZeroSatang: true })} delta={delta(s.current.avg_order_satang, s.previous.avg_order_satang)} />
            <StatTile label="สั่งเข้ามาใหม่" value={String(s.orders_created)} />
          </div>

          <div className="cols cols--2-1">
            <section className="apanel"><h2>ยอดขายรายวัน</h2><RevenueChart daily={s.daily} /></section>
            <section className="apanel">
              <h2>ต้องจัดการ</h2>
              <ul className="todo">
                <li><span className="n num">{s.todo.slips_to_check}</span><span className="grow">สลิปรอตรวจ</span><Link className="mh-btn mh-btn--secondary mh-btn--sm btn-link" to="/orders?status=waiting_payment">ตรวจ</Link></li>
                <li><span className="n num">{s.todo.pending_quote}</span><span className="grow">รอร้านแจ้งค่าจัดส่ง</span><Link className="mh-btn mh-btn--secondary mh-btn--sm btn-link" to="/orders?status=pending_quote">แจ้ง</Link></li>
                <li><span className="n num">{s.todo.to_pack}</span><span className="grow">ชำระแล้ว รอจัดเตรียม</span><Link className="mh-btn mh-btn--secondary mh-btn--sm btn-link" to="/orders?status=paid">เปิด</Link></li>
                <li><span className="n num">{s.todo.low_stock}</span><span className="grow">สินค้าใกล้หมด (ตามสาขา)</span><Link className="mh-btn mh-btn--secondary mh-btn--sm btn-link" to="/warehouse?tab=stock">ดู</Link></li>
                <li><span className="n num">{s.todo.slips_to_receive}</span><span className="grow">ใบส่ง/คืนสินค้ารอสาขายืนยัน</span><Link className="mh-btn mh-btn--secondary mh-btn--sm btn-link" to="/warehouse">ดู</Link></li>
                <li><span className="n num">{s.todo.waiting_payment}</span><span className="grow">รอลูกค้าชำระเงิน</span><Link className="mh-btn mh-btn--secondary mh-btn--sm btn-link" to="/orders?status=waiting_payment">ดู</Link></li>
              </ul>
            </section>
          </div>

          <div className="cols">
            <section className="apanel">
              <h2>สินค้าขายดี (ชิ้น)</h2>
              {s.top_products.length === 0 ? <p className="ink-muted">ยังไม่มียอดขายในช่วงนี้</p> : (
                <ul className="hbar">{s.top_products.map((p) => (
                  <li key={p.name}><span>{p.name}</span><span className="track"><span className="fill" style={{ display: "block", width: `${(p.quantity / maxQty) * 100}%` }} /></span><span className="num bold">{p.quantity}</span></li>
                ))}</ul>
              )}
            </section>
            <section className="apanel">
              <h2>ยอดขายตามวิธีรับสินค้า</h2>
              {s.by_shipping.length === 0 ? <p className="ink-muted">ยังไม่มียอดขายในช่วงนี้</p> : (
                <ul className="hbar">{s.by_shipping.map((p) => (
                  <li key={p.name}><span>{p.name}</span><span className="track"><span className="fill fill--y" style={{ display: "block", width: `${(p.revenue_satang / maxShip) * 100}%` }} /></span><span className="num bold">{formatTHB(p.revenue_satang, { hideZeroSatang: true })}</span></li>
                ))}</ul>
              )}
            </section>
          </div>
        </>
      )}

      {can("orders.view") && <section className="apanel">
        <div className="apanel-head"><h2>คำสั่งซื้อล่าสุด</h2><Link className="sm bold" to="/orders">ดูทั้งหมด</Link></div>
        <div className="mh-tablewrap" style={{ border: 0 }}>
          <table className="mh-table">
            <thead><tr><th>เลขที่สั่งซื้อ</th><th>ลูกค้า</th><th>วิธีรับ</th><th className="r">ยอดรวม</th><th>สถานะ</th><th>สั่งเมื่อ</th></tr></thead>
            <tbody>
              {recent.data?.items.map((o) => (
                <tr key={o.number}>
                  <td><Link className="mh-code" to={`/orders/${o.number}`}>{o.number}</Link></td><td>{o.customer_name}</td><td>{o.shipping_method.name}</td>
                  <td className="r">{o.total_satang === null ? "รอแจ้งค่าส่ง" : formatTHB(o.total_satang)}</td><td><StatusPill status={PILL[o.status]} /></td><td>{formatThaiDate(o.created_at)}</td>
                </tr>
              ))}
              {recent.data?.items.length === 0 && <tr><td colSpan={6} className="ink-muted">ยังไม่มีคำสั่งซื้อ</td></tr>}
            </tbody>
          </table>
        </div>
      </section>}
    </>
  );
}
