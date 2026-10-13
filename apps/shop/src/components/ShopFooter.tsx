export function ShopFooter() {
  return (
    <footer className="footer">
      <div className="footer-in">
        <div className="footer-col">
          <p className="footer-brand">ร้านหมูยอแม่ฮาย</p>
          <p className="sm muted">ต้นตำรับหมูยอเมืองอุบลฯ ห่อใบตอง ผลิตสดใหม่ทุกวัน</p>
        </div>
        <nav className="footer-col" aria-label="สินค้า">
          <h2>สินค้า</h2>
          <a href="/products?category=moo-yo">หมูยอ</a>
          <a href="/products?category=naem">แหนม</a>
          <a href="/products">สินค้าทั้งหมด</a>
        </nav>
        <nav className="footer-col" aria-label="ช่วยเหลือ">
          <h2>ช่วยเหลือ</h2>
          <a href="/track">ติดตามคำสั่งซื้อ</a>
          <a href="/terms">เงื่อนไขการสั่งซื้อ</a>
          <a href="/privacy">นโยบายความเป็นส่วนตัว</a>
        </nav>
        <div className="footer-col">
          <h2>ติดต่อเรา</h2>
          <p>LINE @maehai</p>
          <p className="num">081-878-5474 · 045-254-763</p>
          <a className="mh-btn line-btn btn-link" href="https://line.me/R/ti/p/@maehai" target="_blank" rel="noopener noreferrer">เพิ่มเพื่อนใน LINE</a>
        </div>
      </div>
      <p className="footer-legal">© ร้านหมูยอแม่ฮาย อุบลราชธานี</p>
    </footer>
  );
}
