# Spec: Kho v2 (tồn kho theo chi nhánh)

Trạng thái: **giai đoạn 1 đã triển khai** (mục 4, 5, 8.1–8.3, 12.1–12.3). Các giai đoạn 2 đến 4 vẫn là đề xuất. Cập nhật: 12/10/2026.

Ghi chú giai đoạn 1 (khác với văn bản đề xuất bên dưới):
- Chưa chốt Q1 và Q4 với chủ tiệm, nên làm theo đề xuất: hạn mức online (Q1 = A) và giữ hàng 60 phút (Q4). Đổi bằng cấu hình từng món (`online_quota`) và `ORDER_UNPAID_EXPIRY_MINUTES`.
- File CSV chỉ nhận `tracking` = `none` hoặc `stock`. `daily` và cột `daily_capacity` thuộc giai đoạn 2, hiện báo lỗi "ยังไม่รองรับ".
- Nút "หมดหน้าร้าน" dùng quyền `inventory.adjust` (cho nhân viên bán hàng bấm ở chi nhánh của mình thuộc mục 14, giai đoạn 3).
- Mục 8.4 (nhắc báo phí ship sau 4 giờ) và 8.5 (đếm ngược trên trang đơn của khách) chưa làm.
- Cảnh báo "sắp hết" chỉ phát khi tồn **giảm** xuống ngưỡng. Nhập hàng mà vẫn thấp thì không báo.
Phạm vi: trang quản trị mục **สต็อก**, cách đơn online giữ và trừ hàng, và thông báo liên quan.
Cần chủ tiệm chốt các quyết định ở mục 2 trước khi làm.

## 1. Hiện trạng và vấn đề

### 1.1 Hệ thống đang làm gì

| Phần | Cách làm hiện tại |
|---|---|
| Số liệu | Mỗi cỡ, mỗi chi nhánh có `on_hand` (đang có) và `reserved` (đang giữ cho đơn). Còn bán được = `on_hand − reserved` |
| Theo dõi | Bật/tắt theo từng cỡ. Cỡ không theo dõi luôn coi là còn hàng |
| Đơn online | Đặt đơn thì giữ hàng ở **một** chi nhánh đủ cả đơn (nhận tại tiệm: đúng chi nhánh đó; giao: chi nhánh mặc định trước). Hủy thì trả lại. Gửi hoặc hoàn tất thì trừ hẳn |
| Thao tác kho | Nhập hàng, ghi hàng hỏng, kiểm kê (ghi đè số), chuyển kho (tức thì) |
| Sổ kho | Mọi thay đổi ghi lại: số thay đổi, số sau, lý do, người làm, đơn liên quan |
| Cảnh báo | Báo LINE nhóm nhân viên khi một cỡ chạm ngưỡng thấp (chung cho mọi món, mặc định 5). Khách đăng ký báo khi có hàng lại |

### 1.2 Vấn đề

| # | Vấn đề | Hậu quả |
|---|---|---|
| V1 | Bán tại quầy không trừ kho | Số online lệch dần so với thực tế, bán quá số đang có |
| V2 | Chưa có cỡ nào bật theo dõi, không có cách nhập tồn đầu kỳ hàng loạt | Lúc mở bán mọi món luôn "còn hàng" |
| V3 | Hàng tươi có hạn dùng nhưng hệ thống không biết lô hay ngày hết hạn | Không biết món nào sắp hỏng, không xuất theo hạn gần trước |
| V4 | Khách chọn ngày nhận tương lai, kho chỉ biết số hôm nay | Nhận đơn cho ngày mai dựa trên hàng hôm nay (có thể đã hỏng tới lúc đó) hoặc từ chối đơn mà ngày mai làm kịp |
| V5 | Đơn chưa thanh toán giữ hàng tới 24 giờ (job hủy chạy mỗi giờ), trong khi mã QR hết hạn sau 15 phút | Hàng bị khóa gần 1 ngày bởi đơn không ai trả tiền |
| V6 | Kiểm kê ghi đè từng món, không có phiếu, không có bước duyệt | Không biết chênh lệch bao nhiêu, ai duyệt |
| V7 | Chuyển kho xảy ra ngay, không có bước nhận | Hàng "biến mất" khi đang trên đường cũng không ai biết |
| V8 | Thiếu lý do: khách trả, hỏng khi giao, dùng nội bộ, sửa sai | Dồn hết vào "kiểm kê" hoặc "hàng hỏng", sổ kho mất ý nghĩa |
| V9 | Ngưỡng sắp hết dùng chung, và chỉ kiểm tra khi có đơn online | Ghi hàng hỏng hay chuyển kho làm tụt dưới ngưỡng cũng không báo |
| V10 | Không có giá vốn | Không tính được giá trị tồn và lãi gộp |
| V11 | Nhân viên kho thao tác được mọi chi nhánh | Không khoanh được trách nhiệm theo chi nhánh |

## 2. Quyết định cần chủ tiệm chốt

| # | Câu hỏi | Lựa chọn | Đề xuất |
|---|---|---|---|
| Q1 | Xử lý bán tại quầy thế nào? | A. **Hạn mức online**: mỗi ngày dành riêng N món cho online, quầy bán phần còn lại. B. **Nhập doanh số quầy** cuối ngày để trừ kho. C. Kết nối máy POS | **A** cho lúc mở bán (đơn giản, không cần nhân viên quầy nhập liệu). B làm thêm khi cần số liệu tồn chính xác. C để sau |
| Q2 | Món làm tươi tính theo tồn hay theo năng lực làm mỗi ngày? | A. Theo tồn (như hiện tại). B. Theo **năng lực theo ngày**: mỗi ngày làm tối đa N, đơn trừ vào ngày nhận | **B cho món làm tươi** (หมูยอ, แหนม…), **A cho hàng khô/đóng gói** (เส้น, หอมเจียว…). Hai cách chạy song song, chọn theo từng cỡ |
| Q3 | Có quản lý lô và hạn dùng không? | Có / Không | **Có**, chỉ cho món chọn "theo tồn" và có hạn dùng |
| Q4 | Giữ hàng cho đơn chưa thanh toán bao lâu? | Giữ nguyên 24 giờ / rút ngắn | **60 phút**, trừ khi khách đã gửi slip (chờ nhân viên kiểm tra thì giữ tiếp) |
| Q5 | Ngưỡng duyệt điều chỉnh | Số lượng hoặc giá trị | Hàng hỏng hoặc chênh lệch kiểm kê **> 20 món** (hoặc **> ฿1,000** khi đã có giá vốn) cần quản lý duyệt |

Các mục dưới viết theo các đề xuất này. Chọn khác thì chỉ cần sửa mục tương ứng.

## 3. Khái niệm

| Thuật ngữ | Nghĩa |
|---|---|
| Kiểu theo dõi (mỗi cỡ) | `none`: không theo dõi, luôn còn hàng. `stock`: theo tồn thực. `daily`: theo năng lực theo ngày |
| Tồn (`on_hand`) | Số đang có thật ở chi nhánh |
| Đang giữ (`reserved`) | Đã hứa cho đơn online chưa giao |
| Hạn mức online | Số tối đa online được bán ra từ chi nhánh trong một ngày (chỉ áp dụng kiểu `stock`) |
| Còn bán online | `min(on_hand − reserved, hạn mức online còn lại hôm nay)` |
| Năng lực ngày | Số tối đa làm được cho một ngày nhận, ở một chi nhánh (kiểu `daily`) |
| Lô | Một lần nhập hoặc một mẻ làm: số lượng, ngày làm, ngày hết hạn |

## 4. Bán tại quầy: hạn mức online (Q1 = A)

1. Mỗi cỡ kiểu `stock`, mỗi chi nhánh có **hạn mức online/ngày** (bỏ trống = không giới hạn, dùng hết tồn).
2. Hạn mức tính lại lúc 00:00 giờ Thái mỗi ngày. Đơn online đặt trong ngày trừ vào hạn mức của ngày đặt; đơn bị hủy trả lại hạn mức nếu còn trong ngày.
3. Shop hiển thị "เหลือ N ชิ้น" theo **còn bán online**, không theo tồn thật.
4. Trang สต็อก có cột "ออนไลน์วันนี้" (đã bán / hạn mức), sửa nhanh được ngay trên bảng.
5. Khi quầy bán hết trước, nhân viên bấm **"หมดหน้าร้าน"**: đặt tồn về bằng số đang giữ, ghi sổ lý do `counter_sale`. Online ngừng bán ngay.

**Giai đoạn sau (Q1 = B):** màn "ปิดยอดหน้าร้าน" cuối ngày, nhập số bán quầy từng món. Hệ thống trừ tồn với lý do `counter_sale`.

## 5. Tồn đầu kỳ và bật theo dõi hàng loạt

1. Trang สต็อก có nút **"นำเข้าสต็อก"**, nhận file CSV: `sku, branch_code, tracking (none|stock|daily), on_hand, online_quota, daily_capacity, low_stock_threshold`.
2. Có **xem trước**: dòng hợp lệ, dòng lỗi (SKU không có, chi nhánh sai, số âm, kiểu theo dõi không hợp với cột có giá trị), chênh lệch so với hiện tại. Chỉ ghi khi bấm xác nhận.
3. Ghi tồn qua sổ kho với lý do `opening` (lần đầu) hoặc `count` (các lần sau). Không bao giờ ghi thấp hơn số đang giữ (giống quy tắc hiện tại).
4. Tải được file mẫu có sẵn toàn bộ SKU và chi nhánh hiện có.
5. Quyền: `inventory.adjust`. Ghi vào nhật ký hoạt động: người làm, số dòng, tên file.

## 6. Lô và hạn dùng (Q3)

Áp dụng cho cỡ kiểu `stock` có bật **"มีวันหมดอายุ"**.

1. Nhập hàng bắt buộc nhập **ngày hết hạn** (hoặc ngày làm + số ngày dùng được, mặc định theo từng cỡ). Mỗi lần nhập tạo một lô.
2. Trừ kho (giao đơn, hàng hỏng, bán quầy) lấy từ **lô hết hạn sớm nhất trước** (FEFO), tự động; nhân viên không phải chọn lô.
3. **Lô đã hết hạn không được bán**: không tính vào "còn bán online" từ 00:00 của ngày hết hạn.
4. **Lô cho đơn ngày tương lai**: một đơn có ngày nhận D chỉ được giữ hàng từ lô hết hạn sau D.
5. **Cảnh báo:** sáng mỗi ngày gửi LINE nhóm nhân viên danh sách lô hết hạn trong **2 ngày** tới (số ngày cấu hình được). Dashboard có ô "ใกล้หมดอายุ".
6. Nút **"ตัดของหมดอายุ"** trên lô đã hết hạn: ghi hàng hỏng toàn bộ lô với lý do `expired`.
7. Kiểm kê với món có lô: nhập số theo từng lô.

## 7. Năng lực theo ngày (Q2 = B)

Áp dụng cho cỡ kiểu `daily`, thường là món làm tươi theo đơn.

1. Mỗi cỡ, mỗi chi nhánh có **năng lực mặc định/ngày** và có thể đặt riêng cho từng ngày (ví dụ ngày lễ làm nhiều hơn; ngày nghỉ = 0).
2. Đơn có ngày nhận D trừ vào năng lực của ngày D tại chi nhánh xuất hàng. Hết năng lực ngày D thì shop hiển thị "วันนี้เต็มแล้ว" và gợi ý ngày gần nhất còn chỗ.
3. Trang chọn ngày nhận ở checkout chỉ cho chọn những ngày còn đủ năng lực cho **cả giỏ**.
4. Màn **"แผนผลิต"**: theo từng ngày và chi nhánh, mỗi cỡ có: năng lực, đã nhận đơn, còn trống. In hoặc gửi LINE cho bếp lúc chốt đơn (giờ chốt = `ORDER_CUTOFF_HOUR`, hiện là 13:00).
5. Cỡ kiểu `daily` **không có tồn** và không cần kiểm kê. Hàng làm dư bán ở quầy, ngoài hệ thống.
6. Hủy đơn trả lại năng lực của ngày đó (nếu ngày đó chưa qua).

## 8. Giữ hàng cho đơn chưa thanh toán (Q4)

1. Đơn chờ thanh toán giữ hàng tối đa **60 phút** (cấu hình `ORDER_UNPAID_EXPIRY_MINUTES`, thay cho `ORDER_UNPAID_EXPIRY_HOURS=24`).
2. Đơn **đã gửi slip** thì không tự hủy (giữ như hiện tại), chờ nhân viên kiểm tra.
3. Job hủy đơn quá hạn chạy **mỗi 5 phút** (hiện là mỗi giờ).
4. Đơn chờ báo phí ship (`pending_quote`) cũng giữ hàng; nếu tiệm chưa báo phí trong **4 giờ làm việc**, gửi LINE nhắc nhân viên (không tự hủy).
5. Trang đơn của khách hiển thị thời hạn còn lại: "ชำระภายใน 45 นาที ไม่เช่นนั้นคำสั่งซื้อจะถูกยกเลิก".

## 9. Phiếu kiểm kê

Thay cho kiểm kê ghi đè từng món hiện tại.

| Bước | Ai | Việc |
|---|---|---|
| 1. Tạo phiếu | Kho, quản lý | Chọn chi nhánh và phạm vi (tất cả / một danh mục / chọn món). Hệ thống chụp lại số tồn lúc tạo |
| 2. Đếm | Kho | Nhập số đếm được (theo lô nếu có). Lưu nháp được, đếm trên điện thoại |
| 3. Gửi duyệt | Kho | Hệ thống tính chênh lệch = đếm − (tồn lúc tạo + thay đổi từ lúc tạo tới lúc gửi) |
| 4. Duyệt | Quản lý, chủ tiệm | Xem chênh lệch từng món. Duyệt thì ghi sổ lý do `count`; từ chối thì trả về bước 2 kèm lý do |

- Chênh lệch nhỏ hơn ngưỡng ở Q5 thì người đếm **tự duyệt** được.
- Trong lúc phiếu mở, đơn online vẫn chạy bình thường (không khóa kho). Bước 3 đã tính phần thay đổi trong lúc đếm.
- Phiếu đã duyệt không sửa được. Lưu lại người đếm, người duyệt, thời gian.

## 10. Chuyển kho hai bước

1. Chi nhánh gửi tạo **phiếu chuyển**: món, số lượng (và lô). Hàng rời khỏi tồn chi nhánh gửi ngay, vào trạng thái **"กำลังขนส่ง"**.
2. Chi nhánh nhận bấm **"รับของ"**, nhập số thực nhận. Số này cộng vào tồn chi nhánh nhận.
3. Nhận thiếu: phần thiếu ghi sổ lý do `transit_loss`, LINE báo quản lý.
4. Phiếu chưa nhận quá **24 giờ** thì nhắc trên dashboard.
5. Hủy phiếu chưa nhận: hàng trả về chi nhánh gửi.

## 11. Lý do ghi sổ và duyệt

| Lý do | Ý nghĩa | Hướng | Cần duyệt khi vượt ngưỡng |
|---|---|---|---|
| `opening` | Tồn đầu kỳ | + | Không |
| `receive` | Nhập hàng / mẻ làm xong | + | Không |
| `sale` | Giao đơn online | − | Không (tự động) |
| `counter_sale` | Bán tại quầy | − | Không |
| `waste` | Hỏng, rơi vỡ | − | Có |
| `expired` | Hết hạn | − | Không (có lô làm bằng chứng) |
| `return` | Khách trả lại, còn bán được | + | Không |
| `damaged_in_transit` | Hỏng khi giao cho khách | − | Có |
| `internal_use` | Dùng nội bộ, mẫu thử, biếu | − | Có |
| `count` | Chênh lệch kiểm kê | ± | Có (qua phiếu kiểm kê) |
| `transfer_out` / `transfer_in` | Chuyển kho | ∓ | Không |
| `transit_loss` | Thiếu khi nhận hàng chuyển | − | Không (đã có phiếu) |
| `correction` | Sửa nhập sai | ± | Luôn cần, bắt buộc ghi chú và chỉ tới dòng sổ bị sửa |

- Thao tác cần duyệt tạo **yêu cầu chờ duyệt**. Tồn chưa đổi cho tới khi quản lý duyệt.
- Không xóa dòng sổ kho. Sai thì ghi dòng `correction` đối ứng.

## 12. Ngưỡng sắp hết và gợi ý làm thêm

1. Ngưỡng đặt **theo từng cỡ, từng chi nhánh** (mặc định lấy `LOW_STOCK_THRESHOLD`).
2. Kiểm tra sau **mọi** thay đổi làm giảm tồn (đơn, hàng hỏng, chuyển kho, bán quầy), không chỉ khi có đơn online.
3. Báo LINE **một lần** khi vượt xuống ngưỡng; báo lại chỉ sau khi tồn đã lên trên ngưỡng rồi xuống lại.
4. Trang สต็อก có cột **"ควรผลิต/สั่งเพิ่ม"** = trung bình bán 7 ngày × số ngày cần đủ hàng (mặc định 2) − còn bán. Chỉ là gợi ý.

## 13. Giá vốn (giai đoạn 3)

1. Mỗi cỡ có **giá vốn chuẩn** (chủ tiệm nhập). Không tính giá vốn bình quân theo lô ở giai đoạn này.
2. Báo cáo: giá trị tồn theo chi nhánh, giá trị hàng hỏng/hết hạn theo tháng, lãi gộp theo món (doanh thu − giá vốn × số bán).
3. Quyền xem giá vốn: `reports.view` (nhân viên kho không thấy, giống quy tắc "không thấy tiền").

## 14. Phân quyền

| Quyền mới | Cho phép | Vai trò mặc định |
|---|---|---|
| `inventory.approve` | Duyệt điều chỉnh vượt ngưỡng, duyệt phiếu kiểm kê, sửa sai | Chủ tiệm, quản lý |
| `inventory.plan` | Đặt năng lực theo ngày, hạn mức online, xem/in kế hoạch sản xuất | Chủ tiệm, quản lý, nhân viên kho |

- **Giới hạn theo chi nhánh:** mỗi nhân viên kho gắn một hoặc nhiều chi nhánh, chỉ thấy và thao tác chi nhánh đó. Chủ tiệm, quản lý thấy tất cả.
- Nhân viên bán hàng được bấm "หมดหน้าร้าน" ở chi nhánh của mình (mục 4.5).
- Test ma trận quyền hiện có phải bao gồm các endpoint mới.

## 15. Báo cáo kho

| Báo cáo | Nội dung |
|---|---|
| Sổ kho | Lọc theo chi nhánh, món, lý do, người làm, khoảng ngày. Xuất CSV |
| Hao hụt | Hàng hỏng, hết hạn, thiếu khi chuyển, chênh lệch kiểm kê theo tháng và theo món |
| Tồn theo lô | Lô còn lại, ngày hết hạn, số ngày còn lại |
| Kế hoạch sản xuất | Mục 7.4 |
| Đang giữ | Món nào đang giữ cho đơn nào (bấm sang đơn) |

## 16. Giai đoạn triển khai

| Giai đoạn | Nội dung | Điều kiện |
|---|---|---|
| **1. Trước mở bán** | Mục 5 (nhập tồn đầu kỳ), mục 8 (giữ hàng 60 phút, job 5 phút), mục 4.1–4.5 (hạn mức online, "หมดหน้าร้าน"), mục 12.1–12.3 (ngưỡng theo món) | Chủ tiệm chốt Q1, Q4 |
| **2. Hàng tươi** | Mục 7 (năng lực theo ngày) hoặc mục 6 (lô, hạn dùng), tùy Q2/Q3 | Chủ tiệm chốt Q2, Q3; có danh sách món và năng lực |
| **3. Kiểm soát** | Mục 9, 10, 11, 14, 15 | Q5 |
| **4. Tài chính** | Mục 13, mục 4 giai đoạn B (nhập doanh số quầy) | Có giá vốn |

## 17. Tiêu chí nghiệm thu (giai đoạn 1)

1. Nhập file CSV 40 dòng: xem trước đúng lỗi, ghi đúng tồn, sổ kho có 40 dòng `opening`, nhật ký có 1 dòng.
2. Hạn mức online 10, đã bán online 10: shop báo hết dù tồn thật còn 30; quầy vẫn bán bình thường.
3. Bấm "หมดหน้าร้าน" khi có 2 đơn đang giữ: tồn = 2, còn bán online = 0, 2 đơn đó vẫn giao được.
4. Đơn chưa thanh toán sau 60 phút (cộng tối đa 5 phút chờ job) bị hủy và trả hàng; đơn đã gửi slip không bị hủy.
5. Ghi hàng hỏng làm tồn xuống dưới ngưỡng: nhóm LINE nhận đúng 1 tin.
6. Hai đơn đồng thời tranh món cuối: đúng một đơn thành công (giữ test đa luồng trên Postgres như coupon).

## 18. Ngoài phạm vi

- Nguyên liệu, công thức (BOM), tính giá thành từ nguyên liệu.
- Đơn mua hàng và nhà cung cấp.
- Kết nối máy POS tại quầy.
- Chia một đơn ra nhiều chi nhánh xuất hàng.
- Mã vạch và quét mã khi nhập, xuất.
