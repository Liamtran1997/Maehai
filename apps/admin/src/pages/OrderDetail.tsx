import { StatusPill, formatThaiDate, formatTHB } from "@maehai/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ErrorNotice } from "../components/Notice";
import { api, bahtToSatang, unwrap, type Order } from "../lib/api";
import { useAuth } from "../lib/auth";
import { CAN_CANCEL, NEXT_STATUS, PILL } from "../lib/status";

export function OrderDetail() {
  const { number = "" } = useParams();
  const qc = useQueryClient();
  const { can } = useAuth();
  const key = ["order", number];
  const q = useQuery({ queryKey: key, refetchInterval: 15_000, queryFn: async () => unwrap(await api.GET("/api/admin/orders/{number}", { params: { path: { number } } })) });

  const done = (o?: unknown) => { void qc.invalidateQueries({ queryKey: key }); void qc.invalidateQueries({ queryKey: ["orders"] }); void qc.invalidateQueries({ queryKey: ["todo"] }); void o; };
  const [feeText, setFeeText] = useState("");
  const [tracking, setTracking] = useState("");
  const [rejectReason, setRejectReason] = useState("");
  const [confirmCancel, setConfirmCancel] = useState(false);
  const branches = useQuery({ queryKey: ["branches"], enabled: can("inventory.view"), queryFn: async () => unwrap(await api.GET("/api/admin/inventory/branches")) });
  const moveBranch = useMutation({
    mutationFn: async (branch: string) => unwrap(await api.POST("/api/admin/orders/{number}/branch", { params: { path: { number } }, body: { branch } })),
    onSuccess: (o) => { qc.setQueryData(key, o); done(); },
  });

  const fee = useMutation({
    mutationFn: async (satang: number) => unwrap(await api.POST("/api/admin/orders/{number}/fee", { params: { path: { number } }, body: { fee_satang: satang } })),
    onSuccess: (o) => { setFeeText(""); qc.setQueryData(key, o); done(); },
  });
  const status = useMutation({
    mutationFn: async (v: { to: string; tracking?: string }) => unwrap(await api.POST("/api/admin/orders/{number}/status", { params: { path: { number } }, body: { status: v.to, tracking_ref: v.tracking ?? "" } })),
    onSuccess: (o) => { setConfirmCancel(false); qc.setQueryData(key, o); done(); },
  });
  const confirmPay = useMutation({
    mutationFn: async (id: number) => unwrap(await api.POST("/api/admin/payments/{payment_id}/confirm", { params: { path: { payment_id: id } } })),
    onSuccess: () => done(),
  });
  const rejectPay = useMutation({
    mutationFn: async (id: number) => unwrap(await api.POST("/api/admin/payments/{payment_id}/reject", { params: { path: { payment_id: id } }, body: { reason: rejectReason.trim() } })),
    onSuccess: () => { setRejectReason(""); done(); },
  });

  if (q.isLoading) return <p className="ink-muted">กำลังโหลด…</p>;
  if (q.error || !q.data) return <><Link to="/orders">← กลับ</Link><ErrorNotice error={q.error ?? new Error("ไม่พบคำสั่งซื้อ")} /></>;
  const o: Order = q.data;
  const p = o.payment;
  const quoteOpen = can("orders.quote") && (o.status === "pending_quote" || o.status === "waiting_payment");
  const mayCancel = CAN_CANCEL.has(o.status) && can(o.status === "paid" || o.status === "packing" ? "orders.cancel_paid" : "orders.cancel");
  const feeSatang = bahtToSatang(feeText);
  const mutationError = fee.error ?? status.error ?? confirmPay.error ?? rejectPay.error ?? moveBranch.error;
  const canMoveBranch = can("orders.fulfil") && can("inventory.view") && !["pickup"].includes(o.shipping_method.kind) && ["pending_quote", "waiting_payment", "paid", "packing"].includes(o.status);

  return (
    <>
      <div className="topbar">
        <Link className="icon-btn" to="/orders" aria-label="กลับไปรายการคำสั่งซื้อ"><svg className="ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M15 5l-7 7 7 7" /></svg></Link>
        <h1 style={{ marginRight: 0 }}><span className="mh-code" style={{ fontSize: 22 }}>{o.number}</span></h1>
        <span style={{ marginRight: "auto" }}><StatusPill status={PILL[o.status]} /></span>
        <span className="sm ink-muted">{o.status_label}</span>
      </div>
      <ErrorNotice error={mutationError} />

      <div className="cols cols--2-1">
        <div style={{ display: "flex", flexDirection: "column", gap: 16, minWidth: 0 }}>
          <section className="apanel">
            <h2>รายการสินค้า</h2>
            <div className="mh-tablewrap" style={{ border: 0 }}>
              <table className="mh-table">
                <thead><tr><th>สินค้า</th><th className="r">ราคา</th><th className="r">จำนวน</th><th className="r">รวม</th></tr></thead>
                <tbody>{o.items.map((i) => <tr key={i.sku}><td>{i.product_name} ({i.variant_label}){i.promotion_name && <><br /><span className="xs" style={{ color: "var(--band-red)" }}>{i.promotion_name}</span></>}</td><td className="r">{formatTHB(i.unit_price_satang)}{i.list_price_satang && i.list_price_satang > i.unit_price_satang ? <><br /><s className="xs ink-muted">{formatTHB(i.list_price_satang)}</s></> : null}</td><td className="r">{i.quantity}</td><td className="r">{formatTHB(i.line_total_satang)}</td></tr>)}</tbody>
              </table>
            </div>
            <hr className="hr" />
            <div className="rowline"><span className="ink-muted">ยอดสินค้า</span><span className="num">{formatTHB(o.subtotal_satang)}</span></div>
            {o.coupon_discount_satang > 0 && <div className="rowline"><span className="ink-muted">โค้ด <span className="mh-code">{o.coupon_code}</span></span><span className="num">−{formatTHB(o.coupon_discount_satang)}</span></div>}
            {o.discount_satang > 0 && <div className="rowline"><span className="ink-muted">ส่วนลดโปรโมชัน (รวมในยอดแล้ว)</span><span className="num">−{formatTHB(o.discount_satang)}</span></div>}
            <div className="rowline"><span className="ink-muted">ค่าจัดส่ง</span><span className="num">{o.shipping_waived ? "ส่งฟรี" : o.shipping_fee_satang === null ? "ยังไม่แจ้ง" : formatTHB(o.shipping_fee_satang)}</span></div>
            {o.vat_satang > 0 && <div className="rowline"><span className="ink-muted">ภาษีมูลค่าเพิ่มรวมในยอด</span><span className="num">{formatTHB(o.vat_satang)}</span></div>}
            <div className="rowline"><span className="bold">รวมทั้งสิ้น</span><span className="mh-price num">{o.total_satang === null ? "—" : formatTHB(o.total_satang)}</span></div>
          </section>

          {quoteOpen && (
            <section className="apanel">
              <h2>ค่าจัดส่ง</h2>
              {o.status === "waiting_payment" && o.shipping_fee_satang !== null && <div className="notice notice--ok"><p>แจ้งค่าจัดส่งแล้ว ลูกค้าเห็น QR ชำระเงินในหน้าคำสั่งซื้อ แก้ได้จนกว่าลูกค้าจะแนบสลิป แก้แล้ว QR เดิมจะใช้ไม่ได้</p></div>}
              <form className="form-grid" onSubmit={(e) => { e.preventDefault(); if (feeSatang !== null) fee.mutate(feeSatang); }}>
                <div className="mh-field"><label className="mh-label" htmlFor="fee">ค่าจัดส่ง (บาท)</label>
                  <input className="mh-input num" id="fee" inputMode="decimal" value={feeText} onChange={(e) => setFeeText(e.target.value)} placeholder={o.shipping_fee_satang === null ? "เช่น 120" : String(o.shipping_fee_satang / 100)} aria-invalid={feeText !== "" && feeSatang === null} />
                  <span className="mh-help">{feeText !== "" && feeSatang === null ? "กรอกเป็นตัวเลข ทศนิยมไม่เกิน 2 ตำแหน่ง" : `ขนส่ง: ${o.shipping_method.name}`}</span></div>
                <div style={{ alignSelf: "end" }}><button className="mh-btn mh-btn--primary" type="submit" disabled={feeSatang === null || fee.isPending}>{fee.isPending ? "กำลังบันทึก…" : "บันทึกค่าจัดส่ง"}</button></div>
              </form>
            </section>
          )}

          <section className="apanel">
            <h2>ประวัติ</h2>
            <ol className="tl">
              {o.events.map((e, i) => (
                <li key={i} className={i === o.events.length - 1 ? "now" : "done"}>
                  <span className="pt">{i === o.events.length - 1 ? "" : "✓"}</span>
                  <div><h3>{e.kind === "created" ? "ลูกค้าสั่งซื้อ" : e.kind === "slip_submitted" ? `ลูกค้าแนบสลิป ${e.detail}` : e.detail || e.kind}</h3><p className="xs ink-muted">{new Date(e.created_at).toLocaleString("th-TH", { dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Bangkok" })}</p></div>
                </li>
              ))}
            </ol>
          </section>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 16, minWidth: 0 }}>
          <section className="apanel">
            <h2>การชำระเงิน</h2>
            {!p && <p className="ink-muted">ยังไม่มีการชำระเงิน</p>}
            {p && !can("payments.review") && <p className="xs ink-muted">ตำแหน่งของคุณไม่เห็นสลิปและไม่ยืนยันการชำระเงิน</p>}
            {p && (
              <>
                <div className="rowline"><span className="ink-muted">ยอด</span><span className="num bold">{formatTHB(p.amount_satang)}</span></div>
                <div className="rowline"><span className="ink-muted">สถานะ</span><span className="bold">{{ pending: "รอชำระ", slip_submitted: "รอตรวจสลิป", confirmed: "ยืนยันแล้ว", rejected: "ไม่ผ่าน", expired: "QR หมดอายุ" }[p.status] ?? p.status}</span></div>
                {p.slip_url && <a href={p.slip_url} target="_blank" rel="noreferrer"><img src={p.slip_url} alt="สลิปการโอน" style={{ width: "100%", maxHeight: 360, objectFit: "contain", borderRadius: 12, background: "var(--surface-300)" }} /></a>}
                {p.reject_reason && <p className="sm ink-muted">เหตุผลที่ไม่ผ่าน: {p.reject_reason}</p>}
                {can("payments.review") && (p.status === "slip_submitted" || p.status === "pending") && o.status === "waiting_payment" && (
                  <>
                    <p className="xs ink-muted">เทียบยอดและบัญชีผู้รับในสลิป กับ {formatTHB(p.amount_satang)} ก่อนกดยืนยัน</p>
                    <button className="mh-btn mh-btn--primary" disabled={confirmPay.isPending} onClick={() => confirmPay.mutate(p.id)}>{confirmPay.isPending ? "กำลังยืนยัน…" : "ยืนยันการชำระเงิน"}</button>
                    {p.status === "slip_submitted" && (
                      <div className="mh-field">
                        <label className="mh-label" htmlFor="rr">ไม่ผ่าน เพราะ</label>
                        <input className="mh-input" id="rr" value={rejectReason} onChange={(e) => setRejectReason(e.target.value)} placeholder="เช่น ยอดไม่ตรง" maxLength={200} />
                        <button className="mh-btn mh-btn--secondary mh-btn--sm" disabled={!rejectReason.trim() || rejectPay.isPending} onClick={() => rejectPay.mutate(p.id)}>ส่งกลับให้ลูกค้าแก้</button>
                      </div>
                    )}
                  </>
                )}
              </>
            )}
          </section>

          <section className="apanel">
            <h2>ดำเนินการ</h2>
            {(can("orders.fulfil") ? NEXT_STATUS[o.status] ?? [] : []).map((n) => (
              <div key={n.to} className="mh-field">
                {n.askTracking && (<><label className="mh-label" htmlFor="trk">เลขใบฝากส่ง / เลขพัสดุ (ถ้ามี)</label><input className="mh-input" id="trk" value={tracking} onChange={(e) => setTracking(e.target.value)} maxLength={60} /></>)}
                <button className="mh-btn mh-btn--primary" disabled={status.isPending} onClick={() => status.mutate({ to: n.to, tracking: n.askTracking ? tracking : undefined })}>{n.label}</button>
              </div>
            ))}
            {!(can("orders.fulfil") && NEXT_STATUS[o.status]?.length) && !mayCancel && <p className="ink-muted">{CAN_CANCEL.has(o.status) || NEXT_STATUS[o.status]?.length ? "ไม่มีการดำเนินการที่ตำแหน่งของคุณทำได้ในขั้นตอนนี้" : "คำสั่งซื้อนี้ปิดแล้ว"}</p>}
            {o.tracking_ref && <p className="sm">เลขพัสดุ: <span className="mh-code">{o.tracking_ref}</span></p>}
            {mayCancel && (confirmCancel ? (
              <div className="notice notice--warn" role="alert" style={{ flexDirection: "column" }}>
                <p>{o.status === "paid" || o.status === "packing" ? "ลูกค้าชำระเงินแล้ว ระบบไม่คืนเงินให้ ต้องโอนคืนเองนอกระบบ " : ""}ยืนยันยกเลิก {o.number}? ย้อนกลับไม่ได้</p>
                <div className="mh-row"><button className="mh-btn mh-btn--danger mh-btn--sm" disabled={status.isPending} onClick={() => status.mutate({ to: "cancelled" })}>ยืนยันยกเลิก</button><button className="mh-btn mh-btn--secondary mh-btn--sm" onClick={() => setConfirmCancel(false)}>ไม่ยกเลิก</button></div>
              </div>
            ) : <button className="mh-btn mh-btn--secondary mh-btn--sm" onClick={() => setConfirmCancel(true)}>ยกเลิกคำสั่งซื้อ</button>)}
          </section>

          <section className="apanel">
            <h2>ลูกค้าและการจัดส่ง</h2>
            <dl className="kv">
              <dt>ชื่อ</dt><dd>{o.customer_name}</dd>
              <dt>โทร</dt><dd className="num">{o.phone}</dd>
              <dt>LINE</dt><dd>{o.line_linked ? "เชื่อมต่อแล้ว ได้รับแจ้งเตือนอัตโนมัติ" : "ยังไม่เชื่อมต่อ ต้องแจ้งทางโทรศัพท์"}</dd>
              <dt>วิธีรับ</dt><dd>{o.shipping_method.name}</dd>
              <dt>จัดจากสาขา</dt><dd>{canMoveBranch ? (
                <select className="mh-select" style={{ minHeight: 36 }} aria-label="สาขาที่จัดสินค้า" value={o.fulfillment_branch?.code ?? ""} disabled={moveBranch.isPending} onChange={(e) => moveBranch.mutate(e.target.value)}>
                  {!o.fulfillment_branch && <option value="">—</option>}
                  {branches.data?.map((b) => <option key={b.code} value={b.code}>{b.name}</option>)}
                </select>) : (o.fulfillment_branch?.name ?? "—")}</dd>
              <dt>นัดรับ</dt><dd>{formatThaiDate(o.requested_date)}</dd>
              {o.address_line && <><dt>ที่อยู่</dt><dd>{[o.address_line, o.subdistrict, o.district, o.province, o.postal_code].filter(Boolean).join(" ")}</dd></>}
              {o.note && <><dt>หมายเหตุ</dt><dd>{o.note}</dd></>}
            </dl>
          </section>
        </div>
      </div>
    </>
  );
}
