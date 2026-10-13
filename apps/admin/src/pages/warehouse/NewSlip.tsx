import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, Navigate, useParams } from "react-router-dom";
import { ErrorNotice } from "../../components/Notice";
import { api, unwrap } from "../../lib/api";
import { Created, LineBuilder, itemOptions, toApiLines, useBranches, useMaterials, useSources, useStockItems, type Line } from "./shared";

const KINDS: Record<string, { title: string; back: string }> = {
  receipt: { title: "รับของเข้าคลังกลาง", back: "ใบรับสินค้า" },
  transfer: { title: "ส่งของไปสาขา", back: "ใบส่งสินค้า" },
  return: { title: "สาขาส่งคืนคลัง", back: "ใบคืนสินค้า" },
};

/** Creating a slip is its own page: /warehouse/new/receipt, /new/transfer or /new/return. */
export function NewSlipPage() {
  const { kind = "" } = useParams();
  const info = KINDS[kind];
  if (!info) return <Navigate to="/warehouse?tab=docs" replace />;
  return (
    <>
      <nav className="crumbs" aria-label="ตำแหน่ง"><Link to="/warehouse?tab=docs">คลังสินค้า</Link><span aria-hidden="true">›</span><span>{info.title}</span></nav>
      <div className="page-head">
        <div><h1>{info.title}</h1></div>
      </div>
      {kind === "receipt" && <ReceiptTab />}
      {kind === "transfer" && <TransferTab />}
      {kind === "return" && <StoreReturnTab />}
    </>
  );
}

export function ReceiptTab() {
  const qc = useQueryClient();
  const sources = useSources();
  const stock = useStockItems();
  const mats = useMaterials();
  const [sourceId, setSourceId] = useState("");
  const [supplierRef, setSupplierRef] = useState("");
  const [note, setNote] = useState("");
  const [lines, setLines] = useState<Line[]>([{ item: "", quantity: "", cost: "" }]);
  const [created, setCreated] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: async () => unwrap(await api.POST("/api/admin/inventory/documents/receipts", {
      body: { source_id: Number(sourceId), supplier_ref: supplierRef, note, lines: toApiLines(lines, true) },
    })),
    onSuccess: (d) => {
      setCreated(d.number); setLines([{ item: "", quantity: "", cost: "" }]); setSupplierRef(""); setNote("");
      for (const k of ["documents", "stock", "materials", "report"]) void qc.invalidateQueries({ queryKey: [k] });
    },
  });
  const onSubmit = (e: FormEvent) => { e.preventDefault(); setCreated(null); save.mutate(); };
  return (
    <form className="apanel" style={{ maxWidth: 820 }} onSubmit={onSubmit}>
      <h2>รับของจากแหล่งสินค้าเข้าคลังกลาง</h2>
      <p className="sm ink-muted">ของเข้าคลังกลางทันที ไม่ต้องรอสาขายืนยัน ระบุแหล่งที่มาและเลขใบส่งของ (ถ้ามี)</p>
      <div className="form-grid">
        <div className="mh-field"><label className="mh-label" htmlFor="rs">แหล่งสินค้า</label>
          <select className="mh-select" id="rs" value={sourceId} onChange={(e) => setSourceId(e.target.value)} required>
            <option value="">— เลือกแหล่ง —</option>
            {sources.data?.filter((s) => s.is_active).map((s) => <option key={s.id} value={s.id}>{s.name} ({s.kind_label})</option>)}
          </select></div>
        <div className="mh-field"><label className="mh-label" htmlFor="rref">เลขใบส่งของ/บิลของแหล่ง</label><input className="mh-input" id="rref" value={supplierRef} onChange={(e) => setSupplierRef(e.target.value)} maxLength={60} /></div>
      </div>
      <div className="mh-field"><span className="mh-label">รายการ</span>
        <LineBuilder lines={lines} onChange={setLines} items={itemOptions(stock.data, mats.data)} withCost />
        <span className="mh-help">ราคาต่อหน่วยเป็นสตางค์ (เว้นว่างได้) ใช้เก็บไว้สำหรับรายงานต้นทุนภายหลัง</span>
      </div>
      <div className="mh-field"><label className="mh-label" htmlFor="rnote">หมายเหตุ</label><input className="mh-input" id="rnote" value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} /></div>
      <Created number={created} />
      <ErrorNotice error={save.error} />
      <button className="mh-btn mh-btn--primary" type="submit" disabled={save.isPending || !sourceId || !lines.some((l) => l.item)}>{save.isPending ? "กำลังบันทึก…" : "บันทึกใบรับสินค้า"}</button>
      <p className="xs ink-muted">ยังไม่มีรายการ? สร้างแหล่งสินค้า วัตถุดิบ หรือวัสดุก่อนในแท็บที่เกี่ยวข้อง</p>
      <p className="xs"><Link to="/warehouse?tab=stock">กลับไปหน้าสต็อก</Link></p>
    </form>
  );
}

export function TransferTab() {
  const qc = useQueryClient();
  const branches = useBranches();
  const stock = useStockItems();
  const mats = useMaterials();
  const stores = branches.data?.filter((b) => b.kind === "store") ?? [];
  const [to, setTo] = useState("");
  const [vehicle, setVehicle] = useState("");
  const [carrier, setCarrier] = useState("");
  const [note, setNote] = useState("");
  const [lines, setLines] = useState<Line[]>([{ item: "", quantity: "", cost: "" }]);
  const [created, setCreated] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: async () => unwrap(await api.POST("/api/admin/inventory/documents/transfers", {
      body: { to_branch: to || stores[0]?.code || "", vehicle, carrier, note, lines: toApiLines(lines, false) },
    })),
    onSuccess: (d) => {
      setCreated(d.number); setLines([{ item: "", quantity: "", cost: "" }]); setVehicle(""); setCarrier(""); setNote("");
      for (const k of ["documents", "stock", "materials", "report", "summary", "todo"]) void qc.invalidateQueries({ queryKey: [k] });
    },
  });
  const onSubmit = (e: FormEvent) => { e.preventDefault(); setCreated(null); save.mutate(); };
  return (
    <form className="apanel" style={{ maxWidth: 820 }} onSubmit={onSubmit}>
      <h2>ส่งของจากคลังกลางไปสาขา</h2>
      <p className="sm ink-muted">ของจะออกจากคลังกลางทันที และจะเข้าสาขาเมื่อผู้จัดการสาขาตรวจรับแล้วเท่านั้น</p>
      <div className="form-grid">
        <div className="mh-field"><label className="mh-label" htmlFor="tto">ไปสาขา</label>
          <select className="mh-select" id="tto" value={to || stores[0]?.code || ""} onChange={(e) => setTo(e.target.value)}>
            {stores.map((b) => <option key={b.code} value={b.code}>{b.name}</option>)}
          </select></div>
        <div className="mh-field"><label className="mh-label" htmlFor="tveh">รถที่ใช้ส่ง</label><input className="mh-input" id="tveh" value={vehicle} onChange={(e) => setVehicle(e.target.value)} maxLength={100} placeholder="เช่น กระบะขาว กข-1234" required /></div>
        <div className="mh-field"><label className="mh-label" htmlFor="tcar">ผู้นำส่ง (ถ้ามี)</label><input className="mh-input" id="tcar" value={carrier} onChange={(e) => setCarrier(e.target.value)} maxLength={100} /></div>
      </div>
      <div className="mh-field"><span className="mh-label">รายการ</span>
        <LineBuilder lines={lines} onChange={setLines} items={itemOptions(stock.data, mats.data)} />
      </div>
      <div className="mh-field"><label className="mh-label" htmlFor="tnote">หมายเหตุ</label><input className="mh-input" id="tnote" value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} /></div>
      <Created number={created} />
      <ErrorNotice error={save.error} />
      <button className="mh-btn mh-btn--primary" type="submit" disabled={save.isPending || !vehicle.trim() || !lines.some((l) => l.item)}>{save.isPending ? "กำลังบันทึก…" : "บันทึกใบส่งสินค้า"}</button>
    </form>
  );
}

export function StoreReturnTab() {
  const qc = useQueryClient();
  const branches = useBranches();
  const stock = useStockItems();
  const mats = useMaterials();
  const stores = branches.data?.filter((b) => b.kind === "store") ?? [];
  const [branch, setBranch] = useState("");
  const [note, setNote] = useState("");
  const [lines, setLines] = useState<Line[]>([{ item: "", quantity: "", cost: "" }]);
  const [created, setCreated] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: async () => unwrap(await api.POST("/api/admin/inventory/documents/returns", {
      body: { branch: branch || stores[0]?.code || "", note, lines: toApiLines(lines, false) },
    })),
    onSuccess: (d) => {
      setCreated(d.number); setLines([{ item: "", quantity: "", cost: "" }]); setNote("");
      for (const k of ["documents", "stock", "materials", "report", "summary", "todo"]) void qc.invalidateQueries({ queryKey: [k] });
    },
  });
  const onSubmit = (e: FormEvent) => { e.preventDefault(); setCreated(null); save.mutate(); };
  return (
    <form className="apanel" style={{ maxWidth: 820 }} onSubmit={onSubmit}>
      <h2>สาขาส่งของคืนคลังกลาง</h2>
      <p className="sm ink-muted">ใช้เมื่อสาขามีของเกินหรือใกล้หมดอายุ ของจะออกจากสาขาทันทีและกลับเข้าคลังกลางเมื่อคลังกลางรับแล้ว</p>
      <div className="mh-field"><label className="mh-label" htmlFor="rbr">สาขา</label>
        <select className="mh-select" id="rbr" value={branch || stores[0]?.code || ""} onChange={(e) => setBranch(e.target.value)}>
          {stores.map((b) => <option key={b.code} value={b.code}>{b.name}</option>)}
        </select></div>
      <div className="mh-field"><span className="mh-label">รายการ</span>
        <LineBuilder lines={lines} onChange={setLines} items={itemOptions(stock.data, mats.data)} />
      </div>
      <div className="mh-field"><label className="mh-label" htmlFor="rnote2">เหตุผล</label><input className="mh-input" id="rnote2" value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} /></div>
      <Created number={created} />
      <ErrorNotice error={save.error} />
      <button className="mh-btn mh-btn--primary" type="submit" disabled={save.isPending || !lines.some((l) => l.item)}>{save.isPending ? "กำลังบันทึก…" : "บันทึกใบคืนสินค้า"}</button>
    </form>
  );
}
