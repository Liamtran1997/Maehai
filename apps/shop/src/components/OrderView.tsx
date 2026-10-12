"use client";
import { StatusPill, formatThaiDate, formatTHB, type OrderStatus } from "@maehai/ui";
import { QRCodeSVG } from "qrcode.react";
import { useCallback, useEffect, useRef, useState } from "react";
import { API_URL, api, errorText, type Order, type Payment } from "../lib/client-api";

const PILL: Record<string, OrderStatus> = {
  pending_quote: "waiting", waiting_payment: "waiting", paid: "paid", packing: "packing", shipped: "shipped", done: "done", cancelled: "cancelled",
};
const POLL_STATUSES = new Set(["pending_quote", "waiting_payment"]);

function useCountdown(iso?: string | null) {
  const [left, setLeft] = useState<number | null>(null);
  useEffect(() => {
    if (!iso) return setLeft(null);
    const tick = () => setLeft(Math.max(0, Math.floor((new Date(iso).getTime() - Date.now()) / 1000)));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [iso]);
  return left;
}

export function OrderView({ number, token }: { number: string; token: string }) {
  const [order, setOrder] = useState<Order | null>(null);
  const [missing, setMissing] = useState(false);
  const [netError, setNetError] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await api.GET("/api/orders/{number}", { params: { path: { number }, query: { token } } });
      if (res.response.status === 404) return setMissing(true);
      if (res.data) { setOrder(res.data); setNetError(false); }
    } catch { setNetError(true); }
  }, [number, token]);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => {
    if (!order || !POLL_STATUSES.has(order.status) && order.payment?.status !== "slip_submitted") return;
    const id = setInterval(load, 5000);
    return () => clearInterval(id);
  }, [order, load]);

  if (missing) {
    return (
      <section className="sec"><div className="notice notice--warn"><p>ไม่พบคำสั่งซื้อนี้ ลิงก์อาจไม่ถูกต้อง ลอง<a href="/track" className="bold">ค้นหาด้วยเลขที่และเบอร์โทร</a></p></div></section>
    );
  }
  if (!order) return <section className="sec"><p className="ink-muted" aria-live="polite">{netError ? "เชื่อมต่อไม่ได้ กำลังลองใหม่…" : "กำลังโหลด…"}</p></section>;

  return (
    <section className="sec sec--tight" style={{ gap: 20 }}>
      <div className="panel">
        <div className="rowline"><span className="mh-code">{order.number}</span><StatusPill status={PILL[order.status]} /></div>
        <p className="sm ink-muted">{order.status_label} · นัดรับ {formatThaiDate(order.requested_date)} · {order.shipping_method.name}</p>
      </div>

      {order.status === "pending_quote" && (
        <div className="notice notice--info" role="status"><p>ร้านกำลังคำนวณค่าจัดส่ง จะแจ้งทางโทรศัพท์หรือ LINE แล้วหน้านี้จะแสดง QR ชำระเงินให้อัตโนมัติ เก็บลิงก์หน้านี้ไว้ได้</p></div>
      )}
      {order.status === "waiting_payment" && <PayPanel order={order} onChange={load} />}
      {order.status === "cancelled" && <div className="notice notice--warn"><p>คำสั่งซื้อนี้ถูกยกเลิก หากชำระเงินแล้วกรุณาติดต่อร้าน LINE @maehai</p></div>}
      {!["done", "cancelled"].includes(order.status) && (order.line_linked ? (
        <div className="notice notice--ok"><p>เชื่อมต่อ LINE แล้ว ร้านจะแจ้งเมื่อมีค่าจัดส่ง ได้รับเงิน และจัดส่งสินค้า</p></div>
      ) : order.line_link_url && (
        <div className="panel">
          <h2 style={{ font: "600 18px/1.6 var(--font-sans)" }}>รับแจ้งเตือนทาง LINE</h2>
          <p className="sm ink-muted">กดปุ่มแล้วส่งข้อความที่เตรียมไว้ให้ร้าน เพื่อให้ร้านแจ้งค่าจัดส่งและสถานะคำสั่งซื้อทาง LINE ไม่ต้องเปิดหน้านี้ค้างไว้</p>
          <a className="mh-btn mh-btn--primary btn-link" href={order.line_link_url} target="_blank" rel="noreferrer">เชื่อมต่อ LINE @maehai</a>
        </div>
      ))}
      {order.tracking_ref && <div className="panel"><p className="sm ink-muted">เลขพัสดุ / ใบฝากส่ง</p><p className="mh-code">{order.tracking_ref}</p></div>}

      <div className="panel">
        <h2 style={{ font: "600 18px/1.6 var(--font-sans)" }}>รายการสินค้า</h2>
        {order.items.map((i) => (
          <div key={i.sku} className="rowline"><span>{i.product_name} ({i.variant_label}) × {i.quantity}</span><span className="num">{formatTHB(i.line_total_satang)}</span></div>
        ))}
        <hr className="hr" />
        <div className="rowline"><span className="ink-muted">ยอดสินค้า</span><span className="num">{formatTHB(order.subtotal_satang)}</span></div>
        <div className="rowline"><span className="ink-muted">ค่าจัดส่ง</span><span className="num">{order.shipping_fee_satang === null ? "รอร้านแจ้ง" : formatTHB(order.shipping_fee_satang)}</span></div>
        <div className="rowline"><span className="bold">รวมทั้งสิ้น</span><span className="mh-price num">{order.total_satang === null ? "—" : formatTHB(order.total_satang)}</span></div>
      </div>

      <div className="panel">
        <h2 style={{ font: "600 18px/1.6 var(--font-sans)" }}>ความคืบหน้า</h2>
        <ol className="tl">
          {order.events.map((e, i) => (
            <li key={i} className={i === order.events.length - 1 ? "now" : "done"}>
              <span className="pt">{i === order.events.length - 1 ? "" : "✓"}</span>
              <div><h3>{e.kind === "created" ? "รับคำสั่งซื้อ" : e.kind === "slip_submitted" ? `ส่งสลิปแล้ว ${e.detail}` : e.detail || e.kind}</h3><p className="xs ink-muted">{new Date(e.created_at).toLocaleString("th-TH", { dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Bangkok" })}</p></div>
            </li>
          ))}
        </ol>
      </div>
      <div className="panel"><p className="sm ink-muted">มีคำถามเรื่องคำสั่งซื้อ แชทกับร้านทาง LINE @maehai หรือโทร 081-878-5474</p></div>
    </section>
  );
}

function PayPanel({ order, onChange }: { order: Order; onChange: () => void | Promise<void> }) {
  const [payment, setPayment] = useState<Payment | null>(order.payment ?? null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const left = useCountdown(payment?.status === "pending" ? payment.expires_at : null);

  const charge = useCallback(async () => {
    setBusy(true); setError(null);
    const res = await api.POST("/api/payments/{number}/charge", { params: { path: { number: order.number }, query: { token: order.token } } }).catch(() => null);
    setBusy(false);
    if (res?.data) setPayment(res.data); else setError(res ? errorText(res.error) : "เชื่อมต่อไม่ได้ ลองใหม่อีกครั้ง");
  }, [order.number, order.token]);

  useEffect(() => { if (!payment || (payment.status === "pending" && !payment.qr_payload)) void charge(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const expired = payment?.status === "pending" && left === 0;

  async function sendSlip() {
    const file = fileRef.current?.files?.[0];
    if (!file) return setError("เลือกรูปสลิปก่อน");
    setBusy(true); setError(null);
    const fd = new FormData();
    fd.append("slip", file);
    try {
      const r = await fetch(`${API_URL}/api/payments/${order.number}/slip?token=${encodeURIComponent(order.token)}`, { method: "POST", body: fd });
      const body = await r.json().catch(() => ({}));
      if (!r.ok) setError(errorText(body)); else { setPayment(body); await onChange(); }
    } catch { setError("เชื่อมต่อไม่ได้ ลองใหม่อีกครั้ง"); }
    setBusy(false);
  }

  const mm = left === null ? "" : `${String(Math.floor(left / 60)).padStart(2, "0")}:${String(left % 60).padStart(2, "0")}`;

  if (payment?.status === "slip_submitted") {
    return <div className="notice notice--info" role="status"><p>ร้านได้รับสลิปแล้ว กำลังตรวจสอบ ปกติใช้เวลาไม่กี่นาที หน้านี้จะอัปเดตเอง</p></div>;
  }

  return (
    <div className="mh-pay" style={{ maxWidth: "none" }}>
      <div className="mh-pay__bar"><span>ชำระผ่าน PromptPay</span>{mm && !expired && <span className="num" style={{ color: "var(--warning)" }}>เหลือ {mm} นาที</span>}</div>
      {payment?.status === "rejected" && <div className="notice notice--warn"><p>สลิปไม่ผ่าน: {payment.reject_reason || "กรุณาตรวจสอบยอดและลองใหม่"}</p></div>}
      {payment?.qr_payload && !expired ? (
        <div className="mh-pay__qr" style={{ width: 240, maxWidth: "100%", marginInline: "auto", border: "none", background: "#fff", padding: 12 }} role="img" aria-label={`QR PromptPay ยอด ${formatTHB(payment.amount_satang)}`}>
          <QRCodeSVG value={payment.qr_payload} size={216} marginSize={0} />
        </div>
      ) : (
        <div className="mh-pay__qr" style={{ width: 240, maxWidth: "100%", marginInline: "auto" }}>{expired ? "QR หมดอายุ" : "กำลังสร้าง QR…"}</div>
      )}
      <div><p className="sm ink-muted">ยอดที่ต้องชำระ</p><p className="mh-pay__amount">{formatTHB(payment?.amount_satang ?? order.total_satang ?? 0)}</p></div>
      {expired ? (
        <button className="mh-btn mh-btn--primary" type="button" onClick={charge} disabled={busy}>สร้าง QR ใหม่</button>
      ) : (
        <p className="sm ink-muted">สแกนด้วยแอปธนาคารหรือ Mobile Banking ใดก็ได้ ยอดเงินใส่ให้แล้ว</p>
      )}

      <hr className="hr" />
      <div className="mh-field" style={{ textAlign: "left" }}>
        <label className="mh-label" htmlFor="slip">โอนแล้ว แนบสลิป</label>
        <input className="mh-input" style={{ paddingTop: 8 }} id="slip" type="file" accept="image/jpeg,image/png,image/webp" ref={fileRef} />
        <span className="mh-help">JPG, PNG หรือ WebP ไม่เกิน 5 MB</span>
      </div>
      {error && <div className="notice notice--warn" role="alert"><p>{error}</p></div>}
      <button className="mh-btn mh-btn--secondary" type="button" onClick={sendSlip} disabled={busy}>{busy ? "กำลังส่ง…" : "ส่งสลิป"}</button>
    </div>
  );
}
