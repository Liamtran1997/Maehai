# Spec: Kho v2 (kho tổng, chi nhánh, nguồn hàng ra vào)

Trạng thái: giai đoạn 1 **đã triển khai**. Giai đoạn 2 **đã chốt yêu cầu, sẵn sàng làm**. Giai đoạn 3–5 là đề xuất. Cập nhật: 13/10/2026.
Phạm vi: trang quản trị mục **สต็อก**, chứng từ nhập/chuyển/hoàn hàng giữa các kho, cách đơn online giữ và trừ hàng, báo cáo và thông báo liên quan.

Mọi quyết định đã được chủ tiệm chốt ngày 13/10/2026 (mục 3). Mã `D…` trong văn bản trỏ về quyết định tương ứng.

---

## 1. Bối cảnh vận hành

Tiệm có **3 điểm bán**. Một điểm vừa bán vừa là **kho tổng**.

| Điểm | Vai trò | Nguồn hàng vào |
|---|---|---|
| สาขาถนนศรีณรงค์ (`srinarong`) | **Kho tổng** + điểm bán | Nhập từ nhiều nguồn bên ngoài (chủ tiệm/quản lý nhập tay); hàng hoàn từ chi nhánh |
| สาขาถนนแจ้งสนิท (`changsanit`) | Điểm bán (chi nhánh) | Chỉ nhận từ kho tổng |
| สาขาบุ่งหวาย (`bungwai`) | Điểm bán (chi nhánh) | Chỉ nhận từ kho tổng |

Luồng hàng:

```
 Nguồn bên ngoài ──(phiếu nhập)──▶ KHO TỔNG ศรีณรงค์ ──(phiếu chuyển, đi xe)──▶ แจ้งสนิท / บุ่งหวาย
                                        ▲                                            │
                                        └──────────(phiếu hoàn: hàng hỏng/từ chối)───┘
 Mỗi kho: bán online · bán tại quầy · ghi hỏng · kiểm kê
```

Mục tiêu chính: **truy được mọi đơn vị hàng vào và ra khỏi từng kho**. Với mỗi lần tồn thay đổi, phải biết hàng từ đâu tới hoặc đi đâu, theo chứng từ nào, ai làm, lúc nào.

## 2. Hiện trạng và vấn đề

### 2.1 Hệ thống đang làm gì (sau giai đoạn 1)

| Phần | Cách làm hiện tại |
|---|---|
| Kho | 2 chi nhánh ngang hàng (`srinarong`, `changsanit`). **Chưa có บุ่งหวาย**, chưa có khái niệm kho tổng |
| Số liệu | Mỗi cỡ, mỗi kho: `on_hand` (đang có), `reserved` (giữ cho đơn online), hạn mức online/ngày, ngưỡng sắp hết |
| Đơn online | Giữ hàng ở **một** kho đủ cả đơn (nhận tại tiệm: đúng kho đó; giao: kho mặc định `srinarong` trước). Hủy thì trả lại. Gửi/hoàn tất thì trừ hẳn. Đơn chưa thanh toán giữ hàng 60 phút |
| Nhập hàng | "รับของเข้า": cộng số vào một kho, **không ghi nguồn** |
| Chuyển kho | Một món, một lần, **tức thì**, giữa hai kho bất kỳ. Ghi 2 dòng sổ "โอนออก"/"รับโอน" **không liên kết** với nhau |
| Khác | Ghi hỏng, kiểm kê (ghi đè), "หมดหน้าร้าน", nhập CSV tồn đầu kỳ |
| Sổ kho | Mỗi thay đổi: số thay đổi, số sau, lý do, người làm, đơn liên quan (nếu có) |

### 2.2 Vấn đề

| # | Vấn đề | Hậu quả |
|---|---|---|
| V1 | Không có kho tổng; chuyển kho đi đâu cũng được | Không kiểm soát được luồng hàng một chiều kho tổng → chi nhánh |
| V2 | บุ่งหวาย chưa có trong kho | Không nhận hàng, không bán online, không có số liệu cho điểm thứ ba |
| V3 | Nhập hàng không ghi nguồn, không có chứng từ | Không trả lời được "hàng này từ đâu tới" |
| V4 | Chuyển kho tức thì, không có bước nhận | Hàng thiếu hoặc hỏng trên đường không ai biết, chi nhánh không xác nhận |
| V5 | Hai dòng sổ của một lần chuyển không liên kết; không có số chứng từ | Không đối soát được kho gửi với kho nhận |
| V6 | Không có luồng hoàn hàng hỏng về kho tổng | Hàng hỏng bị ghi lẫn vào "ของเสีย" ở chi nhánh |
| V7 | Nhân viên thao tác được mọi kho | Chi nhánh có thể "nhận" hàng thay kho khác; không khoanh được trách nhiệm |
| V8 | Không có báo cáo nhập–xuất–tồn theo kho | Không đối soát được đầu kỳ + nhập − xuất = cuối kỳ |
| V9 | Hàng tươi có hạn dùng, hệ thống không biết lô | Không biết món sắp hỏng *(giai đoạn sau)* |
| V10 | Không có giá vốn | Không tính được giá trị tồn, hao hụt bằng tiền *(giai đoạn sau)* |

## 3. Quyết định

### 3.1 Đã chốt (chủ tiệm trả lời ngày 13/10/2026)

| # | Câu trả lời | Spec hiểu là |
|---|---|---|
| D1 | สาขาถนนศรีณรงค์ là kho tổng | `srinarong` có vai trò **kho tổng**; hai điểm còn lại là **chi nhánh** |
| D2 | Kho tổng nhận nguyên liệu từ rất nhiều nơi; chủ tiệm hoặc quản lý nhập tay | Có **phiếu nhập** tại kho tổng, ghi nguồn. Chỉ chủ tiệm/quản lý tạo. Danh sách nguồn do họ tự thêm. *Còn mở: nhập nguyên liệu hay thành phẩm, xem Q-A1* |
| D3 | Mỗi lần giao, người gửi tạo phiếu ghi đã xuất gì, sang cửa hàng nào, đi xe gì. Người nhận kiểm tra, bấm xác nhận thì hàng vào kho chi nhánh | Có **phiếu chuyển** kho tổng → chi nhánh, gồm danh sách món và thông tin xe. Hàng **chỉ vào kho chi nhánh khi người nhận xác nhận** |
| D4 | Số chuyến xe mỗi ngày chưa quan tâm | **Không quản lý chuyến xe.** Mỗi phiếu đi một chi nhánh; xe ghi dạng chữ tự do |
| D5 | Hàng hỏng thì mô tả rõ ở bước nhận và hoàn về kho tổng. Người nhận có thể nhận hoặc không | Khi nhận, mỗi món có thể **nhận** hoặc **không nhận (kèm mô tả)**. Phần không nhận tạo **phiếu hoàn** về kho tổng |
| D8 | (Q-A1) Hàng nhập vào có thể là nguyên liệu, thành phẩm, hoặc loại khác | Kho quản lý **mặt hàng kho** gồm nhiều loại, không chỉ các cỡ đang bán (mục 6.1) |
| D9 | (Q-D1) Hàng thiếu: theo đề xuất | Ghi mất trên đường (`transit_loss`) ngay, báo quản lý, không tạo phiếu hoàn |
| D10 | (Q-D2) Hàng hỏng hoàn về: theo đề xuất | Kho tổng chọn từng dòng "เข้าสต็อก" hoặc "ทิ้ง", mặc định "ทิ้ง" với hàng hỏng |
| D11 | (Q-B1) บุ่งหวาย cho nhận tại tiệm | Thêm cách nhận "รับที่ร้าน สาขาบุ่งหวาย" |
| D12 | (Q-F2/F3) Mỗi chi nhánh có 1–2 quản lý phụ trách, họ kiểm và xác nhận hàng | Có vai trò **ผู้จัดการสาขา** gắn với một chi nhánh; chỉ họ (và cấp trên) xác nhận nhận hàng của chi nhánh đó (mục 16) |
| D13 | (Q-C1) Không có bước nháp: theo đề xuất | Tạo phiếu chuyển là gửi luôn; hủy được trước khi chi nhánh xác nhận |

### 3.2 Chốt từ giai đoạn 1 (đã làm, chủ tiệm xác nhận ngày 13/10/2026)

| # | Nội dung | Đang dùng |
|---|---|---|
| D6 | Chia hàng giữa online và quầy | Hạn mức online/ngày cho từng món ở từng kho; nút "หมดหน้าร้าน" |
| D7 | Giữ hàng cho đơn chưa thanh toán | 60 phút, kiểm tra mỗi 5 phút; đơn đã gửi slip không bị hủy |

### 3.3 Chốt theo đề xuất của BA (chủ tiệm đồng ý ngày 13/10/2026)

| # | Câu hỏi | Quyết định |
|---|---|---|
| D14 | Q-A2 Đơn giá trên phiếu nhập | Có ô đơn giá, không bắt buộc |
| D15 | Q-A3 Ai tạo phiếu nhập | Chỉ chủ tiệm và quản lý chung |
| D16 | Q-A4 Tự trừ nguyên liệu theo công thức | Không ở giai đoạn 2; ghi "เบิกใช้" bằng tay. Công thức để sau, khi có số liệu dùng thực tế |
| D17 | Q-A5 Số lẻ và đơn vị | Nguyên liệu/vật tư/khác: tối đa 3 chữ số lẻ. Đơn vị: กก., กรัม, ลิตร, ชิ้น, แพ็ค, ม้วน, ถุง (chủ tiệm thêm được). Thành phẩm: số nguyên, ชิ้น |
| D18 | Q-A6 Kho tổng gửi gì xuống chi nhánh | Mọi loại mặt hàng, chung một phiếu chuyển |
| D19 | Q-B2 Giao tận nơi khi kho tổng hết | Báo hết; nhân viên đổi kho xuất bằng tay nếu muốn |
| D20 | Q-B3 Chuyển giữa hai chi nhánh | Không có. Hoàn về kho tổng rồi chuyển lại |
| D21 | Q-C2 Thời hạn xác nhận nhận hàng | Nhắc sau 24 giờ; không tự xác nhận |
| D22 | Q-C3 Ảnh khi không nhận | Không bắt buộc; đính kèm tối đa 3 ảnh |
| D23 | Q-C4 In phiếu | Có nút in phiếu giao hàng (A5), không bắt buộc dùng |
| D24 | Q-C5 Thông tin xe | Ghi tự do; gợi ý lại các giá trị đã dùng |
| D25 | Q-C6 Cả hai ผู้จัดการสาขา vắng | Quản lý chung hoặc chủ tiệm xác nhận thay, bắt buộc ghi lý do; hoặc phiếu chờ |
| D26 | Q-D3 Chi nhánh chủ động trả hàng | Có; ผู้จัดการสาขา tạo phiếu hoàn |
| D27 | Q-D4 Hàng hoàn có phải về cùng xe | Không bắt buộc; phiếu hoàn chờ tới khi kho tổng xác nhận |
| D28 | Q-E1 Giữ hàng cho chi nhánh ở kho tổng | Không làm riêng; dùng hạn mức online của kho tổng để chừa hàng |
| D29 | Q-E2 Món làm tươi | Tính theo tồn ở giai đoạn 2; năng lực theo ngày để giai đoạn 4 |
| D30 | Q-E3 Ai giao tận nơi | Chỉ kho tổng |
| D31 | Q-F1 Nhóm LINE | Mỗi kho một nhóm LINE nhân viên riêng |
| D32 | Q-F4 Việc ở kho tổng | Nhân viên kho được gán kho tổng tạo phiếu chuyển và nhận hàng hoàn; chủ tiệm/quản lý chung làm thay được. Kho tổng không có ผู้จัดการสาขา |
| D33 | Q-F5 Quyền của ผู้จัดการสาขา | Như mục 16.1; **không** xác nhận thanh toán |
| D34 | Q-F6 Một người hai chi nhánh | Không; mỗi ผู้จัดการสาขา đúng một chi nhánh |

## 4. Thuật ngữ

| Thuật ngữ | Nghĩa |
|---|---|
| Kho | Một nơi có tồn: kho tổng hoặc chi nhánh. Mỗi điểm bán là một kho |
| Mặt hàng kho | Thứ được đếm trong kho: **thành phẩm** (gắn với một cỡ đang bán), **nguyên liệu**, **vật tư/bao bì**, hoặc **khác** |
| Đơn vị tính | Của mặt hàng kho: ชิ้น, แพ็ค, กก., กรัม, ลิตร… Thành phẩm luôn là số nguyên; đơn vị cân đo cho phép số lẻ |
| Kho tổng | Kho duy nhất nhận hàng từ bên ngoài và cấp hàng cho chi nhánh |
| Chi nhánh | Điểm bán chỉ nhận hàng từ kho tổng |
| Nguồn | Nơi hàng tới từ bên ngoài (nhà cung cấp, tự sản xuất…), do chủ tiệm/quản lý tạo |
| Phiếu nhập (`IN-`) | Chứng từ nhập hàng từ một nguồn vào kho tổng |
| Phiếu chuyển (`TR-`) | Chứng từ chuyển hàng từ kho tổng tới một chi nhánh |
| Phiếu hoàn (`RT-`) | Chứng từ trả hàng từ chi nhánh về kho tổng |
| Hàng đang chuyển | Hàng đã rời kho gửi, chưa được kho nhận xác nhận. Không thuộc tồn của kho nào và không bán được |
| Tồn (`on_hand`) | Số đang có thật trong kho |
| Đang giữ (`reserved`) | Đã hứa cho đơn online chưa giao |
| Còn bán online | `min(on_hand − reserved, hạn mức online còn lại hôm nay)` |

Số chứng từ: `IN-2569-000001`, `TR-2569-000001`, `RT-2569-000001` (năm Phật lịch, tăng dần, giống số đơn hàng `MH-`).

## 5. Kho và vai trò

1. Mỗi kho có **vai trò**: `central` (kho tổng) hoặc `store` (chi nhánh). Hệ thống **chỉ có đúng một** kho tổng đang hoạt động; đổi kho tổng chỉ chủ tiệm làm được.
2. Thêm kho `bungwai` – "สาขาบุ่งหวาย", vai trò `store`, và cách nhận "รับที่ร้าน สาขาบุ่งหวาย" cho đơn online (D11).
3. **Đơn giao tận nơi** (ขนส่ง, พัสดุ) luôn xuất từ **kho tổng** (D30). Kho tổng thiếu thì báo hết, không tự lấy từ chi nhánh; nhân viên đổi kho xuất bằng tay được như hiện nay (D19).
4. **Đơn nhận tại tiệm** xuất từ đúng kho đó (như hiện tại).
5. Quy tắc nguồn hàng:

| Kho | Được tăng tồn bằng | Không được |
|---|---|---|
| Kho tổng | Phiếu nhập, nhận phiếu hoàn, kiểm kê, nhập CSV, sửa sai, hủy đơn online | Nhận phiếu chuyển |
| Chi nhánh | Nhận phiếu chuyển, kiểm kê, nhập CSV, sửa sai, hủy đơn online | Phiếu nhập từ nguồn ngoài; nhận từ chi nhánh khác |

6. **Bỏ "โอนระหว่างสาขา" tức thì** hiện có. Mọi luồng hàng giữa các kho đi qua phiếu chuyển hoặc phiếu hoàn. Không có chuyển giữa hai chi nhánh (D20).

## 6. Mặt hàng kho và phiếu nhập kho tổng (`IN-`)

### 6.1 Mặt hàng kho (D8)

Hiện kho chỉ đếm các **cỡ đang bán**. Từ giai đoạn 2, kho đếm **mặt hàng kho**:

| Loại | Ví dụ | Gắn với | Đơn vị | Bán online/quầy |
|---|---|---|---|---|
| `product` – thành phẩm | หมูยอพริกไทยดำ (เล็ก) | Đúng một cỡ đang bán (SKU) | ชิ้น, số nguyên | Có |
| `material` – nguyên liệu | เนื้อหมู, ใบตอง, เครื่องเทศ | — | กก., กรัม, ลิตร, ชิ้น… | Không |
| `supply` – vật tư, bao bì | ถุง, กล่อง, ยางรัด, สติกเกอร์ | — | ชิ้น, แพ็ค, ม้วน… | Không |
| `other` – khác | do chủ tiệm định nghĩa | — | tùy | Không |

- Mỗi cỡ đang bán có bật theo dõi tồn **tự có** một mặt hàng `product` tương ứng. Không tạo tay.
- Mặt hàng loại khác do chủ tiệm/quản lý tạo ở trang **"รายการวัตถุดิบและวัสดุ"**: tên, loại, đơn vị, mã (tự sinh, sửa được), ngưỡng sắp hết, ghi chú. Đã có giao dịch thì không xóa, chỉ ẩn; **không đổi được đơn vị**.
- Số lượng: `product` là số nguyên; các loại khác cho phép **tối đa 3 chữ số thập phân** (D17). Đơn vị có sẵn: กก., กรัม, ลิตร, ชิ้น, แพ็ค, ม้วน, ถุง; chủ tiệm/quản lý thêm được.
- Hạn mức online, giữ hàng cho đơn, "หมดหน้าร้าน" chỉ áp dụng cho `product`.
- Mặt hàng không phải thành phẩm **ra khỏi kho** bằng lý do mới `consume` ("เบิกใช้"): ghi tay, kèm ghi chú (dùng làm gì). Không trừ tự động theo công thức sản xuất (D16).
- Báo cáo nhập–xuất–tồn (mục 9.2) lọc được theo loại.

### 6.2 Nguồn

- Chủ tiệm/quản lý tạo, sửa, ẩn nguồn ở trang **"แหล่งสินค้า"**: tên (bắt buộc), loại (`ผลิตเอง` / `ซื้อ` / `อื่นๆ`), số điện thoại, ghi chú.
- Nguồn đã dùng trong phiếu thì không xóa, chỉ ẩn.
- Có sẵn một nguồn `ผลิตเอง` (tiệm tự làm).

### 6.3 Tạo phiếu

| Trường | Bắt buộc | Quy tắc |
|---|---|---|
| Nguồn | Có | Chọn từ danh sách nguồn đang hiển thị |
| Ngày nhận | Có | Mặc định hôm nay; không được ở tương lai |
| Số chứng từ của nguồn | Không | Ví dụ số hóa đơn của nhà cung cấp |
| Dòng hàng | Có, ≥ 1 | Mặt hàng kho (mọi loại) + số lượng > 0 theo đơn vị của mặt hàng. Một mặt hàng chỉ một dòng. Một phiếu được trộn nhiều loại |
| Đơn giá | Không | Theo đơn vị tính (D14) |
| Ghi chú | Không | ≤ 500 ký tự |

- Lưu phiếu thì **tồn kho tổng tăng ngay**. Mỗi dòng ghi sổ lý do `receive`, kèm số phiếu và nguồn.
- Thành phẩm có cỡ chưa bật theo dõi tồn thì không đưa vào phiếu được (báo "ต้องเปิดนับสต็อกก่อน").
- Thành phẩm tiệm tự làm cũng nhập bằng phiếu nhập, nguồn `ผลิตเอง`.
- Phiếu đã lưu **không sửa, không xóa**. Nhập sai thì tạo phiếu điều chỉnh (mục 12, lý do `correction`) trỏ về phiếu gốc.
- Quyền: chủ tiệm, quản lý (`inventory.receive`).

> Giới hạn có chủ đích (D16): giai đoạn 2 **không** nối nguyên liệu với thành phẩm. Làm 100 cây หมูยอ không tự trừ thịt; người dùng ghi "เบิกใช้" nguyên liệu và nhập thành phẩm `ผลิตเอง` riêng.

## 7. Phiếu chuyển kho tổng → chi nhánh (`TR-`)

### 7.1 Tạo phiếu (người gửi, tại kho tổng)

| Trường | Bắt buộc | Quy tắc |
|---|---|---|
| Kho nhận | Có | Một chi nhánh đang hoạt động |
| Xe | Có | Chữ tự do ≤ 100 ký tự, ví dụ "กระบะขาว กข-1234" |
| Người chở | Không | Chữ tự do |
| Dòng hàng | Có, ≥ 1 | Mặt hàng kho (mọi loại, D18) + số lượng > 0, không vượt **còn dùng được** của kho tổng (thành phẩm: `on_hand − reserved`; loại khác: `on_hand`) |
| Ghi chú | Không | ≤ 500 ký tự |

- Bấm **"ส่งของ"** thì:
  - Tồn kho tổng **giảm ngay** từng dòng (sổ: `transfer_out`, kèm số phiếu, kho nhận).
  - Hàng chuyển sang **đang chuyển**, phiếu ở trạng thái **"กำลังส่ง"**.
  - LINE báo nhóm nhân viên của chi nhánh nhận (mục 15).
- Không có bước "nháp": tạo phiếu là gửi luôn (D13).
- Thiếu hàng ở kho tổng thì phiếu bị từ chối, nêu món và số còn.
- Quyền: nhân viên được gán kho tổng có `inventory.transfer`, quản lý, chủ tiệm.

### 7.2 Trạng thái

```
กำลังส่ง ──(chi nhánh xác nhận)──▶ รับครบ
    │                         └──▶ รับบางส่วน   (có món không nhận → tạo phiếu hoàn)
    │                         └──▶ ไม่รับทั้งหมด (tạo phiếu hoàn toàn bộ)
    └──(người gửi hủy trước khi chi nhánh xác nhận)──▶ ยกเลิก (hàng về lại kho tổng)
```

- Hủy: chỉ người tạo phiếu, quản lý hoặc chủ tiệm; bắt buộc ghi lý do. Tồn kho tổng cộng lại, sổ ghi `transfer_cancel` (ngược với `transfer_out`).
- Phiếu đã xác nhận nhận thì đóng, không sửa.

### 7.3 Nhận hàng (người nhận, tại chi nhánh)

Người nhận mở phiếu "กำลังส่ง" của chi nhánh mình, kiểm từng dòng:

| Cột | Ý nghĩa |
|---|---|
| Đã gửi | Số trên phiếu (chỉ đọc) |
| Nhận | Số nhận vào kho chi nhánh (mặc định = đã gửi) |
| Không nhận | = Đã gửi − Nhận. Nếu > 0: **bắt buộc** chọn lý do (`ชำรุด` hỏng, `ขาด` thiếu, `ไม่ตรง` sai hàng, `อื่นๆ`) và mô tả (≤ 300 ký tự). Đính kèm tối đa 3 ảnh, không bắt buộc (D22) |

- Có nút nhanh **"รับครบทั้งหมด"** và **"ไม่รับทั้งหมด"** (vẫn phải ghi lý do).
- Bấm **"ยืนยันรับของ"** thì:
  - Phần **nhận** cộng vào tồn chi nhánh (sổ: `transfer_in`, kèm số phiếu, kho gửi).
  - Phần **không nhận** đi theo mục 8.
  - Phiếu chuyển sang "รับครบ" / "รับบางส่วน" / "ไม่รับทั้งหมด"; lưu người nhận, thời điểm.
  - LINE báo kho tổng nếu có chênh lệch.
- Không nhận nhiều hơn số đã gửi. Hàng gửi thêm ngoài phiếu thì kho tổng tạo phiếu mới.
- Phiếu chưa xác nhận sau **24 giờ** thì nhắc trên dashboard và LINE quản lý; không tự xác nhận (D21). Khi cả hai ผู้จัดการสาขา vắng, quản lý chung hoặc chủ tiệm xác nhận thay (D25).
- Người xác nhận: **ผู้จัดการสาขา của đúng chi nhánh nhận** (1–2 người mỗi chi nhánh, D12). Quản lý chung và chủ tiệm xác nhận thay được, nhưng phải ghi lý do và nhật ký ghi rõ "xác nhận thay".
- Người gửi ở kho tổng không xác nhận phiếu của chính mình.

## 8. Hàng không nhận và phiếu hoàn (`RT-`)

Theo D5, hàng không nhận hoàn về kho tổng. Cách xử lý tùy lý do:

| Lý do không nhận | Hàng thật ở đâu | Xử lý |
|---|---|---|
| `ชำรุด` hỏng, `ไม่ตรง` sai hàng, `อื่นๆ` | Đi theo xe về kho tổng | Tự tạo **phiếu hoàn** trạng thái "กำลังส่งคืน" |
| `ขาด` thiếu (không có trên xe) | Không ai giữ | Ghi sổ `transit_loss` ngay, không tạo phiếu hoàn; LINE báo quản lý |

"Thiếu" khác "hỏng": hàng thiếu không có gì để hoàn, nên ghi mất ngay và để quản lý điều tra (D9).

Kho tổng nhận phiếu hoàn: với từng dòng, người nhận ở kho tổng chọn:
- **"เข้าสต็อก"**: còn bán được → cộng tồn kho tổng (sổ `return_in`).
- **"ทิ้ง"**: hỏng → không cộng tồn, ghi `waste` kèm số phiếu hoàn.
- Số kho tổng nhận được ít hơn số trên phiếu hoàn → phần thiếu ghi `transit_loss`.

Hàng hoàn có lý do `ชำรุด` mặc định là "ทิ้ง"; người nhận ở kho tổng đổi được (D10).

Phiếu hoàn cũng có thể do ผู้จัดการสาขา **chủ động tạo** (trả hàng sắp hết hạn, dư hàng) (D26): chọn mặt hàng và số lượng, tồn chi nhánh giảm ngay (`return_out`), hàng chuyển sang "đang chuyển". Hàng hoàn không bắt buộc về cùng chuyến xe; phiếu chờ tới khi kho tổng xác nhận (D27).

## 9. Truy vết nguồn hàng và báo cáo

### 9.1 Sổ kho (bổ sung so với hiện tại)

Mỗi dòng sổ có thêm:
- **Chứng từ**: loại + số (`IN-…`, `TR-…`, `RT-…`, `MH-…` đơn hàng, `CNT-…` kiểm kê), bấm để mở.
- **Đối ứng**: nguồn (với phiếu nhập) hoặc kho bên kia (với chuyển/hoàn).

Lọc theo kho, món, lý do, chứng từ, người làm, khoảng ngày. Xuất CSV.

### 9.2 Báo cáo nhập – xuất – tồn theo kho

Cho một kho và khoảng ngày, mỗi món một dòng:

| Đầu kỳ | Nhập từ nguồn | Nhận chuyển | Nhận hoàn | Bán online | Bán quầy | Chuyển đi | Hoàn đi | Hỏng/mất | Chênh kiểm kê | Cuối kỳ |
|---|---|---|---|---|---|---|---|---|---|---|

- Phải thỏa: **Đầu kỳ + các cột vào − các cột ra ± chênh kiểm kê = Cuối kỳ**. Dòng nào không khớp thì tô đỏ (dấu hiệu lỗi dữ liệu).
- Bấm vào một ô để xem các dòng sổ tạo nên số đó.

### 9.3 Hàng đang chuyển

- Danh sách phiếu chuyển "กำลังส่ง" và phiếu hoàn "กำลังส่งคืน": số phiếu, kho gửi → kho nhận, xe, thời gian đã đi, số món.
- Phiếu quá 24 giờ tô cam.
- Tổng hàng đang chuyển theo từng món, để tổng toàn hệ thống = tồn các kho + đang chuyển.

### 9.4 Đối soát chuyển hàng

Theo chi nhánh và khoảng ngày: tổng đã gửi, đã nhận, không nhận theo lý do, tỉ lệ nhận đủ. Danh sách phiếu có chênh lệch.

### 9.5 Truy một món

Cho một SKU: dòng thời gian qua các kho. Ví dụ: `IN-…` từ nguồn X vào kho tổng → `TR-…` sang แจ้งสนิท → bán quầy / đơn `MH-…`.

Lưu ý: khi chưa có lô (mục 13), truy vết là **theo chứng từ và số lượng**, không theo từng đơn vị hàng.

## 10. Bán tại quầy và online *(giai đoạn 1, đã làm)*

1. Mỗi món, mỗi kho có **hạn mức online/ngày** (trống = không giới hạn). Tính lại lúc 00:00 giờ Thái. Đơn hủy trong ngày trả lại hạn mức.
2. Shop hiển thị "เหลือ N ชิ้น" theo **còn bán online**.
3. Nút **"หมดหน้าร้าน"**: tồn = số đang giữ, sổ ghi `counter_sale`.
4. *Giai đoạn sau:* "ปิดยอดหน้าร้าน" cuối ngày, nhập số bán quầy từng món.

Áp vào mô hình kho tổng: kho tổng vừa bán vừa cấp hàng. Phiếu chuyển trừ tồn ngay khi gửi, nên không cần "giữ hàng cho chuyến". Để kho tổng không bán online hết hàng định gửi chi nhánh, đặt **hạn mức online** cho kho tổng (D28).

## 11. Giữ hàng cho đơn chưa thanh toán *(giai đoạn 1, đã làm)*

1. Giữ tối đa 60 phút (`ORDER_UNPAID_EXPIRY_MINUTES`). Job kiểm tra mỗi 5 phút.
2. Đơn đã gửi slip không tự hủy.
3. *Chưa làm:* nhắc báo phí ship sau 4 giờ làm việc; đếm ngược thời hạn trên trang đơn của khách.

## 12. Lý do ghi sổ

| Lý do | Ý nghĩa | Hướng | Chứng từ | Kho |
|---|---|---|---|---|
| `opening` | Tồn đầu kỳ (CSV) | + | — | Mọi kho |
| `receive` | Nhập từ nguồn | + | `IN-` | Kho tổng |
| `transfer_out` | Gửi đi chi nhánh | − | `TR-` | Kho tổng |
| `transfer_cancel` | Hủy phiếu chuyển chưa nhận | + | `TR-` | Kho tổng |
| `transfer_in` | Chi nhánh nhận | + | `TR-` | Chi nhánh |
| `return_out` | Chi nhánh trả về (phiếu hoàn chủ động) | − | `RT-` | Chi nhánh |
| `return_in` | Kho tổng nhận hàng hoàn, còn bán được | + | `RT-` | Kho tổng |
| `transit_loss` | Thiếu trên đường | − (khỏi "đang chuyển") | `TR-`/`RT-` | — |
| `sale` | Giao đơn online | − | `MH-` | Mọi kho |
| `counter_sale` | Bán quầy / หมดหน้าร้าน (chỉ thành phẩm) | − | — | Mọi kho |
| `consume` | Xuất dùng nguyên liệu, vật tư ("เบิกใช้") | − | — | Mọi kho |
| `waste` | Hỏng, hết hạn, hàng hoàn bị bỏ | − | `RT-` nếu từ hàng hoàn | Mọi kho |
| `count` | Chênh lệch kiểm kê / CSV lần sau | ± | `CNT-` | Mọi kho |
| `correction` | Sửa nhập sai, bắt buộc ghi chú và trỏ chứng từ gốc | ± | chứng từ gốc | Mọi kho |

- Không xóa dòng sổ; sai thì ghi dòng `correction` đối ứng.
- Bỏ lý do `transfer_in`/`transfer_out` không có chứng từ (chuyển tức thì cũ). Dữ liệu cũ giữ nguyên.

## 13. Lô và hạn dùng *(đề xuất, giai đoạn 4)*

- Món có bật "มีวันหมดอายุ": mỗi dòng phiếu nhập ghi **ngày hết hạn**, tạo một lô.
- Phiếu chuyển tự lấy lô **hết hạn sớm nhất** (FEFO) và mang lô sang chi nhánh; phiếu hoàn mang lô về.
- Lô hết hạn không bán; cảnh báo lô hết hạn trong 2 ngày; nút "ตัดของหมดอายุ".
- Khi có lô, truy vết được tới từng lô: lô nào, từ nguồn nào, đang nằm ở kho nào.

## 14. Kiểm kê, ngưỡng, năng lực ngày

- **Phiếu kiểm kê (`CNT-`)** theo kho: tạo → đếm → gửi duyệt → quản lý duyệt. Chênh lệch nhỏ hơn ngưỡng thì người đếm tự duyệt.
- **Ngưỡng sắp hết** theo món, theo kho *(đã làm)*. Bổ sung: với chi nhánh, cột **"ควรส่งเพิ่ม"** = trung bình bán 7 ngày × 2 ngày − còn bán − đang chuyển tới. Kho tổng dùng số này khi soạn phiếu chuyển.
- **Năng lực theo ngày** cho món làm theo đơn: để giai đoạn 4, chỉ áp dụng ở kho tổng (nơi làm hàng). Giai đoạn 2 mọi món tính theo tồn (D29).

## 15. Thông báo LINE

| Sự kiện | Gửi tới |
|---|---|
| Phiếu chuyển gửi đi | Nhóm chi nhánh nhận: số phiếu, xe, số món |
| Chi nhánh xác nhận có chênh lệch | Kho tổng và quản lý: món, số, lý do |
| Phiếu chuyển/hoàn quá 24 giờ chưa nhận | Quản lý |
| Ghi `transit_loss` | Quản lý, chủ tiệm |
| Sắp hết hàng *(đã có)* | Nhóm nhân viên |

Mỗi kho có một nhóm LINE nhân viên riêng (D31). Thay biến chung `LINE_STAFF_IDS` bằng cấu hình nhóm theo từng kho trong admin; nhóm chung cũ vẫn nhận tin cấp toàn tiệm (mất trên đường, sắp hết hàng nếu kho chưa có nhóm).

## 16. Phân quyền

### 16.1 Vai trò ผู้จัดการสาขา (D12)

- Vai trò mới **ผู้จัดการสาขา** (`branch_manager`), mỗi người gắn với **đúng một** chi nhánh. Mỗi chi nhánh có 1–2 người.
- Khác với **ผู้จัดการ** hiện có (quản lý chung, thấy mọi kho).
- Kho tổng không có ผู้จัดการสาขา: nhân viên kho được gán kho tổng tạo phiếu chuyển và nhận hàng hoàn; chủ tiệm, quản lý chung làm thay được (D32).
- Mỗi người một tài khoản riêng để nhật ký và chứng từ ghi đúng người xác nhận.

Quyền của ผู้จัดการสาขา, chỉ trong chi nhánh của mình (D33):
- Xem tồn, sổ kho, chứng từ của chi nhánh.
- Xác nhận nhận phiếu chuyển; tạo phiếu hoàn chủ động (D26).
- Ghi hỏng, "เบิกใช้", "หมดหน้าร้าน", đặt hạn mức online và ngưỡng của chi nhánh.
- Xem và xử lý đơn online **nhận tại chi nhánh mình**: chuẩn bị, giao cho khách.
- **Không**: sửa giá, khuyến mãi, mã giảm giá, xác nhận thanh toán, xem doanh thu toàn tiệm, thao tác chi nhánh khác.

### 16.2 Gán kho cho nhân viên

- Mỗi nhân viên (trừ chủ tiệm, quản lý chung) được gán **một hoặc nhiều kho**.
- Họ chỉ **thấy và thao tác** kho được gán: tồn, sổ, phiếu, kiểm kê, nút "หมดหน้าร้าน".
- Chủ tiệm, quản lý thấy mọi kho.
- Đây là điều kiện bắt buộc để "người nhận xác nhận" có ý nghĩa, nên chuyển từ giai đoạn 3 lên **giai đoạn 2**.

### 16.3 Quyền mới

| Quyền | Cho phép | Chủ tiệm | Quản lý | ผจก.สาขา | Bán hàng | Kho | Sản phẩm |
|---|---|:-:|:-:|:-:|:-:|:-:|:-:|
| `inventory.receive` | Tạo phiếu nhập, quản lý nguồn và mặt hàng kho | ✓ | ✓ | | | | |
| `inventory.transfer` | Tạo/hủy phiếu chuyển (tại kho tổng) | ✓ | ✓ | | | ✓ | |
| `inventory.receive_transfer` | Xác nhận nhận phiếu chuyển của chi nhánh mình | ✓* | ✓* | ✓ | | | |
| `inventory.receive_return` | Nhận và xử lý phiếu hoàn tại kho tổng | ✓ | ✓ | | | ✓ | |
| `inventory.approve` | Duyệt kiểm kê, sửa sai, xác nhận thay chi nhánh | ✓ | ✓ | | | | |

\* Xác nhận thay, bắt buộc ghi lý do.

Nhân viên bán hàng ở chi nhánh **không** xác nhận nhận hàng (D12).

Test ma trận quyền phải gồm mọi endpoint mới, và có thêm test "nhân viên kho A không thao tác được kho B".

## 17. Màn hình (admin)

| Màn hình | Nội dung chính |
|---|---|
| สต็อก *(đã có, bổ sung)* | Thêm cột "กำลังส่งมา" cho chi nhánh; lọc theo kho được gán; bỏ "โอนระหว่างสาขา" |
| แหล่งสินค้า | Danh sách nguồn: thêm, sửa, ẩn |
| ใบรับสินค้า (`IN-`) | Danh sách + tạo phiếu nhập tại kho tổng |
| ใบส่งสินค้า (`TR-`) | Kho tổng: tạo, xem, hủy. Chi nhánh: hộp "รอรับ" với nút "ตรวจรับ" |
| ใบคืนสินค้า (`RT-`) | Kho tổng: "รอรับคืน", xử lý từng dòng |
| รายงานคลัง | Nhập – xuất – tồn, hàng đang chuyển, đối soát chuyển hàng, truy một món |
| Dashboard *(bổ sung)* | "รอรับของ" (phiếu đang tới chi nhánh của tôi), "ค้างส่ง > 24 ชม.", "มีของขาด/ชำรุด" |

Phiếu chuyển có nút **"พิมพ์ใบส่งของ"** (A5, gồm số phiếu, kho nhận, xe, dòng hàng, chỗ ký người giao/người nhận). Không bắt buộc dùng (D23). Ô "xe" gợi ý lại các giá trị đã nhập (D24).

## 18. Giá vốn *(đề xuất, giai đoạn 5)*

- Phiếu nhập có thể ghi **đơn giá** từng dòng. Giá vốn món = bình quân gia quyền tại kho tổng.
- Báo cáo: giá trị tồn theo kho, giá trị hao hụt (hỏng, mất trên đường, chênh kiểm kê), lãi gộp theo món.
- Nhân viên kho không thấy giá.

## 19. Giai đoạn triển khai

| Giai đoạn | Nội dung | Trạng thái / điều kiện |
|---|---|---|
| **1. Trước mở bán** | Nhập tồn CSV, hạn mức online, "หมดหน้าร้าน", ngưỡng theo món, giữ hàng 60 phút | **Đã làm** |
| **2. Kho tổng và chứng từ** | Mục 5 (vai trò kho, thêm บุ่งหวาย), 6 (mặt hàng kho nhiều loại, nguồn, phiếu nhập), 7 (phiếu chuyển, nhận hàng), 8 (phiếu hoàn), 9.1–9.3 (sổ có chứng từ, nhập–xuất–tồn, đang chuyển), 12, 15, 16 (ผู้จัดการสาขา, gán kho, quyền mới) | **Sẵn sàng làm.** Đi kèm cập nhật `staff-permissions.md` |
| **3. Kiểm soát** | Phiếu kiểm kê, 9.4–9.5, "ควรส่งเพิ่ม", in phiếu, "ปิดยอดหน้าร้าน" | Sau 2 |
| **4. Hàng tươi** | Lô và hạn dùng, năng lực ngày | Sau giai đoạn 2 (D29) |
| **5. Tài chính** | Giá vốn | Có đơn giá trên phiếu nhập |

## 20. Tiêu chí nghiệm thu (giai đoạn 2)

1. Kho tổng tạo `IN-` từ nguồn "ฟาร์ม A" 100 cây → tồn kho tổng +100, sổ có 1 dòng `receive` trỏ `IN-` và nguồn.
2. Tạo `TR-` 40 cây sang แจ้งสนิท, xe "กระบะขาว" → kho tổng −40; แจ้งสนิท chưa đổi; báo cáo "đang chuyển" có 40; nhóm LINE แจ้งสนิท nhận tin.
3. Nhân viên บุ่งหวาย **không thấy** và không xác nhận được phiếu của แจ้งสนิท (403).
4. แจ้งสนิท xác nhận nhận 37, không nhận 3 (`ชำรุด`, mô tả "แตก") → chi nhánh +37; phiếu "รับบางส่วน"; tạo `RT-` 3 cây "กำลังส่งคืน"; kho tổng nhận LINE.
5. Kho tổng nhận `RT-`: chọn "ทิ้ง" 3 → tồn kho tổng không đổi, sổ có `waste` 3 trỏ `RT-`.
6. Không nhận 2 vì `ขาด` → không tạo `RT-`; sổ có `transit_loss` 2; quản lý nhận LINE.
7. Hủy `TR-` trước khi nhận → kho tổng cộng lại đủ, sổ `transfer_cancel`.
8. Báo cáo nhập–xuất–tồn của cả 3 kho khớp công thức cho mọi món; tổng hệ thống = tồn 3 kho + đang chuyển.
9. Kho tổng thiếu hàng (còn bán 10) → tạo `TR-` 11 bị từ chối, nêu số còn.
10. Không còn đường nào làm tăng tồn chi nhánh từ nguồn ngoài hoặc từ chi nhánh khác (API trả 403/422).
11. Tạo mặt hàng "เนื้อหมู" (nguyên liệu, กก.); `IN-` nhập 12.5 กก. cùng phiếu với 50 cây thành phẩm → hai dòng sổ đúng đơn vị; "เบิกใช้" 10.25 กก. → còn 2.25 กก.; mặt hàng này không xuất hiện ở shop.
12. Nhập 1.5 cho một thành phẩm → bị từ chối (thành phẩm là số nguyên).
13. ผู้จัดการสาขา แจ้งสนิท xác nhận được phiếu của แจ้งสนิท; nhân viên bán hàng của แจ้งสนิท thì không (403); quản lý chung xác nhận thay phải nhập lý do, nhật ký ghi "xác nhận thay".

## 21. Câu hỏi

Không còn câu hỏi mở cho giai đoạn 2. Toàn bộ câu hỏi đã được trả lời ngày 13/10/2026 (mục 3: D1–D13 do chủ tiệm trả lời, D14–D34 theo đề xuất của BA).

Những điểm **sẽ phải hỏi lại** khi tới giai đoạn sau:
- Công thức sản xuất và tự trừ nguyên liệu (D16): cần số liệu dùng thực tế sau vài tuần chạy giai đoạn 2.
- Năng lực theo ngày cho món làm tươi (D29).
- Hạn dùng: món nào có hạn, bao nhiêu ngày (mục 13).
- Ngưỡng duyệt chênh lệch kiểm kê (mục 14).

## 22. Ngoài phạm vi

- Quản lý chuyến xe, lộ trình, tài xế, chi phí vận chuyển (D4).
- Công thức sản xuất và tự trừ nguyên liệu (D16); giá thành sản xuất.
- Đơn mua hàng gửi nhà cung cấp, công nợ.
- Kết nối máy POS, mã vạch, quét mã khi nhận hàng.
- Chuyển hàng giữa hai chi nhánh (D20).
