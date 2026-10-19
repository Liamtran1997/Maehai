# Spec: Đo lường hiệu quả web bán hàng (สถิติการใช้งานเว็บ)

Trạng thái: **kế hoạch, chưa triển khai**. Cập nhật: 19/10/2026. Các câu hỏi cho chủ tiệm ở mục 13 chưa có trả lời.

Mục tiêu: trả lời bằng số liệu câu hỏi **"đưa web bán hàng vào dùng có thực sự giúp tiệm bán được nhiều hơn không"**, và chỉ ra chỗ cần sửa khi chưa đạt. Đo hành vi khách trên shop từ phía trình duyệt (client), ghép với số đơn và doanh thu thật ở máy chủ, rồi hiện trong một trang quản trị cho chủ tiệm.

Khác với **báo cáo ภาพรวม** hiện có (doanh thu, đơn đã thanh toán): báo cáo đó cho biết *bán được bao nhiêu*. Spec này thêm *khách đi qua web thế nào*, *rơi ở bước nào*, *từ đâu tới*, *web có đủ nhanh trên điện thoại thật không*, và *so với trước khi có web thì sao*.

---

## 1. Hiện trạng liên quan

| Chỗ | Hiện trạng | Ảnh hưởng tới kế hoạch |
|---|---|---|
| Go-live (`docs/go-live-checklist.md`) | Web **chưa mở cho khách**. Trước đây khách đặt qua LINE và điện thoại, site cũ maehai.com chỉ để xem | Hệ thống **không có số liệu "trước"**. Muốn so trước/sau phải ghi baseline từ bây giờ, trước ngày mở (mục 9) |
| Doanh thu online (`reports/services.py`) | Tính từ `Payment` đã xác nhận, theo ngày giờ Bangkok, có so với kỳ trước | Là **nguồn sự thật** cho đơn và tiền. Số liệu client chỉ dùng cho hành vi, không dùng để tính doanh thu |
| Đơn hàng (`orders.Order`) | Không có trường nguồn/kênh. Không biết đơn đến từ LINE, Facebook hay QR tại quầy | Thêm mã phiên ẩn danh và nguồn truy cập vào đơn khi tạo (mục 5.3) |
| Lượt bấm hero chiến dịch | Đã đếm ở máy chủ qua link chuyển hướng `/api/shop/campaign/<id>/go`, không dùng cookie | Giữ nguyên cách đếm; hiện thêm trong trang mới |
| Bán tại quầy (kho → "ปิดยอดหน้าร้าน") | Nhân viên nhập số đã bán tại quầy theo ngày, chi nhánh | Dùng để xem web có **lấy khách của quầy** hay **thêm khách mới** (mục 9.2) |
| Đơn qua LINE / điện thoại | **Không** nhập vào hệ thống (giả định, cần chủ tiệm xác nhận, Q2) | Cần một form ghi số đơn kênh khác theo ngày (mục 9.1) |
| Chính sách bảo mật mục 6 | Ghi "chỉ dùng cookie cần thiết" và dữ liệu lưu trên máy (giỏ hàng) | Thiết kế **không dùng cookie**, không định danh cá nhân. Câu chữ mục 6 vẫn cần cập nhật và qua tư vấn pháp lý (mục 7) |
| Quyền `reports.view` | Owner, manager xem doanh thu | Trang mới dùng chung quyền này |
| Lighthouse (phòng thí nghiệm) | Đã đo trên máy phát triển: LCP mobile 2,9–3,8 s, giả lập mạng chậm | Số đo phòng thí nghiệm không phản ánh khách thật. Spec này đo **trên máy khách thật** (Core Web Vitals) |

---

## 2. Câu hỏi kinh doanh cần trả lời

| # | Câu hỏi | Chỉ số trả lời | Ai dùng |
|---|---|---|---|
| B1 | Web có mang thêm đơn và doanh thu cho tiệm không, hay chỉ chuyển khách từ LINE/quầy sang? | Tổng đơn mọi kênh trước/sau; tỉ trọng online; đơn LINE/điện thoại; bán tại quầy | Chủ tiệm |
| B2 | Khách rơi ở bước nào? | Phễu: vào web → xem sản phẩm → thêm giỏ → bắt đầu thanh toán → đặt đơn → đã thanh toán | Chủ tiệm, người làm web |
| B3 | Khách đến từ đâu, kênh nào ra đơn? | Phiên, đơn, doanh thu theo nguồn (LINE, Facebook, Google, QR tại quầy, gõ trực tiếp) | Chủ tiệm (quyết định đăng bài, in QR) |
| B4 | Sản phẩm nào được xem nhiều nhưng ít người mua? | Lượt xem → thêm giỏ → bán, theo sản phẩm | Chủ tiệm (giá, ảnh, mô tả) |
| B5 | Web có đủ nhanh và ổn định trên điện thoại khách không? | LCP, INP, CLS phân vị 75 (p75) theo thiết bị; tỉ lệ lỗi | Người làm web |
| B6 | Một thay đổi giao diện hoặc chiến dịch có làm tốt lên không? | Chỉ số trước/sau quanh **mốc sự kiện**; so theo phiên bản giao diện | Chủ tiệm, người làm web |
| B7 | Khách tìm gì mà không thấy? | Từ khóa tìm kiếm không có kết quả | Chủ tiệm (thêm món, đặt tên) |

---

## 3. Nguyên tắc

1. **Tiền và đơn lấy từ máy chủ.** Client có thể bị chặn (trình chặn quảng cáo, mất mạng), nên con số đơn và doanh thu luôn tính từ `Order`/`Payment`. Client chỉ đo hành vi.
2. **Không định danh cá nhân.** Không cookie, không lưu IP, không ghi tên, số điện thoại, địa chỉ, số đơn hay token trên URL. Phiên là một mã ngẫu nhiên, mất khi đóng tab.
3. **Tôn trọng lựa chọn của khách.** Trình duyệt bật Do Not Track hoặc Global Privacy Control thì không gửi gì. Có cách tắt trong trang chính sách.
4. **Không dùng dịch vụ bên thứ ba** (Google Analytics, Facebook Pixel): dữ liệu ở lại máy chủ của tiệm, không cần chia sẻ với bên khác trong chính sách bảo mật, không thêm script nặng.
5. **Số liệu nhỏ phải hiện số tuyệt đối.** Tiệm nhỏ có ít phiên; tỉ lệ % trên 12 phiên dễ gây hiểu lầm. Mọi tỉ lệ hiện kèm số đếm, và báo "ít dữ liệu" khi mẫu dưới ngưỡng (mặc định 100 phiên).
6. **Trước/sau không phải nhân quả.** Mùa lễ, khuyến mãi, giá, thời tiết đều ảnh hưởng doanh số. Trang báo cáo luôn ghi rõ điều này và hiện các mốc sự kiện cạnh biểu đồ.
7. **Nhẹ.** Script đo không làm chậm trang: gửi gộp, gửi khi rời trang (`sendBeacon`), dưới 3 KB.

---

## 4. Định nghĩa chỉ số

| Chỉ số | Công thức | Nguồn |
|---|---|---|
| Phiên (session) | Số mã phiên khác nhau có ít nhất một lượt xem trang | Client |
| Tỉ lệ xem sản phẩm | Phiên có ≥1 lượt xem trang chi tiết / phiên | Client |
| Tỉ lệ thêm giỏ | Phiên có ≥1 lần thêm giỏ / phiên | Client |
| Tỉ lệ bắt đầu thanh toán | Phiên vào trang thanh toán khi giỏ có hàng / phiên | Client |
| **Tỉ lệ chuyển đổi** | Đơn tạo từ web (đơn có mã phiên) / phiên | Server (đơn) + Client (phiên) |
| Tỉ lệ thanh toán xong | Đơn đã xác nhận thanh toán / đơn đã tạo | Server |
| Tỉ lệ bỏ giỏ | 1 − (phiên đặt đơn / phiên thêm giỏ) | Server + Client |
| Giá trị đơn trung bình (AOV) | Doanh thu đã xác nhận / số đơn đã thanh toán (giống báo cáo ภาพรวม) | Server |
| Doanh thu online | Tổng `Payment` đã xác nhận trong kỳ | Server |
| Đơn hủy vì quá hạn | Đơn bị scheduler hủy do không thanh toán / đơn tạo | Server |
| Tỉ trọng online | Đơn web / (đơn web + đơn LINE/điện thoại + đơn tại quầy quy đổi) | Server + nhập tay (mục 9) |
| LCP, INP, CLS | Phân vị 75 trên các lượt đo thật, tách điện thoại/máy tính. Ngưỡng tốt: LCP ≤ 2,5 s, INP ≤ 200 ms, CLS ≤ 0,1 | Client |
| Tỉ lệ lỗi | Phiên có lỗi JavaScript / phiên | Client (giai đoạn 3) |

Một ngày tính theo giờ Bangkok, như các báo cáo hiện có.

---

## 5. Thu thập dữ liệu

### 5.1 Sự kiện phía khách (shop)

| Sự kiện | Khi nào | Dữ liệu riêng |
|---|---|---|
| `page_view` | Mỗi lần đổi trang | Đường dẫn **đã chuẩn hóa**: bỏ toàn bộ query; `/orders/MH-…` thành `/orders/:number` |
| `product_view` | Mở trang chi tiết sản phẩm | `slug` |
| `add_to_cart` | Bấm "เพิ่มลงตะกร้า" thành công | `slug`, cỡ, số lượng, giá trị (satang, chỉ để tham khảo) |
| `cart_view` | Mở trang giỏ hàng | Số món, giá trị |
| `checkout_start` | Mở trang thanh toán khi giỏ có hàng | Số món, giá trị |
| `search` | Tìm kiếm trên trang danh sách | Từ khóa (tối đa 40 ký tự, chữ thường), số kết quả |
| `web_vital` | Trình duyệt báo LCP, INP, CLS, FCP, TTFB | Tên chỉ số, giá trị, xếp loại (good/needs-improvement/poor), loại trang |
| `js_error` | Lỗi JavaScript chưa bắt (giai đoạn 3) | Thông điệp đã cắt ngắn, trang. Không gửi stack chứa dữ liệu nhập |

**Thuộc tính chung của mọi sự kiện:** thời điểm, mã phiên, thiết bị (điện thoại/tablet/máy tính theo bề rộng màn hình), nguồn của phiên (mục 5.2), phiên bản giao diện (`design_version`, ví dụ `2026-10-redesign`), trang vào đầu tiên.

**Không gửi:** tên, số điện thoại, địa chỉ, ghi chú, mã giảm giá đã nhập, số đơn, token, nội dung ô nhập, toàn bộ URL có query, IP (máy chủ chỉ dùng IP tạm thời để giới hạn tần suất, không lưu).

### 5.2 Nguồn truy cập

Xác định một lần khi phiên bắt đầu, theo thứ tự:

1. `utm_source` trên link (ví dụ link trong bài Facebook, QR in tại quầy `?utm_source=qr_srinarong`). Chỉ nhận chữ, số, `_`, `-`, tối đa 40 ký tự.
2. Trang giới thiệu (referrer), chỉ giữ **nhóm**: `line`, `facebook`, `google`, `tiktok`, `instagram`, `other`. Không lưu URL đầy đủ.
3. Không có gì: `direct`.

**Đề xuất cho tiệm:** in QR cho từng chi nhánh với `utm_source` riêng, và dùng link có `utm_source=line_oa` trong tin nhắn LINE OA. Nếu không, nhiều lượt từ LINE sẽ hiện là `direct` vì ứng dụng LINE không luôn gửi referrer.

### 5.3 Ghép phiên với đơn (phía máy chủ)

- Khi tạo đơn, shop gửi kèm mã phiên và nguồn của phiên (hai trường **tuỳ chọn** trong body `POST /api/orders`).
- Máy chủ lưu vào đơn (`session_ref`, `traffic_source`). Từ đó tính đơn và doanh thu **theo nguồn** và tỉ lệ chuyển đổi mà không phụ thuộc client có gửi được sự kiện "đặt đơn" hay không.
- Đơn không có mã phiên (khách tắt đo, bị chặn) vẫn tính vào doanh thu, xếp nguồn `unknown`.

### 5.4 Nhận sự kiện (máy chủ)

- `POST /api/analytics/events`, công khai, nhận một **lô tối đa 20 sự kiện**, kiểu nội dung `text/plain` hoặc JSON (để `sendBeacon` gửi được không cần preflight CORS).
- Kiểm tra từng trường theo danh sách cho phép; trường lạ bị bỏ. Lô sai định dạng trả 204 nhưng không ghi (không lộ chi tiết cho người dò).
- Giới hạn tần suất theo IP bằng `core.ratelimit` (chính sách mới `analytics`, ví dụ 120 lô/phút). Tối đa 300 sự kiện mỗi phiên mỗi ngày.
- Bỏ qua bot: User-Agent của crawler phổ biến, trình duyệt headless.
- Ghi vào bảng sự kiện thô; không chạy truy vấn nặng trong request.

---

## 6. Lưu trữ

| Bảng | Nội dung | Giữ bao lâu |
|---|---|---|
| `WebEvent` | Sự kiện thô (mục 5.1) | **180 ngày**, rồi xóa (`prune_web_events`, chạy trong `scheduler` mỗi đêm) |
| `WebDailyStat` | Tổng hợp theo ngày × thiết bị × nguồn × phiên bản giao diện: phiên, xem SP, thêm giỏ, bắt đầu thanh toán, p75 LCP/INP/CLS | Lâu dài (số liệu tổng, không có mã phiên) |
| `WebProductDailyStat` | Theo ngày × sản phẩm: lượt xem, lượt thêm giỏ | Lâu dài |
| `Order` (thêm trường) | `session_ref` (32 ký tự, rỗng được), `traffic_source` (40 ký tự) | Theo đơn |
| `SalesChannelEntry` | Nhập tay: ngày, kênh (`line`, `phone`, `other`), số đơn, doanh thu (tuỳ chọn), ghi chú, người nhập | Lâu dài |
| `Milestone` | Mốc sự kiện: ngày, tên, loại (`release`, `campaign`, `promotion`, `other`) | Lâu dài |

Tổng hợp chạy mỗi đêm cho ngày hôm trước, và có thể chạy lại cho một khoảng ngày (`rollup_web_stats --from --to`). Trang báo cáo đọc từ bảng tổng hợp; riêng "hôm nay" tính trực tiếp từ bảng thô.

---

## 7. Quyền riêng tư (PDPA)

- Không cookie, không định danh cá nhân, không theo dõi giữa các lần ghé (mã phiên trong `sessionStorage`, mất khi đóng tab). Vì vậy **không cần banner đồng ý cookie** theo thiết kế này, nhưng **kết luận này phải được tư vấn pháp lý xác nhận** (Q7).
- Trang chính sách cần thêm vào mục 6 một đoạn: tiệm thu thống kê ẩn danh về cách dùng web và tốc độ tải để cải thiện cửa hàng, không gắn với cá nhân, giữ dữ liệu thô 180 ngày, và cách tắt. **Câu chữ do chủ tiệm và tư vấn pháp lý duyệt**, người làm web không tự sửa văn bản pháp lý.
- Đơn hàng giữ `session_ref` là mã ngẫu nhiên; không thể dùng để tìm lại người mua qua web.
- Trang chính sách có nút "ไม่ส่งสถิติการใช้งาน" lưu lựa chọn trong `localStorage` của máy đó.

---

## 8. Trang quản trị: "สถิติเว็บ"

Mục mới trong menu nhóm **หน้าร้าน**, quyền `reports.view`. Bố cục từ trên xuống (điện thoại: cùng thứ tự, một cột):

1. **Thanh chọn kỳ:** วันนี้ / 7 วัน / 30 วัน / 90 วัน / tự chọn; so với kỳ trước có cùng độ dài. Lọc theo thiết bị, nguồn.
2. **Ô số liệu:** phiên, tỉ lệ chuyển đổi, đơn từ web, doanh thu online, AOV. Mỗi ô có số kỳ trước và mũi tên. Mẫu nhỏ thì ghi "ข้อมูลยังน้อย".
3. **Phễu:** 6 bước (mục 2, B2), mỗi bước có số phiên, % so với bước đầu và % rơi so với bước trước. Bước rơi nhiều nhất được tô nổi và có gợi ý chỗ cần xem (ví dụ rơi nhiều ở thanh toán thì xem phí ship, cách nhận hàng).
4. **Biểu đồ theo ngày:** phiên và đơn, kèm **mốc sự kiện** (vạch dọc có nhãn: ngày mở web, chiến dịch bắt đầu/kết thúc lấy tự động từ `cms`, khuyến mãi, mốc nhập tay).
5. **Nguồn truy cập:** bảng phiên, đơn, doanh thu, tỉ lệ chuyển đổi theo nguồn.
6. **Sản phẩm:** xem → thêm giỏ → bán (bán lấy từ đơn đã thanh toán); sắp theo "xem nhiều mua ít".
7. **Tìm kiếm không có kết quả:** 20 từ khóa nhiều nhất.
8. **Tốc độ trên máy khách:** p75 LCP, INP, CLS theo điện thoại/máy tính, màu theo ngưỡng tốt/cần cải thiện/kém, số lượt đo.
9. **Trước / sau** (mục 9): khối so sánh tổng mọi kênh quanh một mốc được chọn.
10. **Xuất CSV** số liệu theo ngày (giai đoạn 4).

Cuối trang luôn có một dòng giải thích bằng tiếng Thái: số đơn và tiền tính ở máy chủ; số phiên có thể thấp hơn thật do khách tắt đo hoặc chặn; trước/sau không chứng minh nguyên nhân.

---

## 9. Đánh giá "web có cải thiện bán hàng không"

### 9.1 Ghi baseline trước khi mở web

Vì hệ thống chưa có số liệu "trước":

- Thêm form **"ยอดช่องทางอื่น"** trong trang thống kê: mỗi ngày (hoặc mỗi tuần) nhân viên nhập số đơn qua LINE và điện thoại, doanh thu nếu có.
- Bắt đầu nhập **ít nhất 4 tuần trước ngày mở web**, và **tiếp tục sau khi mở**. Nếu chỉ nhập trước, sẽ không thấy được khách chuyển từ LINE sang web.
- Bán tại quầy lấy từ "ปิดยอดหน้าร้าน" đã có, quy đổi ra số món và doanh thu theo giá niêm yết.
- Nếu có sổ sách cùng kỳ năm trước (Q4), nhập tổng theo tháng làm mốc so sánh theo mùa.

### 9.2 Cách đọc kết quả

| Kết quả | Ý nghĩa |
|---|---|
| Đơn web tăng, đơn LINE/điện thoại **giữ nguyên**, quầy giữ nguyên | Web **mang thêm khách** |
| Đơn web tăng, đơn LINE/điện thoại **giảm tương ứng** | Web **chuyển kênh**: chưa thêm doanh thu, nhưng có thể giảm việc trả lời tin nhắn (đo bằng số tin LINE, Q5) |
| Đơn web tăng, quầy giảm | Khách quầy đặt online. Xem phí ship, quãng đường |
| Tổng mọi kênh tăng so với cùng kỳ năm trước và 4 tuần trước | Dấu hiệu tốt, nhưng loại trừ mùa lễ và khuyến mãi bằng mốc sự kiện |

### 9.3 Mục tiêu thành công (chốt với chủ tiệm, Q3)

Đề xuất để thảo luận, chưa phải cam kết:

| Sau 3 tháng mở web | Đề xuất |
|---|---|
| Tỉ lệ chuyển đổi (đơn / phiên) | [ระบุ, gợi ý 1,5–3 % cho cửa hàng thực phẩm nhỏ] |
| Tỉ trọng đơn online trên tổng đơn đặt trước | [ระบุ] |
| Tổng đơn mọi kênh so với baseline 4 tuần | [ระบุ] |
| Tỉ lệ thanh toán xong (đơn đã trả / đơn tạo) | ≥ 80 % (thấp hơn thì xem QR, thời gian giữ hàng) |
| p75 LCP trên điện thoại | ≤ 2,5 s |

### 9.4 So sánh giao diện về sau

- Mọi sự kiện mang `design_version`. Khi đổi giao diện, tăng phiên bản trong biến build; trang thống kê lọc được theo phiên bản.
- Thử A/B (chia ngẫu nhiên khách giữa hai giao diện cùng lúc) là cách duy nhất loại được ảnh hưởng mùa vụ, nhưng cần lượng khách đủ lớn. Để ở giai đoạn 4, chỉ làm khi phiên/tháng đủ (ước lượng ở Q6).

---

## 10. API

| Phương thức | Đường dẫn | Quyền | Ghi chú |
|---|---|---|---|
| POST | `/api/analytics/events` | Công khai, giới hạn tần suất | Mục 5.4 |
| POST | `/api/orders` (đổi) | Như cũ | Thêm `session_ref`, `traffic_source` tuỳ chọn |
| GET | `/api/admin/analytics/summary?days=&from=&to=&device=&source=` | `reports.view` | Ô số liệu, phễu, chuỗi theo ngày, so kỳ trước |
| GET | `/api/admin/analytics/sources`, `/products`, `/searches`, `/vitals` | `reports.view` | Các bảng mục 8 |
| GET/POST/PUT/DELETE | `/api/admin/analytics/channel-entries` | `reports.view` để xem; `orders.view` để nhập (Q2) | Form mục 9.1 |
| GET/POST/DELETE | `/api/admin/analytics/milestones` | `reports.view` | Mốc nhập tay; mốc chiến dịch lấy tự động |
| GET | `/api/admin/analytics/before-after?date=&days=` | `reports.view` | Mục 9 |

---

## 11. Giai đoạn triển khai

| Giai đoạn | Nội dung | Kết quả kiểm tra |
|---|---|---|
| **1. Thu thập** (làm trước ngày mở web) | Script đo trên shop (5.1, 5.2), endpoint nhận (5.4), `WebEvent`, ghép phiên với đơn (5.3), tôn trọng DNT/GPC, xóa sau 180 ngày, form "ยอดช่องทางอื่น" để bắt đầu ghi baseline | Test backend: nhận/lọc lô, giới hạn tần suất, bỏ bot, không lưu IP, đơn có nguồn; e2e: duyệt shop → đặt đơn → có sự kiện và đơn mang mã phiên; kiểm tra không có tên/SĐT/token trong bảng sự kiện |
| **2. Báo cáo** | Tổng hợp hằng đêm, trang "สถิติเว็บ" phần 1–8, mốc chiến dịch tự động | Test số liệu phễu, p75, so kỳ trước trên dữ liệu mẫu; xem trên điện thoại |
| **3. Trước/sau và chất lượng** | Khối trước/sau, mốc nhập tay, `js_error`, cảnh báo "ít dữ liệu" | Test so sánh quanh mốc; kiểm tra với dữ liệu baseline nhập tay |
| **4. Mở rộng (khi cần)** | Xuất CSV, A/B giao diện, báo LINE cho chủ tiệm khi tỉ lệ chuyển đổi tụt mạnh | Theo từng mục |

Giai đoạn 1 phải chạy **ít nhất 4 tuần trước ngày mở web** để có baseline kênh LINE/điện thoại (mục 9.1).

---

## 12. Rủi ro

| Rủi ro | Cách giảm |
|---|---|
| Trình chặn quảng cáo chặn script đo, số phiên thấp hơn thật | Gửi về tên miền của tiệm (không phải bên thứ ba), đường dẫn trung tính; đơn và tiền vẫn đúng vì tính ở máy chủ |
| Bot, người dò làm phồng số liệu | Lọc User-Agent, giới hạn tần suất, giới hạn sự kiện mỗi phiên |
| Mẫu nhỏ dẫn tới kết luận sai | Hiện số tuyệt đối, ngưỡng "ít dữ liệu", khuyến nghị đọc theo tháng |
| Mùa lễ, khuyến mãi làm sai so sánh trước/sau | Mốc sự kiện tự động, so cùng kỳ năm trước khi có sổ sách |
| Nhân viên quên nhập "ยอดช่องทางอื่น" | Nhắc trong mục "ต้องจัดการ" ở trang ภาพรวม khi hôm qua chưa nhập |
| Thu thập vượt quá điều chính sách cho phép | Danh sách trường cho phép ở máy chủ; test kiểm tra không có dữ liệu cá nhân; pháp lý duyệt câu chữ (mục 7) |

---

## 13. Câu hỏi cho chủ tiệm

| # | Câu hỏi | Vì sao cần |
|---|---|---|
| Q1 | Ngày dự kiến mở web cho khách? | Lùi lại 4 tuần để bắt đầu giai đoạn 1 và ghi baseline |
| Q2 | Đơn qua LINE và điện thoại hiện ghi ở đâu (sổ, Excel, không ghi)? Ai sẽ nhập số mỗi ngày? | Quyết định form 9.1 và quyền nhập |
| Q3 | Thế nào là "thành công" sau 3 tháng (mục 9.3)? | Chốt mục tiêu trước khi đo, tránh đọc số theo cảm tính |
| Q4 | Có số đơn/doanh thu theo tháng của năm trước không? | So cùng kỳ, loại ảnh hưởng mùa vụ |
| Q5 | Có muốn đo số tin nhắn hỏi hàng trên LINE OA không (LINE cho xem thống kê)? | Đo lợi ích "giảm việc trả lời tin nhắn" khi khách tự đặt trên web |
| Q6 | Ước lượng số khách ghé web mỗi tháng? | Quyết định có làm A/B hay không (cần mẫu đủ lớn) |
| Q7 | Tư vấn pháp lý có đồng ý thống kê ẩn danh không cookie không cần banner đồng ý không? | Quyết định có thêm bước đồng ý trên shop hay không |
| Q8 | In QR riêng cho từng chi nhánh và dùng link có `utm_source` trong LINE OA được không? | Đo đúng nguồn khách (mục 5.2) |

---

## 14. Không làm trong phạm vi này

- Google Analytics, Facebook Pixel hay công cụ bên thứ ba khác.
- Ghi màn hình (session recording), bản đồ nhiệt (heatmap).
- Theo dõi một khách qua nhiều lần ghé, hồ sơ khách hàng, quảng cáo bám đuổi.
- Đo hành vi trong trang quản trị.
- Tự kết luận nguyên nhân (máy học, mô hình thống kê). Báo cáo đưa số liệu và mốc, người đọc quyết định.
