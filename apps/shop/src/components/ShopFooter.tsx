export function ShopFooter() {
  return (
    <footer className="footer">
      <p className="bold">ร้านหมูยอแม่ฮาย</p>
      <p className="sm">สั่งออนไลน์ทาง LINE @maehai</p>
      <p className="sm">โทร 081-878-5474 · 045-254-763</p>
      <nav aria-label="นโยบายและเงื่อนไข" className="sm" style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
        <a href="/privacy">นโยบายความเป็นส่วนตัว</a>
        <a href="/terms">เงื่อนไขการสั่งซื้อ</a>
      </nav>
    </footer>
  );
}
