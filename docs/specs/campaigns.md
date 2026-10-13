# Spec: Chiến dịch theo dịp lễ (แคมเปญ / เทศกาล)

Trạng thái: **kế hoạch, chưa triển khai**. Cập nhật: 13/10/2026 (đã có câu trả lời của chủ tiệm, xem mục 13).

Mục tiêu: vào các dịp lễ trong năm, nhân viên tự đổi giao diện hiển thị cho khách ở trang chủ (màu, banner, video, thanh thông báo, nhóm sản phẩm nổi bật) từ trang quản trị, **đặt lịch trước**, tự bật và tự tắt đúng giờ, không cần sửa code hay deploy lại.

Khác với **khuyến mãi** (`product-management.md`) và **mã giảm giá** (`coupons.md`): chiến dịch không tự giảm giá. Chiến dịch là "lớp trình bày" theo dịp lễ, và **có thể gắn** khuyến mãi hoặc mã giảm giá đã có để hiển thị cùng.

---

## 1. Hiện trạng liên quan

| Chỗ | Hiện trạng | Ảnh hưởng tới kế hoạch |
|---|---|---|
| Menu "รายงานโปรโมชัน" → `/campaigns` | Trang báo cáo hiệu quả khuyến mãi và mã (`Campaigns.tsx`, quyền `reports.view`) | Trang `/campaigns` sẽ thành trang **แคมเปญ** có nhiều tab. Báo cáo hiện tại chuyển vào tab "รายงาน" của trang này, không mất chức năng |
| App `maehai.cms` | Đã đăng ký trong settings nhưng **chưa có model** | Đặt model chiến dịch ở đây |
| Trang chủ shop (`apps/shop/src/app/page.tsx`) | Hero, nhóm "รสยอดนิยม" và nội dung khác viết cứng trong code. `force-dynamic` (render mỗi request) | Hero và thanh thông báo lấy từ API chiến dịch; nội dung mặc định giữ nguyên khi không có chiến dịch |
| Ảnh sản phẩm | Kiểm tra bằng Pillow, tối đa 5 MB (`IMAGE_MAX_MB`), lưu `MEDIA_ROOT/products` hoặc S3 | Ảnh chiến dịch dùng lại cách kiểm tra này, lưu dưới `media/campaigns/` |
| Caddy (`deploy/Caddyfile`) | Chỉ phục vụ `/media/products/*`; API giới hạn body **8 MB** | Phải mở thêm `/media/campaigns/*`; upload video cần một route riêng có giới hạn lớn hơn |
| Quyền | Có vai trò `content` (พนักงานดูแลสินค้า) | Cho vai trò này soạn chiến dịch, nhưng chỉ owner/manager được **phát hành** |

---

## 2. Khái niệm

**Chiến dịch** = một gói trình bày cho một dịp, có thời gian bắt đầu và kết thúc. Một chiến dịch gồm:

1. **Giao diện (theme)**: chọn một mẫu dịp lễ có sẵn, chỉnh màu nhấn trong giới hạn an toàn.
2. **Hero**: ảnh hoặc video lớn ở đầu trang chủ, kèm tiêu đề, mô tả ngắn và nút kêu gọi.
3. **Thanh thông báo**: một dòng chữ trên cùng mọi trang shop (ví dụ "สั่งก่อน 10 เม.ย. ส่งทันสงกรานต์"), có link tuỳ chọn.
4. **Nhóm sản phẩm của dịp**: tên nhóm + danh sách sản phẩm chọn tay, hiện ở trang chủ thay cho hoặc trên nhóm "รสยอดนิยม".
5. **Khuyến mãi / mã đi kèm** (tuỳ chọn): gắn khuyến mãi hoặc mã đã có, để banner hiển thị đúng điều kiện. Chiến dịch **không** tạo giảm giá riêng.
6. **Hiệu ứng trang trí** (tuỳ chọn, mặc định tắt): hoạ tiết viền nhẹ theo mẫu (đèn lồng, hoa, nến...). Không có hiệu ứng rơi hay chuyển động liên tục.

Tại một thời điểm, khách chỉ thấy **tối đa một** chiến dịch. Khi không có chiến dịch nào đang chạy, shop hiện giao diện mặc định như hiện nay.

---

## 3. Giao diện theo dịp (theme)

### 3.1 Vì sao dùng mẫu có sẵn thay cho chỉnh CSS tự do

- Màu thương hiệu, độ tương phản chữ và bố cục điện thoại đã được kiểm tra; CSS tự do dễ làm vỡ trang thanh toán hoặc làm chữ khó đọc.
- Mẫu chỉ đổi một nhóm **token** nhỏ (màu nhấn, nền hero, hoạ tiết). Trang giỏ hàng, thanh toán, PromptPay **không đổi màu**, để khách không nghi ngờ khi trả tiền.

### 3.2 Mẫu đề xuất ban đầu

| Mẫu | Dịp gợi ý | Màu nhấn | Trang trí |
|---|---|---|---|
| `default` | Ngày thường | Xanh lá thương hiệu | Không |
| `new_year` | ปีใหม่ | Vàng ánh kim + xanh đậm | Hoạ tiết pháo hoa nét mảnh |
| `chinese_new_year` | ตรุษจีน | Đỏ + vàng | Đèn lồng ở góc hero |
| `songkran` | สงกรานต์ | Xanh nước + trắng | Hoạ tiết hoa, giọt nước |
| `candle_festival` | แห่เทียนพรรษา (อุบลฯ) | Cam đất + vàng sáp | Hoạ tiết nến chạm |
| `mothers_day` | วันแม่ | Xanh dương nhạt | Hoa มะลิ |
| `vegetarian` | เทศกาลกินเจ | Vàng + đỏ | Cờ เจ |
| `loy_krathong` | ลอยกระทง | Xanh đêm + vàng | Hoạ tiết กระทง |

**Lễ hội nến Ubon (แห่เทียนพรรษา) là dịp đầu tiên chủ tiệm cần**, nên mẫu `candle_festival` làm đầu tiên, ngay giai đoạn 1.

### 3.3 Chỉnh màu trong giới hạn

- Nhân viên có thể đổi **màu nhấn** của mẫu. Hệ thống kiểm tra độ tương phản với chữ trắng và chữ đậm (tối thiểu 4.5:1 cho chữ thường). Không đạt thì báo lỗi bằng tiếng Thái và không cho lưu.
- Không cho đổi phông, cỡ chữ, khoảng cách.

---

## 4. Ảnh động (GIF) và video

Hero của chiến dịch **không bắt buộc** có chuyển động. Nhân viên chọn một trong: dùng hero mặc định, **ảnh tĩnh**, **ảnh động GIF**, hoặc **video**.

### 4.0 Ảnh động GIF

| Mục | Quy tắc |
|---|---|
| Định dạng | GIF (kiểm tra bằng Pillow như ảnh sản phẩm), cũng nhận WebP động |
| Dung lượng | Tối đa **8 MB** (biến môi trường `ANIMATION_MAX_MB`). GIF nặng hơn video nhiều lần cho cùng độ dài, nên form gợi ý dùng video nếu file lớn |
| Ảnh poster | **Tự tạo** từ khung hình đầu bằng Pillow, nhân viên không cần tải riêng (có thể thay bằng ảnh khác) |
| Phát | Tự chạy. Khi khách bật "giảm chuyển động" hoặc tiết kiệm dữ liệu thì hiện ảnh poster. Có nút tạm dừng (đổi sang ảnh poster) |

GIF dùng chung đường xử lý với ảnh, nên làm được ngay giai đoạn 1; video cần thêm route upload riêng nên để giai đoạn 2.

### 4.1 Hai nguồn video

| Nguồn | Ưu điểm | Nhược điểm |
|---|---|---|
| **Tải file MP4 lên** | Tự chủ, phát tự động không âm thanh, không quảng cáo | Tốn dung lượng máy chủ và băng thông |
| **Link YouTube** | Không tốn băng thông máy chủ | Có logo YouTube, chậm hơn, dính cookie bên thứ ba |

Đề xuất: làm **tải MP4** trước cho hero; link YouTube để giai đoạn sau, chỉ dùng trong phần nội dung bên dưới hero.

### 4.2 Quy tắc file tải lên

| Mục | Quy tắc |
|---|---|
| Định dạng | MP4 (H.264 + AAC) hoặc WebM. Kiểm tra bằng "magic bytes", không tin đuôi file |
| Dung lượng | Tối đa **25 MB** (biến môi trường `VIDEO_MAX_MB`) |
| Thời lượng khuyến nghị | 6 đến 30 giây, lặp lại |
| Ảnh poster | **Bắt buộc**. Hiện khi video chưa tải xong, khi khách bật "giảm chuyển động", hoặc khi dùng chế độ tiết kiệm dữ liệu |
| Phát | Tự động, **tắt tiếng**, lặp, `playsinline`. Có nút tạm dừng cho người khuyết tật |
| Trên điện thoại | Cho phép tải video riêng cho điện thoại (dọc, nhẹ hơn). Không có thì dùng ảnh poster thay video |

### 4.3 Hạ tầng cần đổi

- Caddy: thêm route phục vụ `/media/campaigns/*`; thêm route upload video riêng với `max_size` 30 MB, chỉ cho người đã đăng nhập quản trị (API đã kiểm tra quyền).
- Header `Cache-Control` dài hạn cho file media; tên file có mã băm nên đổi file là đổi URL.
- Lưu trữ theo cấu hình hiện có, giống ảnh sản phẩm: `STORAGE_BACKEND=local` thì ở `MEDIA_ROOT/campaigns/`, `STORAGE_BACKEND=s3` thì ở bucket ảnh sản phẩm, prefix `campaigns/`. Không thêm cấu hình lưu trữ riêng cho chiến dịch.
- Chưa nén lại video trên máy chủ (cần ffmpeg). Giai đoạn đầu chỉ kiểm tra định dạng và dung lượng; hướng dẫn nhân viên xuất video đúng chuẩn.

---

## 5. Lịch và trạng thái

| Trạng thái | Ý nghĩa |
|---|---|
| `draft` (ร่าง) | Đang soạn, khách không thấy |
| `scheduled` (ตั้งเวลาแล้ว) | Đã phát hành, chờ tới giờ bắt đầu |
| `live` (กำลังแสดง) | Đang hiện cho khách |
| `ended` (จบแล้ว) | Hết giờ, hoặc bị kết thúc sớm |

Quy tắc:

1. Thời gian theo `Asia/Bangkok`. Bắt đầu bắt buộc, kết thúc bắt buộc (tránh chiến dịch chạy mãi).
2. Trạng thái `live`/`ended` **tính theo giờ hiện tại**, không cần job chạy định kỳ.
3. Hai chiến dịch đã phát hành **không được chồng giờ**. Lưu sẽ báo trùng với chiến dịch nào.
4. Có nút "จบก่อนกำหนด" (đặt giờ kết thúc = bây giờ) và "เลื่อน".
5. Sửa chiến dịch đang chạy: lưu là khách thấy ngay; có xác nhận trước khi lưu.
6. Có nút **"ทำซ้ำ"**: chép chiến dịch năm trước sang năm nay, chỉ cần chỉnh ngày.

---

## 6. Xem trước

- Nút "ดูตัวอย่าง" mở trang chủ shop với chiến dịch đang soạn, kể cả khi chưa tới giờ.
- Cách làm: API cấp một **mã xem trước** ngắn hạn (30 phút, ký bằng `SECRET_KEY`); shop nhận `?preview=<mã>` và gọi API lấy đúng chiến dịch đó. Có dải chữ "โหมดตัวอย่าง" để không nhầm với trang thật.
- Xem trước cả khổ máy tính và điện thoại (mở tab mới, hoặc khung điện thoại trong trang quản trị).

---

## 7. Trang quản trị: "แคมเปญ"

Menu: đổi mục "รายงานโปรโมชัน" thành **"แคมเปญ"** (vẫn đường dẫn `/campaigns`). Trang có các tab:

| Tab | Nội dung |
|---|---|
| **แคมเปญ** | Danh sách: tên, mẫu, thời gian, trạng thái. Lọc theo trạng thái. Nút "สร้างแคมเปญ" |
| **ปฏิทิน** | Dòng thời gian 12 tháng, thấy khoảng trống và chỗ trùng. Có gợi ý các dịp lễ trong năm |
| **รายงาน** | Báo cáo khuyến mãi và mã hiện có (chuyển từ trang cũ), thêm số liệu theo từng chiến dịch |

Trang soạn chiến dịch (cùng kiểu trang sửa sản phẩm, có mục bên trái và thanh lưu dưới cùng):

1. ข้อมูลหลัก: tên (nội bộ), thời gian.
2. หน้าตา: chọn mẫu (ô xem thử nhỏ), màu nhấn, bật/tắt trang trí.
3. ส่วนหัว (hero): ảnh hoặc video, poster, tiêu đề, mô tả, nút (chữ + link).
4. แถบประกาศ: chữ, link, bật/tắt.
5. สินค้าของเทศกาล: tên nhóm, chọn sản phẩm, sắp thứ tự.
6. โปรโมชันที่เกี่ยวข้อง: chọn khuyến mãi / mã đã có (chỉ hiển thị).
7. Thanh dưới: "บันทึกร่าง", "ดูตัวอย่าง", "เผยแพร่" (theo quyền).

---

## 8. Quyền

| Quyền mới | Ai có | Làm được |
|---|---|---|
| `campaigns.edit` | owner, manager, sales | Tạo, sửa **bản nháp**, tải ảnh/GIF/video, xem trước |
| `campaigns.publish` | owner, manager, sales | Phát hành, sửa chiến dịch đang chạy, kết thúc sớm, xoá |

Theo trả lời của chủ tiệm: quản lý (manager) hoặc nhân viên bán hàng (sales) tự làm và tự phát hành chiến dịch, không cần bước duyệt riêng. Vai trò `content` không có quyền chiến dịch. Vẫn tách hai quyền để sau này muốn thêm bước duyệt chỉ cần đổi bảng vai trò.

Báo cáo vẫn theo `reports.view`. Mọi thao tác phát hành / sửa / kết thúc ghi vào nhật ký (audit log) như các mục khác.

---

## 9. Phía khách (shop)

- API công khai `GET /api/shop/campaign/current` trả chiến dịch đang chạy (hoặc rỗng). Shop gọi mỗi lần render trang; API đặt cache ngắn (60 giây) để chịu tải.
- `layout.tsx` của shop thêm thanh thông báo và lớp CSS của mẫu (`data-theme="songkran"`). Token màu chỉ áp dụng trong khu vực trang chủ, danh sách và chi tiết sản phẩm; **không** áp cho giỏ hàng, thanh toán, theo dõi đơn.
- Hero: dùng ảnh, GIF hoặc video của chiến dịch nếu có, không thì hero mặc định hiện tại.
- Chiến dịch **chỉ đổi trang chủ** (hero, nhóm sản phẩm) cùng thanh thông báo và màu nhấn. Trang chi tiết sản phẩm **không** có banner chiến dịch (chủ tiệm không cần).
- Ảnh/video có `alt`/mô tả bắt buộc bằng tiếng Thái.
- Khi API chiến dịch lỗi: shop hiện giao diện mặc định, không lỗi trang.

---

## 10. Dữ liệu (app `cms`)

```text
Campaign
  name, slug
  theme            (choice: default, new_year, ...)
  accent_color     (hex, nullable = theo mẫu)
  decorations      (bool)
  starts_at, ends_at
  published_at     (null = bản nháp)
  hero_kind        (none | image | animation | video)
  hero_image       (file, ảnh tĩnh hoặc GIF/WebP động), hero_video (file), hero_video_mobile (file), hero_poster (file; GIF thì tự tạo)
  hero_title, hero_subtitle, hero_cta_label, hero_cta_url
  bar_enabled, bar_text, bar_url
  collection_title
  created_by, updated_by, timestamps

CampaignProduct   (campaign, product, sort_order)
CampaignPromotion (campaign, promotion)  /  CampaignCoupon (campaign, coupon)
```

Ràng buộc: `ends_at > starts_at`; không chồng giờ giữa các chiến dịch đã phát hành (kiểm tra ở service, có test).

---

## 11. Báo cáo theo chiến dịch

- Số đơn, doanh thu, số món bán trong thời gian chiến dịch, so với khoảng thời gian dài bằng nhau ngay trước đó (cùng cách tính với báo cáo khuyến mãi hiện có: chỉ đơn đã thanh toán, không bị huỷ).
- Doanh thu của nhóm sản phẩm trong chiến dịch.
- Số lượt bấm nút trên hero (đếm ở máy chủ khi khách đi qua link chuyển hướng `/c/<slug>`; không dùng cookie theo dõi).

---

## 12. Giai đoạn triển khai

| Giai đoạn | Nội dung | Kết quả kiểm tra |
|---|---|---|
| **1. Nền tảng** | Model, migration, quyền, API quản trị (CRUD, phát hành, kết thúc sớm, kiểm tra trùng giờ), trang "แคมเปญ" (danh sách + soạn), mẫu theme `default` + **`candle_festival` (làm trước)** + สงกรานต์, ปีใหม่, hero bằng **ảnh hoặc GIF** (poster tự tạo), thanh thông báo, nhóm sản phẩm, xem trước | Test backend cho lịch/trùng/quyền; e2e: tạo → xem trước → phát hành → shop đổi giao diện → hết giờ tự trở lại |
| **2. Video** | Upload MP4/WebM, poster, video điện thoại, route Caddy, giảm chuyển động/tiết kiệm dữ liệu | Test kiểm tra file sai định dạng/quá dung lượng; kiểm tra trên điện thoại thật |
| **3. Lịch và báo cáo** | Tab ปฏิทิน, nút ทำซ้ำ, chuyển báo cáo cũ vào tab รายงาน, báo cáo theo chiến dịch, đếm lượt bấm | Test số liệu báo cáo |
| **4. Mở rộng (khi cần)** | Mẫu còn lại, link YouTube, thông báo LINE khi chiến dịch bắt đầu (dùng Outbox có sẵn), popup một lần | Theo từng mục |

---

## 13. Câu trả lời của chủ tiệm (13/10/2026)

| Câu hỏi | Trả lời | Ảnh hưởng tới kế hoạch |
|---|---|---|
| Dịp lễ cần làm trước | Lễ hội nến Ubon Ratchathani (แห่เทียนพรรษา) | Mẫu `candle_festival` làm đầu tiên (mục 3.2, giai đoạn 1) |
| Ai soạn, ai phát hành | Manager hoặc sales | Cả hai quyền chiến dịch cho owner, manager, sales; không có bước duyệt riêng (mục 8) |
| Video | Có thể có hoặc không; có thể là video hoặc GIF | Hero không bắt buộc chuyển động; thêm GIF/WebP động ở giai đoạn 1, video ở giai đoạn 2 (mục 4) |
| Lưu trữ | Giống ảnh, theo cấu hình | Dùng `STORAGE_BACKEND` hiện có, không cấu hình riêng (mục 4.3) |
| Banner ở trang chi tiết sản phẩm | Không | Chiến dịch chỉ đổi trang chủ, thanh thông báo và màu nhấn (mục 9) |
| Thời gian lễ hội nến | Hằng năm vào tháng 7 | Lễ năm 2569 đã qua, nên chiến dịch đầu tiên là **tháng 7/2570 (2027)**. Ngày lễ đi theo âm lịch (quanh วันอาสาฬหบูชา và วันเข้าพรรษา) nên đổi mỗi năm: tab ปฏิทิน chỉ gợi ý "tháng 7", nhân viên tự nhập ngày giờ chính xác khi tạo hoặc khi "ทำซ้ำ" từ năm trước. Hệ thống không tự tính ngày âm lịch |

Giai đoạn 1 cần xong và chạy thử trên máy thật trước **cuối tháng 6/2570**, để kịp soạn và xem trước chiến dịch lễ hội nến đầu tiên.

## 14. Không làm trong phạm vi này

- Trình kéo thả tự thiết kế trang, chỉnh CSS hay HTML tự do.
- Đổi màu trang giỏ hàng, thanh toán, PromptPay.
- Hiệu ứng rơi (tuyết, hoa) chạy liên tục, nhạc nền tự phát.
- Nén/chuyển định dạng video trên máy chủ (cần ffmpeg, xem lại ở giai đoạn 4).
