# Spec: Đo lường hiệu quả web bán hàng (สถิติการใช้งานเว็บ)

Trạng thái: **kế hoạch, chưa triển khai**. Cập nhật: 19/10/2026 (đã có câu trả lời của chủ tiệm, xem mục 13).

Mục tiêu: theo dõi bằng số liệu **lượng khách có tăng lên sau khi đưa web bán hàng vào dùng không**, và chỉ ra chỗ cần sửa khi chưa tăng. Kết hợp ba nguồn: dữ liệu đơn ở máy chủ (đầy đủ, không cần hỏi khách), số lượt ghé đếm ở máy chủ (không định danh), và hành vi trên trình duyệt của những khách **đồng ý** cho đo. Kết quả hiện trong một trang quản trị cho chủ tiệm.

Khác với **báo cáo ภาพรวม** hiện có (doanh thu, đơn đã thanh toán): báo cáo đó cho biết *bán được bao nhiêu*. Spec này thêm *có bao nhiêu khách, khách mới hay khách cũ*, *khách đi qua web thế nào và rơi ở bước nào*, *từ đâu tới*, và *web có đủ nhanh trên điện thoại thật không*.

---

## 1. Hiện trạng liên quan

| Chỗ | Hiện trạng | Ảnh hưởng tới kế hoạch |
|---|---|---|
| Go-live (`docs/go-live-checklist.md`) | Web **mở cho khách trong tháng 10/2026**. Trước đây khách đặt qua LINE và điện thoại, site cũ maehai.com chỉ để xem | Không có số liệu web "trước" để so. Đo **mức tăng theo thời gian kể từ ngày mở** (mục 9) |
| Đơn qua LINE / điện thoại | **Chưa ghi ở đâu** (chủ tiệm xác nhận) | Không đo được web có "lấy khách" của LINE hay không, trừ khi bắt đầu ghi từ bây giờ (mục 9.3, tuỳ chọn) |
| Sổ sách năm trước | **Không có** | Không so cùng kỳ năm trước. Mùa vụ chỉ được nhận diện bằng mốc sự kiện |
| Đơn hàng (`orders.Order`) | Có số điện thoại (chỉ chữ số) trên mọi đơn; không có trường nguồn/kênh | Đếm **khách mua, khách mới, khách quay lại** theo số điện thoại ở máy chủ. Thêm nguồn truy cập vào đơn khi tạo (mục 5.4) |
| Doanh thu online (`reports/services.py`) | Tính từ `Payment` đã xác nhận, theo ngày giờ Bangkok | Là **nguồn sự thật** cho đơn và tiền |
| Lượt bấm hero chiến dịch | Đã đếm ở máy chủ qua `/api/shop/campaign/<id>/go`, không dùng cookie | Giữ nguyên; hiện thêm trong trang mới |
| Bán tại quầy (kho → "ปิดยอดหน้าร้าน") | Nhân viên nhập số đã bán tại quầy theo ngày, chi nhánh | Hiện cạnh số online để thấy xu hướng chung (mục 9.2) |
| Chính sách bảo mật mục 6 | Ghi "chỉ dùng cookie cần thiết", dữ liệu lưu trên máy (giỏ hàng) | Tư vấn pháp lý **yêu cầu hỏi đồng ý** trước khi đo hành vi. Thêm banner đồng ý (mục 7); câu chữ mục 6 phải cập nhật qua pháp lý |
| Quyền `reports.view` | Owner, manager xem doanh thu | Trang mới dùng chung quyền này |
| Lighthouse (phòng thí nghiệm) | LCP mobile 2,9–3,8 s trên máy phát triển, giả lập mạng chậm | Spec này đo tốc độ **trên máy khách thật** (khách đã đồng ý) |

---

## 2. Câu hỏi kinh doanh cần trả lời

| # | Câu hỏi | Chỉ số trả lời | Ai dùng |
|---|---|---|---|
| **B1** | **Lượng khách có tăng không?** (thước đo thành công, mục 9) | Khách mua mỗi tuần/tháng; khách mới; lượt ghé web | Chủ tiệm |
| B2 | Khách có quay lại mua không? | Khách quay lại, số lần mua trung bình mỗi khách | Chủ tiệm |
| B3 | Khách rơi ở bước nào? | Phễu: vào web → xem sản phẩm → thêm giỏ → bắt đầu thanh toán → đặt đơn → đã thanh toán | Chủ tiệm, người làm web |
| B4 | Khách đến từ đâu, kênh nào ra đơn? | Đơn, khách, doanh thu theo nguồn (LINE, Facebook, Google, QR tại quầy, gõ trực tiếp) | Chủ tiệm (đăng bài, in QR) |
| B5 | Sản phẩm nào được xem nhiều nhưng ít người mua? | Lượt xem → thêm giỏ → bán, theo sản phẩm | Chủ tiệm (giá, ảnh, mô tả) |
| B6 | Web có đủ nhanh và ổn định trên điện thoại khách không? | LCP, INP, CLS phân vị 75 (p75) theo thiết bị; tỉ lệ lỗi | Người làm web |
| B7 | Một thay đổi (chiến dịch, khuyến mãi, giao diện) có làm khách tăng không? | Chỉ số quanh **mốc sự kiện**; theo phiên bản giao diện | Chủ tiệm, người làm web |
| B8 | Khách tìm gì mà không thấy? | Từ khóa tìm kiếm không có kết quả | Chủ tiệm (thêm món, đặt tên) |

---

## 3. Nguyên tắc

1. **Khách và tiền lấy từ máy chủ.** Số khách mua, đơn, doanh thu tính từ `Order`/`Payment`, luôn đầy đủ dù khách có đồng ý đo hay không. Đây là các chỉ số chính để đánh giá.
2. **Đo hành vi chỉ khi khách đồng ý.** Trước khi khách bấm "อนุญาต" trên banner, trình duyệt **không gửi gì** và không lưu mã nào ngoài lựa chọn của khách.
3. **Không định danh cá nhân trong dữ liệu hành vi.** Không cookie, không lưu IP, không ghi tên, số điện thoại, địa chỉ, số đơn hay token. Mã khách ghé là số ngẫu nhiên, chỉ tạo sau khi đồng ý.
4. **Không dùng dịch vụ bên thứ ba** (Google Analytics, Facebook Pixel): dữ liệu ở lại máy chủ của tiệm, không thêm script nặng.
5. **Số liệu nhỏ phải hiện số tuyệt đối.** Mọi tỉ lệ hiện kèm số đếm, báo "ít dữ liệu" khi mẫu dưới ngưỡng (mặc định 100 phiên hoặc 30 đơn).
6. **Số đo hành vi là một mẫu, không phải toàn bộ.** Chỉ khách đồng ý mới được đo, nên số phiên luôn thấp hơn thật. Trang báo cáo hiện **tỉ lệ đồng ý** và chỉ dùng số này để xem xu hướng và tỉ lệ, không coi là tổng số khách.
7. **Tăng theo thời gian không phải nhân quả.** Mùa lễ, khuyến mãi, giá đều ảnh hưởng. Trang báo cáo luôn ghi rõ và hiện mốc sự kiện cạnh biểu đồ.
8. **Nhẹ.** Script đo dưới 3 KB, gửi gộp, gửi khi rời trang (`sendBeacon`), không tải khi khách chưa đồng ý.

---

## 4. Định nghĩa chỉ số

### 4.1 Khách (thước đo chính, từ máy chủ)

| Chỉ số | Công thức | Nguồn |
|---|---|---|
| **Khách mua** | Số số điện thoại khác nhau có ≥1 đơn **đã thanh toán** trong kỳ | `Order` + `Payment` |
| **Khách mới** | Khách mua có đơn đã thanh toán **đầu tiên** rơi vào kỳ này | `Order` + `Payment` |
| **Khách quay lại** | Khách mua trong kỳ đã từng có đơn đã thanh toán trước kỳ | `Order` + `Payment` |
| Số lần mua mỗi khách | Đơn đã thanh toán / khách mua | `Order` + `Payment` |
| Đơn, doanh thu, AOV | Như báo cáo ภาพรวม (chỉ đơn đã thanh toán, không bị huỷ) | `Payment` |
| Tỉ lệ thanh toán xong | Đơn đã xác nhận thanh toán / đơn đã tạo | `Order` + `Payment` |
| Đơn hủy vì quá hạn | Đơn bị scheduler hủy do không thanh toán / đơn tạo | `Order` |

Số điện thoại chỉ dùng để **đếm** ở máy chủ. Báo cáo không hiện số điện thoại, chỉ hiện con số tổng.

### 4.2 Lượt ghé web (từ máy chủ, không định danh)

| Chỉ số | Công thức | Nguồn |
|---|---|---|
| **Lượt xem trang** | Số lần máy chủ shop trả về một trang cho trình duyệt thật (bỏ bot), cộng dồn theo ngày × loại trang (trang chủ, danh sách, chi tiết, giỏ, thanh toán) | Máy chủ shop |

Đếm không cần đồng ý vì không đọc hay ghi gì trên máy khách và không lưu dữ liệu cá nhân, chỉ cộng một con số. **Cần pháp lý xác nhận** (Q9). Đây là chỉ số "khách ghé" đầy đủ nhất có thể có khi không dùng cookie.

### 4.3 Hành vi (từ trình duyệt, chỉ khách đồng ý)

| Chỉ số | Công thức |
|---|---|
| Khách ghé (đã đồng ý) | Số mã khách ghé khác nhau trong kỳ |
| Phiên | Chuỗi lượt xem của một mã khách ghé, cách nhau dưới 30 phút |
| Tỉ lệ xem sản phẩm, thêm giỏ, bắt đầu thanh toán | Phiên có bước đó / phiên |
| Tỉ lệ chuyển đổi | Đơn có mã khách ghé / phiên (chỉ trong nhóm đã đồng ý) |
| Tỉ lệ bỏ giỏ | 1 − (phiên đặt đơn / phiên thêm giỏ) |
| **Tỉ lệ đồng ý** | Số lần bấm "อนุญาต" / số lần banner được trả lời (cả hai nút). Đếm ở máy chủ, không định danh |
| LCP, INP, CLS | Phân vị 75, tách điện thoại/máy tính. Ngưỡng tốt: LCP ≤ 2,5 s, INP ≤ 200 ms, CLS ≤ 0,1 |
| Tỉ lệ lỗi | Phiên có lỗi JavaScript / phiên (giai đoạn 3) |

Một ngày, một tuần (thứ Hai đến Chủ nhật) tính theo giờ Bangkok.

---

## 5. Thu thập dữ liệu

### 5.1 Banner đồng ý

- Hiện ở đáy màn hình lần đầu khách vào shop, **không che** nút đặt hàng hay thanh mua dính đáy (thanh mua đẩy lên trên banner).
- Hai nút **ngang hàng, cùng cỡ**: "อนุญาต" và "ไม่อนุญาต", cùng link tới chính sách bảo mật. Không đặt sẵn lựa chọn, không làm nút từ chối mờ hơn.
- Lựa chọn lưu trong `localStorage` (chỉ để nhớ lựa chọn, thuộc loại cần thiết). Hỏi lại khi phiên bản chính sách thay đổi.
- Trang chính sách có mục đổi lựa chọn bất kỳ lúc nào. Rút lại đồng ý thì xóa mã khách ghé khỏi máy và ngừng gửi ngay.
- Trình duyệt bật Do Not Track hoặc Global Privacy Control: coi như "ไม่อนุญาต", không hiện banner.
- **Câu chữ banner do chủ tiệm và tư vấn pháp lý duyệt.** Người làm web chỉ để khung và chỗ trống `[ระบุ]`.

### 5.2 Sự kiện phía khách (chỉ sau khi đồng ý)

| Sự kiện | Khi nào | Dữ liệu riêng |
|---|---|---|
| `page_view` | Mỗi lần đổi trang | Đường dẫn **đã chuẩn hóa**: bỏ toàn bộ query; `/orders/MH-…` thành `/orders/:number` |
| `product_view` | Mở trang chi tiết sản phẩm | `slug` |
| `add_to_cart` | Bấm "เพิ่มลงตะกร้า" thành công | `slug`, cỡ, số lượng, giá trị (satang, chỉ để tham khảo) |
| `cart_view` | Mở trang giỏ hàng | Số món, giá trị |
| `checkout_start` | Mở trang thanh toán khi giỏ có hàng | Số món, giá trị |
| `search` | Tìm kiếm trên trang danh sách | Từ khóa (tối đa 40 ký tự, chữ thường), số kết quả |
| `web_vital` | Trình duyệt báo LCP, INP, CLS, FCP, TTFB | Tên chỉ số, giá trị, xếp loại, loại trang |
| `js_error` | Lỗi JavaScript chưa bắt (giai đoạn 3) | Thông điệp đã cắt ngắn, trang |

**Thuộc tính chung:** thời điểm, mã khách ghé (ngẫu nhiên, trong `localStorage`, chỉ tạo sau khi đồng ý), thiết bị (điện thoại/tablet/máy tính theo bề rộng màn hình), nguồn (mục 5.3), phiên bản giao diện (`design_version`, ví dụ `2026-10-redesign`).

**Không gửi:** tên, số điện thoại, địa chỉ, ghi chú, mã giảm giá đã nhập, số đơn, token, nội dung ô nhập, URL có query, IP (máy chủ chỉ dùng IP tạm thời để giới hạn tần suất, không lưu).

### 5.3 Nguồn truy cập

Xác định khi khách vào trang đầu tiên, theo thứ tự:

1. `utm_source` trên link (ví dụ bài Facebook, QR in tại quầy `?utm_source=qr_srinarong`). Chỉ nhận chữ, số, `_`, `-`, tối đa 40 ký tự.
2. Trang giới thiệu (referrer), chỉ giữ **nhóm**: `line`, `facebook`, `google`, `tiktok`, `instagram`, `other`. Không lưu URL đầy đủ.
3. Không có gì: `direct`.

Nguồn được dùng ở **hai nơi**: gắn vào sự kiện hành vi (chỉ khi đồng ý), và gắn vào **đơn hàng** (mục 5.4). Nguồn trên đơn chỉ là một nhóm như `facebook`, không phải dữ liệu cá nhân, nên gắn được cả khi khách không đồng ý đo (Q9).

**Đề xuất cho tiệm:** in QR cho từng chi nhánh với `utm_source` riêng, và dùng link có `utm_source=line_oa` trong tin nhắn LINE OA. Nếu không, nhiều lượt từ LINE sẽ hiện là `direct`.

### 5.4 Ghép với đơn (phía máy chủ)

- Khi tạo đơn, shop gửi kèm **nguồn** (luôn có) và **mã khách ghé** (chỉ khi đã đồng ý), hai trường tuỳ chọn trong body `POST /api/orders`.
- Máy chủ lưu vào đơn (`traffic_source`, `visitor_ref`). Từ đó tính đơn, khách mua và doanh thu **theo nguồn** cho **mọi** đơn, và tỉ lệ chuyển đổi trong nhóm đã đồng ý.

### 5.5 Nhận sự kiện và đếm lượt (máy chủ)

- `POST /api/analytics/events`: công khai, nhận lô tối đa 20 sự kiện, kiểu `text/plain` hoặc JSON (để `sendBeacon` gửi không cần preflight CORS). Kiểm tra trường theo danh sách cho phép; trường lạ bị bỏ. Lô sai trả 204 nhưng không ghi.
- `POST /api/analytics/consent`: ghi **một con số** cho mỗi câu trả lời banner (`allow` / `deny`) theo ngày, không mã, không IP. Dùng tính tỉ lệ đồng ý.
- Lượt xem trang (mục 4.2): máy chủ shop cộng dồn theo ngày × loại trang khi render trang cho trình duyệt thật, bỏ bot theo User-Agent và các yêu cầu prefetch.
- Giới hạn tần suất theo IP bằng `core.ratelimit` (chính sách mới `analytics`, ví dụ 120 lô/phút). Tối đa 300 sự kiện mỗi mã khách ghé mỗi ngày.
- Ghi thô, không chạy truy vấn nặng trong request.

---

## 6. Lưu trữ

| Bảng | Nội dung | Giữ bao lâu |
|---|---|---|
| `WebEvent` | Sự kiện thô (mục 5.2) | **180 ngày**, rồi xóa (`prune_web_events`, chạy trong `scheduler` mỗi đêm) |
| `WebPageCount` | Ngày × loại trang → số lượt xem (mục 4.2) | Lâu dài |
| `ConsentCount` | Ngày × lựa chọn → số lần | Lâu dài |
| `WebDailyStat` | Ngày × thiết bị × nguồn × phiên bản giao diện: khách ghé, phiên, xem SP, thêm giỏ, bắt đầu thanh toán, p75 LCP/INP/CLS | Lâu dài (số tổng, không có mã) |
| `WebProductDailyStat` | Ngày × sản phẩm: lượt xem, lượt thêm giỏ | Lâu dài |
| `Order` (thêm trường) | `traffic_source` (40 ký tự), `visitor_ref` (32 ký tự, rỗng được) | Theo đơn |
| `Milestone` | Mốc sự kiện: ngày, tên, loại (`release`, `campaign`, `promotion`, `other`) | Lâu dài |
| `SalesChannelEntry` (tuỳ chọn, mục 9.3) | Nhập tay: ngày, kênh (`line`, `phone`), số đơn | Lâu dài |

Số khách mua, khách mới, khách quay lại **không cần bảng mới**: tính trực tiếp từ `Order`/`Payment`, và tính được cho cả các đơn có trước khi tính năng này chạy.

Tổng hợp chạy mỗi đêm cho ngày hôm trước, chạy lại được cho một khoảng ngày (`rollup_web_stats --from --to`). Trang báo cáo đọc bảng tổng hợp; riêng "hôm nay" tính trực tiếp.

---

## 7. Quyền riêng tư (PDPA)

- Theo ý kiến tư vấn pháp lý: **phải hỏi đồng ý** trước khi đo hành vi trên trình duyệt. Banner ở mục 5.1.
- Không đồng ý thì không có gì gửi từ trình duyệt; khách vẫn mua bình thường, không bị hạn chế chức năng.
- Trang chính sách cần cập nhật mục 6: tiệm thu thống kê về cách dùng web và tốc độ tải khi khách đồng ý, không gắn với cá nhân, giữ dữ liệu thô 180 ngày, cách đổi lựa chọn; và tiệm dùng dữ liệu đơn (số điện thoại) để **đếm** số khách mua, khách quay lại. **Câu chữ do chủ tiệm và tư vấn pháp lý duyệt**.
- Cần pháp lý xác nhận hai việc không qua banner (Q9): đếm lượt xem trang ở máy chủ (mục 4.2) và gắn nhóm nguồn vào đơn (mục 5.3). Nếu không được, hai việc này cũng chỉ làm khi khách đồng ý.

---

## 8. Trang quản trị: "สถิติเว็บ"

Mục mới trong menu nhóm **หน้าร้าน**, quyền `reports.view`. Bố cục từ trên xuống (điện thoại: cùng thứ tự, một cột):

1. **Thanh chọn kỳ:** theo tuần / theo tháng, 4 / 12 / 26 tuần hoặc tự chọn; so với kỳ trước cùng độ dài. Lọc theo nguồn.
2. **Khối "ลูกค้า" (đầu trang, thước đo chính):** khách mua, khách mới, khách quay lại, lượt xem trang. Mỗi ô có số kỳ trước, mũi tên tăng/giảm, và đường xu hướng.
3. **Biểu đồ theo tuần:** khách mua (cột chia khách mới / quay lại) và lượt xem trang (đường), có **trung bình trượt 4 tuần** để bớt dao động, và **mốc sự kiện** (ngày mở web, chiến dịch lấy tự động từ `cms`, khuyến mãi, mốc nhập tay).
4. **Đơn và tiền:** đơn, doanh thu, AOV, tỉ lệ thanh toán xong, đơn hủy vì quá hạn.
5. **Nguồn:** khách mua, đơn, doanh thu theo nguồn (mọi đơn); kèm phiên và tỉ lệ chuyển đổi trong nhóm đã đồng ý.
6. **Phễu** (nhóm đã đồng ý): 6 bước, số phiên, % so với bước đầu, % rơi so với bước trước. Bước rơi nhiều nhất được tô nổi kèm gợi ý chỗ cần xem.
7. **Sản phẩm:** xem → thêm giỏ → bán; sắp theo "xem nhiều mua ít".
8. **Tìm kiếm không có kết quả:** 20 từ khóa nhiều nhất.
9. **Tốc độ trên máy khách:** p75 LCP, INP, CLS theo thiết bị, màu theo ngưỡng, số lượt đo.
10. **Bán tại quầy** (từ "ปิดยอดหน้าร้าน"): số món theo tuần, để đặt cạnh xu hướng online.

Cuối trang luôn có dòng giải thích bằng tiếng Thái: khách và tiền tính từ đơn ở máy chủ và đầy đủ; số phiên chỉ gồm khách đồng ý (kèm tỉ lệ đồng ý hiện tại); tăng/giảm không chứng minh nguyên nhân.

---

## 9. Đánh giá "lượng khách có tăng không"

### 9.1 Thước đo thành công

Chủ tiệm đánh giá thành công bằng **lượng khách tăng**. Spec định nghĩa cụ thể:

| Thước đo | Định nghĩa | Vì sao |
|---|---|---|
| **Chính: khách mua mỗi tuần** | Mục 4.1, xu hướng trung bình trượt 4 tuần | Đếm người thật có trả tiền, đầy đủ, không phụ thuộc banner |
| Phụ: khách mới mỗi tuần | Mục 4.1 | Web có kéo thêm người chưa từng mua online |
| Phụ: khách quay lại | Mục 4.1 | Khách có giữ lại được |
| Phụ: lượt xem trang mỗi tuần | Mục 4.2 | Có thêm người biết và ghé web (dấu hiệu sớm, trước khi thành đơn) |

**Đọc kết quả:** "tăng" khi trung bình 4 tuần gần nhất cao hơn trung bình 4 tuần trước đó. Trang hiện mức tăng % và số tuyệt đối. Chưa đặt con số mục tiêu (chủ tiệm chưa xác định); sau 3 tháng có dữ liệu, xem lại để đặt mục tiêu cho quý sau. Khung nhập mục tiêu để sẵn ở giai đoạn 3.

### 9.2 Giới hạn cần nói rõ

- **Không có số liệu trước khi có web** (không ghi đơn LINE/điện thoại, không có sổ năm trước). Vì vậy báo cáo trả lời được "lượng khách **trên web** có tăng dần không", nhưng **không** trả lời được "tổng khách của tiệm có nhiều hơn trước khi có web không".
- Vài tuần đầu sau khi mở, số khách tăng gần như chắc chắn (từ 0 lên). Nên đọc xu hướng **từ tuần thứ 5 trở đi**, sau khi khách quen đã biết web.
- Mùa lễ và khuyến mãi làm số nhảy; đối chiếu với mốc sự kiện trước khi kết luận.

### 9.3 Tuỳ chọn: ghi đơn LINE và điện thoại từ bây giờ

Nếu tiệm muốn biết web có **thêm** khách hay chỉ **chuyển** khách từ LINE sang, cần bắt đầu ghi số đơn LINE và điện thoại mỗi ngày từ bây giờ (form "ยอดช่องทางอื่น", giai đoạn 3). Không bắt buộc. Không ghi thì phần này để trống, các phần khác không bị ảnh hưởng.

| Kết quả sau vài tháng | Ý nghĩa |
|---|---|
| Khách web tăng, đơn LINE/điện thoại giữ nguyên | Web **mang thêm khách** |
| Khách web tăng, đơn LINE/điện thoại giảm tương ứng | Web **chuyển kênh**: chưa thêm khách, nhưng giảm việc trả lời tin nhắn |

### 9.4 So sánh giao diện về sau

- Mọi sự kiện mang `design_version`. Khi đổi giao diện, tăng phiên bản; trang thống kê lọc được theo phiên bản.
- Thử A/B (chia ngẫu nhiên khách giữa hai giao diện) để giai đoạn 4, chỉ làm khi lượng khách đủ lớn.

---

## 10. API

| Phương thức | Đường dẫn | Quyền | Ghi chú |
|---|---|---|---|
| POST | `/api/analytics/events` | Công khai, giới hạn tần suất | Mục 5.5, chỉ sau khi đồng ý |
| POST | `/api/analytics/consent` | Công khai, giới hạn tần suất | Đếm câu trả lời banner |
| POST | `/api/orders` (đổi) | Như cũ | Thêm `traffic_source`, `visitor_ref` tuỳ chọn |
| GET | `/api/admin/analytics/customers?period=week&weeks=` | `reports.view` | Khối "ลูกค้า", biểu đồ theo tuần |
| GET | `/api/admin/analytics/summary?from=&to=&source=` | `reports.view` | Đơn, tiền, phễu, tỉ lệ đồng ý |
| GET | `/api/admin/analytics/sources`, `/products`, `/searches`, `/vitals`, `/storefront` | `reports.view` | Các bảng mục 8 |
| GET/POST/DELETE | `/api/admin/analytics/milestones` | `reports.view` | Mốc nhập tay; mốc chiến dịch lấy tự động |
| GET/POST/PUT/DELETE | `/api/admin/analytics/channel-entries` | `reports.view` xem; `orders.view` nhập | Tuỳ chọn, mục 9.3 |

---

## 11. Giai đoạn triển khai

Web mở trong tháng 10/2026. Phần đếm khách từ đơn không phụ thuộc thời điểm (tính lại được từ đơn cũ), nhưng **nguồn trên đơn và banner phải có trước ngày mở** thì mới không mất số liệu những tuần đầu.

| Giai đoạn | Nội dung | Kết quả kiểm tra |
|---|---|---|
| **1. Trước ngày mở** | Banner đồng ý (khung, chờ câu chữ pháp lý), nguồn truy cập gắn vào đơn, đếm lượt xem trang ở máy chủ, đếm câu trả lời banner, script sự kiện chỉ chạy sau khi đồng ý, endpoint nhận, xóa sau 180 ngày | Test: không đồng ý thì không có request đo nào; DNT/GPC; đơn có nguồn; lọc bot; không lưu IP; không có tên/SĐT/token trong bảng sự kiện. E2e: từ chối → mua được, không có sự kiện; đồng ý → có sự kiện, đơn mang mã |
| **2. Báo cáo khách** (trong 2 tuần sau khi mở) | Trang "สถิติเว็บ" mục 1–5 và 10: khách mua/mới/quay lại theo tuần, lượt xem trang, đơn và tiền, nguồn, mốc chiến dịch tự động | Test số liệu khách mới/quay lại trên dữ liệu mẫu (cùng SĐT nhiều đơn, đơn huỷ, đơn chưa trả) |
| **3. Hành vi và chất lượng** | Phễu, sản phẩm, tìm kiếm, tốc độ, `js_error`, mốc nhập tay, khung đặt mục tiêu, form "ยอดช่องทางอื่น" (tuỳ chọn) | Test p75, phễu; xem trên điện thoại |
| **4. Mở rộng (khi cần)** | Xuất CSV, A/B giao diện, báo LINE cho chủ tiệm khi khách mua tuần giảm mạnh | Theo từng mục |

---

## 12. Rủi ro

| Rủi ro | Cách giảm |
|---|---|
| Ít khách bấm "อนุญาต", số hành vi quá ít | Thước đo chính (khách mua) không phụ thuộc banner; hiện tỉ lệ đồng ý; chỉ dùng hành vi để xem tỉ lệ và xu hướng |
| Banner làm khách khó chịu hoặc che nút mua | Banner nhỏ ở đáy, trả lời một lần, không che thanh mua; kiểm tra trên điện thoại |
| Một khách dùng nhiều số điện thoại, hoặc nhiều người chung một số | Chấp nhận sai số nhỏ; ghi chú trong trang báo cáo |
| Vài tuần đầu "tăng" chỉ vì từ 0 lên | Đọc xu hướng từ tuần thứ 5, dùng trung bình trượt 4 tuần |
| Trình chặn quảng cáo chặn script | Khách và tiền vẫn đúng vì tính ở máy chủ; gửi về tên miền của tiệm |
| Bot làm phồng lượt xem trang | Lọc User-Agent, bỏ prefetch, giới hạn tần suất |
| Mùa lễ, khuyến mãi làm sai đánh giá | Mốc sự kiện tự động và nhập tay |
| Thu thập vượt quá điều chính sách cho phép | Danh sách trường cho phép ở máy chủ; test không có dữ liệu cá nhân; pháp lý duyệt câu chữ (mục 7) |

---

## 13. Câu trả lời của chủ tiệm (19/10/2026)

| Câu hỏi | Trả lời | Ảnh hưởng tới kế hoạch |
|---|---|---|
| Q1. Ngày mở web | Xem như mở trong tháng này (10/2026) | Không ghi được baseline trước khi mở. Giai đoạn 1 phải có trước ngày mở (mục 11) |
| Q2. Đơn LINE, điện thoại ghi ở đâu | Chưa ghi | Không so được tổng khách trước/sau. Ghi từ bây giờ là tuỳ chọn (mục 9.3) |
| Q3. Thế nào là thành công | Chưa xác định; dựa vào **lượng khách tăng** | Thước đo chính là **khách mua mỗi tuần**, kèm khách mới, quay lại, lượt xem trang (mục 9.1). Chưa đặt con số mục tiêu |
| Q4. Sổ sách cùng kỳ năm trước | Không có | Bỏ so sánh cùng kỳ năm trước |
| Q7. Không cần banner đồng ý? | **Không**: phải hỏi đồng ý | Thêm banner (mục 5.1); đo hành vi chỉ khi đồng ý; khách và tiền lấy từ máy chủ (mục 3) |

### Còn mở

| # | Câu hỏi | Vì sao cần |
|---|---|---|
| Q5 | Có muốn đo số tin nhắn hỏi hàng trên LINE OA (từ thống kê của LINE) không? | Đo lợi ích "giảm việc trả lời tin nhắn" khi khách tự đặt trên web |
| Q6 | Ước lượng số khách ghé web mỗi tháng? | Quyết định có làm A/B hay không |
| Q8 | In QR riêng cho từng chi nhánh và dùng link có `utm_source` trong LINE OA được không? | Đo đúng nguồn khách (mục 5.3) |
| Q9 | Pháp lý có cho phép đếm lượt xem trang ở máy chủ (chỉ một con số, không định danh) và gắn nhóm nguồn vào đơn khi khách **không** đồng ý không? | Nếu không, lượt xem trang và nguồn trên đơn chỉ có ở nhóm đã đồng ý, thước đo phụ "lượt xem trang" kém đầy đủ |
| Q10 | Câu chữ banner và đoạn bổ sung mục 6 chính sách bảo mật | Pháp lý duyệt trước ngày mở |

---

## 14. Không làm trong phạm vi này

- Google Analytics, Facebook Pixel hay công cụ bên thứ ba khác.
- Ghi màn hình (session recording), bản đồ nhiệt (heatmap).
- Hồ sơ từng khách, quảng cáo bám đuổi, hiện số điện thoại khách trong báo cáo thống kê.
- Đo hành vi trong trang quản trị.
- So sánh với thời gian trước khi có web (không có dữ liệu, mục 9.2).
- Tự kết luận nguyên nhân (máy học, mô hình thống kê). Báo cáo đưa số liệu và mốc, người đọc quyết định.
