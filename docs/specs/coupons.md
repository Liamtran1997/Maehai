# Spec: Mã giảm giá (coupon) cho cả đơn

Trạng thái: đã triển khai. Cập nhật: 12/10/2026.
Khác với **khuyến mãi** (giảm giá từng sản phẩm, tự áp dụng, xem `product-management.md`): mã giảm giá là **khách tự nhập** ở trang thanh toán và giảm trên **cả đơn**.

## 1. Cấu hình (nhân viên, trang "โค้ดส่วนลด")

| Trường | Bắt buộc | Quy tắc |
|---|---|---|
| Mã | Có | A-Z, 0-9, dấu `-`, 2 đến 24 ký tự, duy nhất. Lưu chữ hoa; khách gõ hoa thường đều được. Có nút "สุ่มใหม่" (không dùng ký tự dễ nhầm như 0/O, 1/I) |
| Tên | Có | Để nhân viên nhớ (ví dụ "แจกลูกค้าเก่า ต.ค."). Khách không thấy |
| Kiểu giảm | Có | **Phần trăm** (1 đến 90) hoặc **số tiền** cố định trên cả đơn |
| Trần giảm | Không | Chỉ cho kiểu phần trăm. Ví dụ "10% tối đa ฿100" |
| Đơn tối thiểu | Không | Tính trên tiền hàng sau khuyến mãi, không tính phí ship |
| Không dùng cho hàng đang giảm giá | Không | Bật thì hàng đã giảm bởi khuyến mãi không được tính vào đơn tối thiểu và không được giảm thêm |
| Số lần dùng tổng | Không | Để trống = không giới hạn |
| Số lần dùng mỗi số điện thoại | Không | Mặc định **1**. Để trống = không giới hạn |
| Thời gian | Bắt đầu: có. Kết thúc: không | Đặt trước được |
| Bật/tắt | | |

## 2. Quy tắc tính

1. Mã giảm trên **tiền hàng sau khi đã trừ khuyến mãi từng món**. **Không giảm phí ship.** Dùng được cùng khuyến mãi từng món.
2. Giảm % làm tròn nửa lên tới satang. Có trần thì không vượt trần.
3. Giảm theo số tiền không vượt quá phần tiền hàng được phép giảm.
4. **Tiền hàng sau giảm luôn còn ít nhất ฿1** (PromptPay không thu được 0 đồng). Nếu một mã sẽ làm hàng thành miễn phí, mức giảm bị cắt cho vừa.
5. Mỗi đơn dùng **một** mã.
6. VAT (nếu tiệm đăng ký) tính trên số tiền khách trả sau khi trừ mã.
7. Số tiền ở mã QR PromptPay là số sau khi trừ mã.
8. Đơn hàng lưu mã và số tiền đã giảm; sửa hay tắt mã về sau không đổi đơn cũ.

## 3. Điều kiện sử dụng (kiểm tra theo thứ tự)

| # | Kiểm tra | Thông báo cho khách |
|---|---|---|
| 1 | Mã tồn tại, đang bật, đã tới giờ bắt đầu, chưa hết hạn | "ไม่พบโค้ดนี้หรือหมดอายุแล้ว" |
| 2 | Chưa dùng hết số lần tổng | "โค้ดนี้ถูกใช้ครบจำนวนแล้ว" |
| 3 | Số điện thoại chưa dùng hết số lần của mình | "เบอร์โทรนี้ใช้โค้ดนี้ครบสิทธิ์แล้ว" |
| 4 | Có hàng đủ điều kiện (khi bật "ไม่ใช้กับสินค้าที่ลดราคาอยู่แล้ว") | "โค้ดนี้ใช้กับสินค้าที่ลดราคาอยู่แล้วไม่ได้" |
| 5 | Đạt đơn tối thiểu | "ซื้อครบ ฿500.00 เพื่อใช้โค้ดนี้ (ขาดอีก ฿270.00)" |
| 6 | Mức giảm lớn hơn 0 | "โค้ดนี้ใช้กับยอดนี้ไม่ได้" |

Mã không tồn tại, bị tắt, chưa bắt đầu và đã hết hạn đều trả **cùng một câu**, để người đoán mã không biết mã nào có thật.

## 4. Lượt dùng

- Một lượt được tính khi **đặt đơn thành công**, không phải khi khách bấm "ใช้โค้ด".
- **Hủy đơn trả lại lượt** (kể cả đơn bị hủy tự động vì quá hạn thanh toán). Đơn đã gửi hoặc hoàn tất thì giữ lượt.
- Số điện thoại được chuẩn hóa trước khi đếm, nên `081-234-5678`, `0812345678`, `+66 81 234 5678` là cùng một người.
- Khi nhiều khách đặt cùng lúc tranh lượt cuối, chỉ một đơn thành công. Hệ thống khóa dòng của mã trong lúc tạo đơn; có test đa luồng xác nhận trên Postgres (8 đơn cùng lúc, đúng 1 thành công; bỏ khóa thì test fail).
- Số điện thoại **không phải bằng chứng danh tính**: một người có nhiều SIM vẫn dùng lại được. Muốn chặt hơn cần đăng nhập tài khoản khách (chưa có).

## 5. Với khách (trang thanh toán)

- Ô "มีโค้ดส่วนลดไหม" và nút "ใช้โค้ด". Bấm Enter cũng được.
- Mã hợp lệ: hiện tên mã, số tiền giảm, và tổng tiền hàng mới. Có nút "เอาออก".
- Đổi giỏ hàng thì mã tự bị bỏ và khách phải áp lại, để số tiền luôn khớp.
- Khi đặt đơn, server **tính lại từ đầu** và quyết định cuối cùng; số hiển thị chỉ là xem trước. Nếu mã không còn hợp lệ (hết lượt trong lúc khách điền form), đơn bị từ chối kèm lý do và **không** tạo đơn, không giữ hàng.
- Trang đơn hàng hiện dòng "โค้ด XXXX −฿..".

## 6. Với nhân viên

- Bảng: mã, mức giảm, đã dùng / giới hạn, tổng tiền đã giảm, thời gian, trạng thái (ใช้ได้, ตั้งเวลาไว้, หมดเวลาแล้ว, ใช้ครบแล้ว, ปิดอยู่).
- "ประวัติ": danh sách đơn đã dùng mã (số đơn, số điện thoại, tiền giảm, đã hủy và trả lượt chưa).
- Mã đã được dùng: **không xóa** (giữ lịch sử), **không đổi chữ của mã**. Dùng "ปิดโค้ดตอนนี้". Mã chưa ai dùng thì xóa được.
- Trang chi tiết đơn có dòng "โค้ด ... −฿...".

## 7. Chống lạm dụng

- Dò mã: sai quá **10 lần / 15 phút** từ một địa chỉ IP thì bị chặn (429), kể cả khi thử qua trang xem trước hay qua nút đặt đơn. Xem trước tối đa 30 lần / 10 phút mỗi IP.
- Một IP bị chặn không ảnh hưởng khách khác.

## 8. Chưa làm (đề xuất)

1. **Miễn phí ship** làm loại mã riêng (hiện mã chỉ giảm tiền hàng, và phí ship do tiệm báo sau đặt đơn).
2. **Mã dành cho một khách** (gắn với số điện thoại hoặc tài khoản) và **đơn đầu tiên**.
3. **Mã chỉ cho một số sản phẩm hoặc danh mục.**
4. **Báo cáo hiệu quả mã**: doanh thu, số đơn, tỷ lệ chuyển đổi, chi phí giảm giá theo mã (hiện chỉ có tổng đã giảm và số lần dùng).
5. **Tạo hàng loạt** mã dùng một lần để gửi riêng từng khách.
6. **Chặn nhờ tài khoản**: yêu cầu đăng nhập LINE để mã dùng một lần thật sự một người.
