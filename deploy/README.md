# Triển khai Maehai bằng Docker

Một máy chủ, một tên miền, một lệnh. Toàn bộ hệ thống chạy trong Docker Compose:

| Service | Vai trò |
|---|---|
| `web` | Caddy: HTTPS tự động (Let's Encrypt), phục vụ trang admin, chuyển tiếp các đường còn lại |
| `shop` | Website bán hàng (Next.js) |
| `api` | Django API (gunicorn, 3 worker) |
| `worker` | Gửi tin LINE trong hàng đợi. **Không chạy thì không ai nhận được thông báo** |
| `scheduler` | Hủy đơn quá hạn chưa thanh toán (mỗi giờ) để trả hàng về kho |
| `migrate` | Chạy migration database rồi thoát, trước khi `api` khởi động |
| `db` | PostgreSQL 16 |
| `redis` | Bộ đếm giới hạn tần suất (rate limit) dùng chung giữa các worker |

Đường dẫn trên tên miền:

| URL | Đi tới |
|---|---|
| `/` | Website bán hàng |
| `/admin` | Trang quản trị |
| `/api/…` | API |
| `/django-admin/` | Django admin (tạo tài khoản nhân viên, xem hàng đợi LINE) |
| `/media/products/…` | Ảnh sản phẩm (công khai) |
| `/media/…` còn lại | **Luôn 404**. Ảnh slip chuyển khoản không bao giờ được phục vụ công khai; nhân viên xem slip qua `/api/admin/payments/<id>/slip` (phải đăng nhập) |

## Yêu cầu

- Máy chủ Linux có Docker Engine 24+ và Docker Compose v2. 2 GB RAM là đủ cho một cửa hàng.
- Một tên miền (ví dụ `maehai.example.com`) có bản ghi DNS `A` trỏ về IP máy chủ.
- Cổng 80 và 443 mở ra Internet (Caddy cần cả hai để xin chứng chỉ HTTPS).

## Cài đặt lần đầu

```bash
git clone https://github.com/Liamtran1997/Maehai.git /srv/maehai
cd /srv/maehai
cp deploy/.env.example deploy/.env
```

Sửa `deploy/.env`:

1. `SITE_ADDRESS`, `PUBLIC_HOST`: tên miền, ví dụ `maehai.example.com`. `PUBLIC_ORIGIN`: `https://maehai.example.com`.
2. `DJANGO_SECRET_KEY` và `POSTGRES_PASSWORD`: mỗi cái chạy `openssl rand -hex 32` một lần rồi dán vào. API **từ chối khởi động** nếu khóa bí mật thiếu hoặc ngắn hơn 32 ký tự.
3. `PROMPTPAY_ID`: số điện thoại hoặc mã số thuế nhận PromptPay của tiệm. Thiếu thì khách không thanh toán được.
4. Các biến LINE (xem mục LINE bên dưới). Có thể để trống lúc đầu: tin nhắn sẽ được đánh dấu "bỏ qua" chứ không dồn lại.

Khởi động:

```bash
docker compose -f deploy/docker-compose.yml --env-file deploy/.env up -d --build
```

Lần build đầu mất vài phút. Kiểm tra:

```bash
docker compose -f deploy/docker-compose.yml --env-file deploy/.env ps
curl https://maehai.example.com/api/health
```

Nạp dữ liệu ban đầu và tạo tài khoản quản trị:

```bash
alias dc='docker compose -f deploy/docker-compose.yml --env-file deploy/.env'
dc exec api python manage.py seed_shipping      # các cách nhận hàng của tiệm
dc exec api python manage.py seed_inventory     # 2 chi nhánh, gắn với cách nhận tại tiệm
dc exec api python manage.py seed_catalog       # 22 sản phẩm từ site cũ. GIÁ LÀ GIÁ MẪU, phải sửa trong admin
dc exec api python manage.py createsuperuser    # tài khoản đăng nhập /admin
```

`seed_catalog` là tùy chọn. Nếu nhập sản phẩm tay trong `/admin` thì bỏ qua.

## Cập nhật phiên bản mới

```bash
cd /srv/maehai
deploy/backup.sh          # luôn sao lưu trước
git pull
dc up -d --build
```

`migrate` tự chạy trước khi `api` mới khởi động. Nếu migration lỗi, `api` cũ không bị thay và lệnh báo lỗi.

## Sao lưu

`deploy/backup.sh [số ngày giữ]` lưu database (`pg_dump`) và toàn bộ file upload (ảnh sản phẩm và slip) vào `deploy/backups/`, xóa bản cũ hơn số ngày giữ (mặc định 14). Chạy hằng ngày bằng cron:

```cron
15 3 * * *  cd /srv/maehai && deploy/backup.sh 14 >> deploy/backups/backup.log 2>&1
```

File backup chứa dữ liệu khách hàng và ảnh slip ngân hàng. Chỉ lưu nơi có kiểm soát quyền truy cập, và nên chép thêm ra ngoài máy chủ (một ổ khác hoặc dịch vụ lưu trữ).

Khôi phục:

```bash
dc stop api worker scheduler shop
dc exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists' < deploy/backups/db-YYYYMMDD-HHMMSS.dump
dc run --rm -T --entrypoint sh api -c 'tar -C /data/media -xzf -' < deploy/backups/media-YYYYMMDD-HHMMSS.tar.gz
dc up -d
```

## LINE

1. Trong LINE Developers, kênh Messaging API của `@maehai`: lấy **Channel secret** và tạo **Channel access token (long-lived)**. Điền `LINE_CHANNEL_SECRET`, `LINE_CHANNEL_ACCESS_TOKEN`.
2. Webhook URL: `https://maehai.example.com/api/line/webhook`, bật **Use webhook**.
3. ID nhóm nhân viên: thêm bot vào nhóm LINE của tiệm, nhắn `/id`, bot trả lại ID. Điền vào `LINE_STAFF_IDS` (nhiều ID cách nhau bằng dấu phẩy).
4. `dc up -d` để áp dụng.

Tin gửi lỗi xem ở `/django-admin/` mục Outbox (có lý do lỗi).

## Vận hành hằng ngày

```bash
dc logs -f api              # log API
dc logs -f worker           # tin LINE đã gửi
dc logs --since 1h web      # log truy cập
dc restart api              # khởi động lại một service
```

## Lưu ý bảo mật

- `deploy/.env` chứa mọi khóa bí mật. Đã bị `.gitignore` chặn, **không bao giờ commit**. Repo GitHub đang public.
- Chỉ Caddy mở cổng ra ngoài. `db`, `redis`, `api`, `shop` chỉ nằm trong mạng nội bộ Docker.
- API tin đúng một lớp proxy (`TRUSTED_PROXY_COUNT=1`, là Caddy) khi xác định IP khách cho rate limit. Nếu đặt thêm proxy/CDN phía trước (ví dụ Cloudflare), tăng số này lên tương ứng, nếu không mọi khách sẽ bị coi là cùng một IP.
- Admin chạy chung tên miền với shop (`/admin`). Nhờ vậy cookie đăng nhập chỉ dùng trong một origin, không cần CORS. Đổi lại, nếu sau này shop bị lỗi XSS thì trang admin cũng chịu ảnh hưởng. Muốn tách hẳn, có thể chuyển admin sang tên miền con riêng.

## Chạy thử trên máy cá nhân (không HTTPS)

Trong `deploy/.env`:

```
SITE_ADDRESS=http://localhost
PUBLIC_HOST=localhost
PUBLIC_ORIGIN=http://localhost:8080
HTTP_PORT=8080
HTTPS_PORT=8443
```

Rồi `dc up -d --build` và mở http://localhost:8080 (shop) và http://localhost:8080/admin.
