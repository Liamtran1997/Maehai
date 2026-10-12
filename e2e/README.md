# Kiểm thử trên trình duyệt (end-to-end)

Chạy cả API, shop và admin trên một database SQLite riêng (`e2e/e2e.sqlite3`, không đụng dữ liệu dev), rồi mở trình duyệt thật để đi qua các luồng chính.

Lần đầu:

```bash
pnpm install
pnpm --filter @maehai/e2e exec playwright install chromium
```

Chạy:

```bash
pnpm --filter @maehai/e2e test
```

Test gồm:
- **shop.spec.ts**: trang chủ, danh mục, chi tiết sản phẩm, trang chính sách, không tràn ngang trên điện thoại.
- **flow.spec.ts**: khách thêm vào giỏ, checkout (bắt buộc đồng ý điều khoản), nhận QR, tải slip; chủ tiệm đăng nhập và xác nhận thanh toán; khách thấy đã thanh toán.
- **staff.spec.ts**: quyền theo vị trí (chủ, kho), đổi mật khẩu tạm bắt buộc, báo lỗi đăng nhập bằng tiếng Thái.

Khi test lỗi, ảnh chụp và trace nằm trong `e2e/test-results/`.
