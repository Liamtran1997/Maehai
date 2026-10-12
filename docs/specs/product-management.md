# Spec: Quản lý sản phẩm, danh mục, khuyến mãi, hết hàng

Trạng thái: đã triển khai. Cập nhật: 12/10/2026.
Phạm vi: trang quản trị (`/admin`) và cách thông tin hiện ra ở website bán hàng.

## 1. Sản phẩm

### 1.1 Thông tin nhân viên nhập

| Trường | Bắt buộc | Quy tắc | Hiện ở shop |
|---|---|---|---|
| Tên (tiếng Thái) | Có | ≤150 ký tự | Tên sản phẩm |
| Tên tiếng Anh | Không | ≤150 ký tự | Chưa dùng (dành cho bản tiếng Anh) |
| slug | Có | `a-z`, `0-9`, `-`; duy nhất | Đường dẫn `/products/<slug>`. Đổi slug làm link cũ hỏng |
| Danh mục | Có | Một danh mục | Bộ lọc và breadcrumb |
| Ảnh | Không | Tối đa 10 ảnh mỗi sản phẩm. JPG/PNG/WebP, ≤5 MB mỗi ảnh, kiểm tra đúng là ảnh thật. Thêm nhiều ảnh cùng lúc, đổi thứ tự bằng ‹ ›, xóa từng ảnh | Ảnh đầu tiên là ảnh chính (lưới sản phẩm). Trang chi tiết có thư viện ảnh với ảnh nhỏ bên dưới. Thiếu ảnh thì hiện hình cây หมูยอ vẽ sẵn |
| Mô tả ngắn, mô tả, số อย., cách bảo quản | Không | | Trang chi tiết |
| Màu dây thun | Không | vàng / đỏ / xanh | Hình minh họa khi chưa có ảnh |
| Nhãn | Không | ขายดี / ใหม่ | Góc thẻ sản phẩm |
| Thứ tự hiển thị | Có (mặc định 0) | Số nhỏ hiện trước | Thứ tự trong danh sách |
| Nổi bật trang chủ | Không | Bật/tắt | Hàng "รสยอดนิยม" trên trang chủ (4 món đầu). Không chọn món nào thì lấy 4 món đầu theo thứ tự |
| Hiển thị | Có | Bật/tắt | Tắt = ẩn khỏi shop, không ai đặt được |

### 1.2 Cỡ và giá

- Mỗi sản phẩm có ít nhất 1 cỡ. Mỗi cỡ có tên cỡ, SKU (duy nhất toàn hệ thống), **giá niêm yết** (> 0), cân nặng (tùy chọn).
- Nhân viên luôn nhập **giá niêm yết** (giá trước giảm). Giảm giá làm ở mục Khuyến mãi, không sửa giá niêm yết.
- SKU của cỡ đã tồn tại không sửa được (gắn với đơn hàng và tồn kho).
- Xóa một cỡ = ngừng bán cỡ đó; đơn cũ vẫn giữ nguyên.
- Giá lưu bằng satang (số nguyên). Không dùng số thập phân.

## 2. Danh mục

- Nhân viên tạo, sửa, đổi thứ tự, ẩn/hiện danh mục ở trang **หมวดหมู่**.
- **Ẩn danh mục** = ẩn luôn mọi sản phẩm trong đó khỏi shop, và khách **không đặt được** các sản phẩm đó (kể cả còn trong giỏ). Nhân viên vẫn thấy trong admin.
- **Xóa** chỉ được khi danh mục không còn sản phẩm. Muốn bỏ một danh mục đang có hàng: chuyển sản phẩm sang danh mục khác, hoặc ẩn đi.
- Danh mục không có sản phẩm đang bán thì không hiện trên shop (tránh bộ lọc trống).

## 3. Khuyến mãi

### 3.1 Cấu hình

| Trường | Quy tắc |
|---|---|
| Tên | Khách nhìn thấy, ví dụ "ลดรับสงกรานต์" |
| Kiểu | Giảm % (1 đến 90) hoặc giảm số tiền cố định mỗi đơn vị |
| Áp dụng cho | Sản phẩm chọn sẵn / cả danh mục / toàn shop |
| Bắt đầu | Bắt buộc. Có thể đặt trước (trạng thái "ตั้งเวลาไว้") |
| Kết thúc | Tùy chọn. Bỏ trống = chạy tới khi tắt |
| Bật/tắt | Tắt là dừng ngay |

### 3.2 Quy tắc tính giá

1. **Không cộng dồn.** Một cỡ nằm trong nhiều khuyến mãi cùng lúc thì khách nhận **một** mức giảm lớn nhất.
2. Giảm % làm tròn nửa lên tới satang.
3. Mức giảm làm giá về 0 hoặc âm thì **bỏ qua**, cỡ đó giữ giá niêm yết. Admin hiện cảnh báo những cỡ bị ảnh hưởng khi lưu.
4. Giá được tính **tại server, lúc đặt hàng**. Giá shop hiển thị và giá tính tiền dùng chung một hàm, và shop không cache dữ liệu giá.
5. Đơn hàng lưu lại giá niêm yết, giá bán và tên khuyến mãi của từng dòng. Sửa hoặc tắt khuyến mãi về sau **không** đổi đơn cũ.
6. Khuyến mãi áp dụng trên giá sản phẩm, **không** trên phí ship.

### 3.3 Vòng đời

| Trạng thái | Ý nghĩa | Thao tác |
|---|---|---|
| ตั้งเวลาไว้ | Chưa tới giờ bắt đầu | Sửa, tắt, xóa |
| กำลังใช้ | Đang chạy | Sửa, "ปิดตอนนี้" (đặt giờ kết thúc = bây giờ). **Không xóa** để giữ lịch sử |
| หมดเวลาแล้ว | Đã qua giờ kết thúc | Sửa (ví dụ gia hạn) |
| ปิดอยู่ | Đã tắt | Bật lại |

### 3.4 Hiển thị ở shop

- Thẻ sản phẩm: giá thấp nhất sau giảm (màu đỏ), giá gốc gạch ngang, nhãn "ลด 15%" (khi sản phẩm không có nhãn khác).
- Trang chi tiết: dải thông báo tên khuyến mãi và ngày kết thúc; giá từng cỡ đã trừ giảm.
- Trang đơn hàng (khách và admin): dòng "ส่วนลดโปรโมชัน"; admin thấy tên khuyến mãi theo từng dòng hàng.

## 4. Hết hàng

### 4.1 Với khách

- Chỉ áp dụng cho cỡ **có theo dõi tồn kho** (trang Tồn kho). Cỡ không theo dõi luôn coi là còn hàng.
- Cỡ hết hàng: chip ghi "หมด", không chọn được. Cả sản phẩm hết thì thẻ có nhãn "หมด" nhưng **vẫn hiện** (khách biết tiệm có bán, để quay lại).
- Còn ≤5: hiện "เหลือ N ชิ้น". Số lượng chọn không vượt quá số còn.
- **Báo khi có hàng lại (qua LINE).** Cỡ hết hàng có nút "ให้ร้านแจ้งทาง LINE เมื่อมีของ". Bấm vào mở LINE với tin soạn sẵn; khách gửi là đăng ký. Khi cỡ đó bán được trở lại (nhập hàng, kiểm kê tăng, hoặc một đơn bị hủy trả hàng về), mỗi khách đăng ký nhận **một** tin rồi đăng ký đóng lại.
  - Tin báo không giữ hàng cho khách ("จำนวนจำกัด ร้านไม่ได้กันของไว้ให้").
  - Đổi chi nhánh xuất hàng của một đơn **không** gửi tin (hàng chỉ được trả tạm rồi giữ lại ngay).
  - Nút chỉ hiện khi LINE của tiệm đã cấu hình.
- Đặt hàng kiểm tra tồn kho tại server; thiếu thì từ chối kèm tên món và số còn.

### 4.2 Với nhân viên

- Tin LINE vào nhóm nhân viên **một lần** khi một cỡ chạm ngưỡng thấp (mặc định 5) ở một chi nhánh, kể cả khi về 0 ("หมดแล้ว").
- Dashboard và menu "สต็อก" có số món sắp hết.

## 5. Tìm và lọc trong admin

Trang Sản phẩm: tìm theo tên/tên tiếng Anh/slug; lọc theo danh mục; lọc theo trạng thái (đang hiện, đang ẩn, nổi bật trang chủ, chưa có ảnh, đang có khuyến mãi).

## 6. Chưa làm (đề xuất cho giai đoạn sau)

Xếp theo mức ưu tiên đề xuất:

1. ~~Nhiều ảnh cho một sản phẩm~~ đã làm (xem mục 1.1).
2. **Mã giảm giá (coupon)** áp trên cả đơn, ví dụ "ลด 50 บาท เมื่อซื้อครบ 500". Cần thêm ô nhập mã ở checkout và quy tắc kết hợp với khuyến mãi theo sản phẩm.
3. **Lịch sử đổi giá** (ai đổi, khi nào, từ bao nhiêu). Hiện chỉ có lịch sử tồn kho.
4. **Giới hạn số lượng mua** mỗi đơn cho hàng khuyến mãi.
5. **SEO**: tiêu đề và mô tả riêng cho từng trang sản phẩm, ảnh chia sẻ mạng xã hội.
6. **Nội dung tiếng Anh** cho shop (đã có tên tiếng Anh, chưa có giao diện).
7. **Báo cáo hiệu quả khuyến mãi** (doanh thu và số đơn trong thời gian chạy).
8. **Phân quyền nhân viên**: hiện mọi nhân viên đều sửa được giá và khuyến mãi. Nên tách quyền "chủ tiệm" và "nhân viên bán hàng".
