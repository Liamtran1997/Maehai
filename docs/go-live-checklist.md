# Checklist trước khi đưa lên thật

Cập nhật: 12/10/2026. Phần kỹ thuật đã làm xong trên máy phát triển; các mục dưới đây cần tiệm hoặc máy chủ.

## Đã làm (trên máy phát triển)

- [x] Dữ liệu sản phẩm từ maehai.com: 28 sản phẩm, 33 ảnh gốc, đúng tên và màu dây thun. Món mới để **ẩn** với giá tạm.
- [x] Trang chính sách bảo mật và điều khoản (bản nháp, có ô [ระบุ]).
- [x] Khách phải đồng ý điều khoản trước khi đặt hàng; sự đồng ý được ghi lại trên đơn.
- [x] Phân quyền nhân viên, nhật ký hoạt động, đổi mật khẩu tạm bắt buộc.
- [x] Thư viện ảnh nhiều tấm, lưu local hoặc S3 theo cấu hình.
- [x] Kiểm thử trên trình duyệt: 20 test (shop, luồng đặt hàng đầy đủ, quyền nhân viên), chạy trên cả điện thoại và máy tính.
- [x] Backend: 275 test trên SQLite, 276 trên Postgres.

## Tiệm cần cung cấp

- [ ] **Giá thật** cho từng cỡ của 28 sản phẩm (hiện là giá tạm ฿100 cho món mới và giá mẫu cho 22 món cũ). Sau đó bật hiển thị từng món.
- [ ] **Mô tả, số อย., cách bảo quản, trọng lượng** cho từng sản phẩm.
- [ ] **Đếm kho thực tế** rồi bật theo dõi tồn kho cho các món cần theo dõi.
- [ ] **Số PromptPay** nhận tiền và có đăng ký VAT hay không.
- [ ] **Ngày nghỉ** không giao hàng (biến `NON_WORKING_DATES`).
- [ ] **Điền các chỗ [ระบุ]** trong trang chính sách, rồi nhờ tư vấn pháp lý kiểm tra (PDPA, thời hạn lưu dữ liệu, hoàn tiền, điều khoản vận chuyển).
- [ ] Ảnh sản phẩm mới chụp nếu ảnh trên site cũ không đủ đẹp.

## Cần máy chủ thật

- [ ] Tên miền, HTTPS, bản ghi DNS.
- [ ] Bộ khóa riêng cho máy chủ (`deploy/.env`), không dùng khóa của máy phát triển.
- [ ] Migration trên Postgres của máy chủ, sao lưu trước.
- [ ] Lịch sao lưu hằng ngày và thử khôi phục.
- [ ] Tiến trình gửi LINE (`worker`) và hủy đơn quá hạn (`scheduler`) đang chạy.

## Cần LINE và lưu trữ

- [ ] LINE Official Account `@maehai`: token, secret, webhook, ID nhóm nhân viên.
- [ ] Nếu dùng S3: bucket, quyền IAM, và thử upload ảnh thật (chưa kiểm chứng).

## Trước khi mở cho khách

- [ ] Đổi mật khẩu Postgres dùng khi phát triển (đã dùng trong chat) và xóa mọi tài khoản thử.
- [ ] Tạo chủ tiệm thật bằng `createsuperuser`, tạo nhân viên qua trang "พนักงานและสิทธิ์".
- [ ] Kiểm tra trên điện thoại thật ít nhất một lần.
- [ ] Chạy một đơn thật từ đầu đến cuối với số tiền nhỏ.
