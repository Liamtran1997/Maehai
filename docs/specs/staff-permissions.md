# Spec: Phân quyền nhân viên

Trạng thái: mục 1–7 đã triển khai. **Mục 8 (ผู้จัดการสาขา, phạm vi theo kho, quyền kho mới) đã chốt, chưa triển khai**: làm cùng giai đoạn 2 của `inventory.md`. Cập nhật: 13/10/2026.

## 1. Vấn đề trước đây

Mọi nhân viên đăng nhập được đều làm được mọi thứ: sửa giá, tạo mã giảm giá, xác nhận đã nhận tiền, hủy đơn đã trả tiền, xem slip chuyển khoản. Không có cách tạo nhân viên trong hệ thống (phải dùng dòng lệnh) và không có dấu vết ai làm gì.

## 2. Nguyên tắc

- **Server là nơi quyết định.** Mọi API quản trị đều khai báo quyền nó cần và bị chặn nếu thiếu (403). Giao diện chỉ ẩn nút để người dùng khỏi bấm vào thứ chắc chắn bị từ chối.
- **Vai trò cố định trong mã nguồn**, không sửa được trong giao diện. Quy tắc dễ rà soát, có test, không ai nới quyền nhầm. Muốn thêm vai trò thì sửa mã và deploy.
- **Quyền chi tiết, vai trò gộp quyền.** Code kiểm tra quyền, không kiểm tra vai trò.
- **Mặc định chặn.** Một test tự dò mọi endpoint quản trị và fail nếu endpoint nào thiếu khai báo quyền hoặc vai trò nào làm được thứ không được phép.

## 3. Quyền

| Quyền | Cho phép |
|---|---|
| `reports.view` | Xem doanh thu, báo cáo |
| `orders.view` | Xem đơn, thông tin khách, địa chỉ giao |
| `orders.quote` | Báo phí vận chuyển |
| `orders.fulfil` | Đóng gói, gửi, hoàn tất đơn; đổi chi nhánh xuất hàng |
| `orders.cancel` | Hủy đơn **chưa** thanh toán |
| `orders.cancel_paid` | Hủy đơn **đã** thanh toán (tiệm phải tự hoàn tiền) |
| `payments.review` | Xem slip, xác nhận hoặc từ chối thanh toán |
| `catalog.view` | Xem sản phẩm, danh mục, khuyến mãi |
| `catalog.edit` | Thêm, sửa sản phẩm, ảnh, danh mục (không gồm giá) |
| `pricing.manage` | Sửa giá, tạo khuyến mãi và mã giảm giá |
| `coupons.view` | Xem danh sách mã giảm giá và lịch sử dùng |
| `inventory.view` | Xem tồn kho |
| `inventory.adjust` | Nhận hàng, ghi hàng hỏng, kiểm kê, chuyển kho, bật/tắt theo dõi kho |
| `staff.manage` | Quản lý nhân viên, xem nhật ký hoạt động |
| `inventory.receive` *(mới)* | Tạo phiếu nhập kho tổng, quản lý nguồn và mặt hàng kho |
| `inventory.transfer` *(mới)* | Tạo, hủy phiếu chuyển kho tổng → chi nhánh |
| `inventory.receive_transfer` *(mới)* | Xác nhận nhận phiếu chuyển của chi nhánh mình |
| `inventory.receive_return` *(mới)* | Nhận và xử lý phiếu hoàn tại kho tổng |
| `inventory.approve` *(mới)* | Duyệt kiểm kê, sửa sai, xác nhận thay chi nhánh |

## 4. Vai trò

| Quyền | Chủ tiệm | Quản lý | Nhân viên bán hàng | Nhân viên kho | Nhân viên sản phẩm |
|---|:-:|:-:|:-:|:-:|:-:|
| reports.view | ✓ | ✓ | | | |
| orders.view | ✓ | ✓ | ✓ | ✓ | |
| orders.quote | ✓ | ✓ | ✓ | | |
| orders.fulfil | ✓ | ✓ | ✓ | ✓ | |
| orders.cancel | ✓ | ✓ | ✓ | | |
| orders.cancel_paid | ✓ | ✓ | | | |
| payments.review | ✓ | ✓ | ✓ | | |
| catalog.view | ✓ | ✓ | ✓ | ✓ | ✓ |
| catalog.edit | ✓ | ✓ | | | ✓ |
| pricing.manage | ✓ | ✓ | | | |
| coupons.view | ✓ | ✓ | ✓ | | |
| inventory.view | ✓ | ✓ | ✓ | ✓ | ✓ |
| inventory.adjust | ✓ | ✓ | | ✓ | |
| staff.manage | ✓ | | | | |

Lý do các quyết định chính:

- **Nhân viên kho không thấy tiền:** không xem slip, không xác nhận thanh toán, không xem mã giảm giá, không xem doanh thu. Họ vẫn thấy tên, số điện thoại và địa chỉ khách vì cần để giao hàng.
- **Hủy đơn đã trả tiền là quyền riêng:** hủy đơn đã thanh toán tạo nghĩa vụ hoàn tiền (hệ thống không tự hoàn). Chỉ chủ tiệm và quản lý được làm, và luôn ghi nhật ký.
- **Giá tách khỏi nội dung sản phẩm:** người chăm sóc nội dung sửa mô tả, ảnh được nhưng sửa giá thì bị từ chối. Thêm cỡ mới và tạo sản phẩm mới cũng tính là đặt giá nên cần `pricing.manage`.
- **Bán hàng xem được mã giảm giá** để hỗ trợ khách hỏi, nhưng không tạo hay sửa.
- **Chỉ chủ tiệm quản lý nhân viên.** Quản lý không tạo được tài khoản mới hay nâng quyền (tránh leo thang đặc quyền).

## 5. Quản lý tài khoản

- **Tạo:** chủ tiệm nhập tên đăng nhập (a-z, số, `.`, `-`, `_`, 3 đến 30 ký tự), tên hiển thị, vị trí, mật khẩu tạm.
- **Mật khẩu tạm:** nhân viên **bị chặn khỏi mọi chức năng** cho tới khi đổi mật khẩu, ngay lần đăng nhập đầu. Áp dụng cả với tài khoản bị chủ tiệm đặt lại mật khẩu.
- **Quy tắc mật khẩu:** tối thiểu 10 ký tự, không nằm trong danh sách mật khẩu phổ biến, không phải toàn số, không giống tên đăng nhập. Thông báo bằng tiếng Thái.
- **Đổi vị trí:** có hiệu lực **ngay lập tức**, không cần đăng nhập lại.
- **Khóa tài khoản:** người đó bị đẩy ra ngay (không đợi hết phiên). Lịch sử họ đã làm vẫn giữ nguyên. Không xóa tài khoản.
- **Đặt lại mật khẩu:** đăng xuất người đó khỏi mọi thiết bị và buộc đặt mật khẩu mới.
- **Tự đổi mật khẩu:** cần nhập mật khẩu hiện tại (nhập sai bị giới hạn như đăng nhập sai); thiết bị khác bị đăng xuất, thiết bị đang dùng giữ nguyên.
- **Chống tự khóa mình:** chủ tiệm không tự đổi vị trí, tự khóa, hay tự đặt lại mật khẩu qua màn quản lý. **Luôn còn ít nhất 1 chủ tiệm** đang hoạt động.
- **Đăng nhập:** mật khẩu đúng vẫn chưa đủ; tài khoản phải đang hoạt động và có vị trí. Tài khoản `createsuperuser` tính là chủ tiệm.

## 6. Nhật ký hoạt động

Chủ tiệm xem ở tab "ประวัติการใช้งาน": thời gian, người làm, việc, đối tượng, chi tiết, địa chỉ IP. Ghi lại:

| Việc | Ghi gì |
|---|---|
| Thêm/sửa/khóa nhân viên, đặt lại mật khẩu, đổi mật khẩu | Ai, đối tượng nào, đổi gì |
| Sửa giá, thêm cỡ, tạo sản phẩm | Giá cũ → giá mới từng SKU |
| Tạo/sửa/đóng/xóa khuyến mãi và mã giảm giá | Tên và mức giảm |
| Hủy đơn đã thanh toán | Số đơn và trạng thái trước khi hủy |

Nhật ký chỉ thêm, không có chức năng sửa hay xóa trong ứng dụng. Xác nhận thanh toán, đổi trạng thái đơn và thay đổi tồn kho đã có lịch sử riêng (nhật ký đơn và sổ kho).

## 7. Dữ liệu hiện có khi nâng cấp

Migration tự cấp vai trò cho người dùng nhân viên cũ để không ai bị khóa ngoài: superuser thành **chủ tiệm**, nhân viên khác thành **quản lý** (đúng với quyền họ có trước đây, trừ quản lý nhân viên). Chủ tiệm nên rà lại và hạ quyền nếu cần.

## 8. ผู้จัดการสาขา và phạm vi theo kho *(đã chốt, chưa triển khai)*

Nguồn: `inventory.md` mục 16, quyết định D12, D25, D32–D34.

### 8.1 Vai trò mới: ผู้จัดการสาขา (`branch_manager`)

- Gắn với **đúng một** chi nhánh (không phải kho tổng). Mỗi chi nhánh có 1–2 người. Mỗi người một tài khoản riêng.
- Là người **duy nhất ở chi nhánh** được xác nhận nhận hàng từ kho tổng.

| Quyền | ผู้จัดการสาขา | Phạm vi |
|---|:-:|---|
| reports.view | | |
| orders.view | ✓ | Chỉ đơn nhận tại chi nhánh mình |
| orders.quote | | |
| orders.fulfil | ✓ | Chỉ đơn nhận tại chi nhánh mình: chuẩn bị, giao cho khách |
| orders.cancel, orders.cancel_paid | | |
| payments.review | | Không xác nhận thanh toán (D33) |
| catalog.view | ✓ | |
| catalog.edit, pricing.manage, coupons.view | | |
| inventory.view | ✓ | Chỉ chi nhánh mình |
| inventory.adjust | ✓ | Chỉ chi nhánh mình: ghi hỏng, เบิกใช้, หมดหน้าร้าน, hạn mức online, ngưỡng |
| inventory.receive_transfer | ✓ | Chỉ phiếu gửi tới chi nhánh mình; tạo phiếu hoàn chủ động |
| inventory.receive, transfer, receive_return, approve | | |
| staff.manage | | |

### 8.2 Quyền kho mới cho các vai trò hiện có

| Quyền | Chủ tiệm | Quản lý | Bán hàng | Kho | Sản phẩm |
|---|:-:|:-:|:-:|:-:|:-:|
| inventory.receive | ✓ | ✓ | | | |
| inventory.transfer | ✓ | ✓ | | ✓ | |
| inventory.receive_transfer | ✓ (thay) | ✓ (thay) | | | |
| inventory.receive_return | ✓ | ✓ | | ✓ | |
| inventory.approve | ✓ | ✓ | | | |

- "(thay)": chủ tiệm và quản lý chung xác nhận thay chi nhánh được, **bắt buộc ghi lý do**, nhật ký ghi "xác nhận thay" (D25).
- Nhân viên bán hàng **không** xác nhận nhận hàng (D12).

### 8.3 Phạm vi theo kho

- Chủ tiệm và quản lý chung: mọi kho.
- Các vai trò khác được **gán một hoặc nhiều kho** khi tạo/sửa nhân viên. ผู้จัดการสาขา: đúng một chi nhánh (D34).
- Mọi API kho kiểm tra **cả quyền lẫn kho**: có quyền nhưng sai kho thì 403. Danh sách (tồn, sổ, phiếu, đơn nhận tại tiệm) tự lọc theo kho được gán.
- Đổi kho được gán có hiệu lực ngay, giống đổi vai trò.
- Nhật ký hoạt động ghi thêm thay đổi kho được gán.
- Test: ma trận quyền mở rộng thêm chiều "kho"; mỗi endpoint kho có test "đúng quyền, sai kho → 403".

## 9. Chưa làm (đề xuất)

1. ~~Giới hạn theo chi nhánh~~ đã chốt, xem mục 8 (làm cùng giai đoạn 2 kho).
2. **Xác thực hai bước (2FA)** cho chủ tiệm và quản lý.
3. **Đăng nhập bằng LINE** thay mật khẩu.
4. **Nhật ký đăng nhập** (thành công và thất bại, theo thiết bị) và cảnh báo đăng nhập lạ.
5. **Vai trò tùy chỉnh** chỉnh được trong giao diện (hiện cố định trong mã nguồn có chủ đích).
6. **Phê duyệt hai người** cho việc nhạy cảm (ví dụ giảm giá lớn, hủy đơn đã trả tiền có giá trị cao).
7. **Mở rộng nhật ký** cho cả xác nhận thanh toán và thay đổi tồn kho trong cùng một màn hình.
