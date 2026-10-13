"use client";

export default function Error({ reset }: { error: Error; reset: () => void }) {
  return (
    <section className="sec sec--narrow" style={{ textAlign: "center", paddingBlock: 72 }}>
      <h1 style={{ font: "500 28px/1.4 var(--font-display)" }}>โหลดข้อมูลไม่สำเร็จ</h1>
      <p className="ink-muted">ระบบเชื่อมต่อร้านไม่ได้ในขณะนี้ ลองใหม่อีกครั้ง หรือสั่งทาง LINE @maehai</p>
      <div><button className="mh-btn mh-btn--primary" onClick={reset}>ลองใหม่</button></div>
    </section>
  );
}
