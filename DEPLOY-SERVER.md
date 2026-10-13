# Triển khai TalkCut trên máy chủ nội bộ (bản dùng chung)

Tài liệu cho DevOps. Bản máy chủ phục vụ khoảng 20 người, thường 4–5 người dùng
cùng lúc. Mọi xử lý nặng (nhận diện khuôn mặt, dựng video, tạo bản xem trước)
chạy trên máy chủ chỉ có CPU. Người dùng chỉ cần trình duyệt, kể cả trên máy
văn phòng i3/i5 RAM 8 GB.

Bản cá nhân trên máy Windows (INSTALL.md) vẫn dùng như cũ. Bản máy chủ chỉ thêm
lớp cấu hình `compose.server.yaml`.

## 1. Cấu hình máy chủ đề xuất

| | Tối thiểu | Đề xuất (4–5 người cùng lúc) |
|---|---|---|
| CPU | 8 vCPU x86-64 (AVX2) | 16 vCPU |
| RAM | 16 GB | 32 GB |
| Ổ dữ liệu | 1 TB | 2 TB trở lên, SSD hoặc RAID HDD |
| Mạng LAN | 1 Gbps | 1 Gbps |
| Hệ điều hành | Linux có Docker Engine 24+ và Docker Compose v2.20+ | |

Không cần GPU. Cách ước lượng:

- **Dựng clip**: clip 211 giây 1080p dựng mất 127 giây trên i7-12700K (20
  luồng), và 304 giây khi giới hạn 8 luồng/8 GB như máy văn phòng. Bản máy chủ
  dùng preset `veryfast`; trên 60 giây video 1080×1920, khâu nén nhanh hơn
  `fast` 2–2,7 lần (SSIM 0,99 so với `fast`).
- **Nhận diện khuôn mặt** cho một clip 211 giây mất khoảng 63 giây trên
  i7-12700K. Máy chủ tự làm trước cho 6 đoạn AI đề xuất tốt nhất, nên người dùng
  mở clip là có sẵn khung hình.
- **Chuyển lời nói thành chữ** chạy trên Google (Gemini), gần như không tốn CPU
  máy chủ. Buổi livestream 3,9 giờ: khoảng 4 phút nhận dạng giọng nói (48 đoạn
  5 phút chạy song song) và khoảng 1,5 phút AI chọn đoạn.
- **Video 4K/AV1/HEVC**: máy chủ tạo thêm một bản xem trước 1080p H.264 để máy
  văn phòng phát mượt. Khi xuất video vẫn dùng file gốc.

Các con số trên đo trên máy phát triển. Cần đo lại trên máy chủ thật (mục 8).

**Dung lượng.** Mỗi buổi 4K dài 30 phút gồm:

- File gốc: 0,6–20 GB, tùy máy quay.
- Bản xem trước: khoảng 0,7 GB.
- Mỗi clip xuất ra: 30–60 MB cho mỗi phút.

Với 1–2 video mỗi tuần, nên dự trù 1–2 TB mỗi năm nếu không dọn gì.

**Dọn nguồn cũ.** Trong **Thư viện nguồn**, nút **Xóa** trên mỗi nguồn sẽ:

- Hiện dung lượng sẽ được giải phóng trước khi xóa.
- Xóa video gốc, bản xem trước, lời thoại, các clip và khung hình đã tính.
- Mặc định giữ lại các video đã xuất; người dùng có thể chọn xóa luôn.
- Không cho xóa nguồn đang có tác vụ chạy hoặc đang chờ.

Nên nhắc người dùng xóa nguồn khi đã xuất xong clip.

## 2. Yêu cầu mạng

- Máy chủ cần ra Internet qua HTTPS tới `generativelanguage.googleapis.com`
  (Gemini). Nếu nhập video từ YouTube thì cần thêm `*.youtube.com` và
  `*.googlevideo.com`. Nếu bắt buộc đi qua proxy, thêm vào `.env` cả hai dòng
  `HTTPS_PROXY=...` và `NO_PROXY=face-engine,localhost,127.0.0.1`.
- Người dùng chỉ truy cập qua reverse proxy HTTPS (mục 4). Cổng 8092 của
  container chỉ mở trên `127.0.0.1`.

## 3. Cài đặt

```bash
git clone https://github.com/<tổ-chức>/Talkcut.git /opt/talkcut
cd /opt/talkcut
cp .env.example .env
```

Sửa `.env`:

```ini
GEMINI_API_KEY=<key do MISA cấp>
TALKCUT_ALLOWED_ORIGINS=https://talkcut.misa.local
# Video nguồn có thể tới vài chục GB khi là file gốc 4K
MAX_UPLOAD_GB=40
# Tài khoản quản trị đầu tiên (chỉ dùng khi chưa có tài khoản nào).
# Lần đăng nhập đầu sẽ bắt đổi mật khẩu; sau đó xóa hai dòng này.
TALKCUT_ADMIN_USERNAME=quantri
TALKCUT_ADMIN_PASSWORD=<mật khẩu tạm, ít nhất 8 ký tự>
# Thư mục dữ liệu trên ổ lớn (tùy chọn; mặc định dùng Docker volume)
DATA_PATH=/srv/talkcut-data
# Thư mục chung chỉ-đọc để chọn video có sẵn (tùy chọn)
SOURCE_DIR=/mnt/video-share
```

Nếu dùng `DATA_PATH`, hai container chạy bằng uid 10001:

```bash
sudo mkdir -p /srv/talkcut-data && sudo chown 10001:10001 /srv/talkcut-data
```

Khởi động:

```bash
docker compose -f compose.yaml -f compose.server.yaml up -d --build
docker compose -f compose.yaml -f compose.server.yaml ps
curl -s http://127.0.0.1:8092/api/health
```

Kết quả `/api/health` phải có `"auth_enabled":true` và
`"google_configured":true`.

Để đỡ phải gõ `-f ... -f ...` mỗi lần, có thể thêm dòng sau vào `.env`:

```ini
COMPOSE_FILE=compose.yaml:compose.server.yaml
```

Từ đó chỉ cần `docker compose up -d`. Các lệnh bên dưới viết theo cách này.

## 4. Reverse proxy HTTPS (nginx)

```nginx
server {
    listen 80;
    server_name talkcut.misa.local;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name talkcut.misa.local;
    ssl_certificate     /etc/ssl/talkcut/fullchain.pem;
    ssl_certificate_key /etc/ssl/talkcut/privkey.pem;

    # Video nguồn được gửi thành từng mảnh 8 MB; logo, nhạc, intro tới 1 GB.
    client_max_body_size 1100m;
    proxy_request_buffering off;
    # Video xem trước phát theo Range, không đệm qua nginx.
    proxy_buffering off;
    proxy_read_timeout 600s;
    proxy_send_timeout 600s;

    location / {
        proxy_pass http://127.0.0.1:8092;
        proxy_http_version 1.1;
        proxy_set_header Host $http_host;
        proxy_set_header X-Forwarded-Host $http_host;
        proxy_set_header X-Forwarded-Proto $scheme;
        # Ghi đè (không nối thêm) để người dùng không giả được địa chỉ IP.
        proxy_set_header X-Forwarded-For $remote_addr;
    }
}
```

Lưu ý:

- **Cookie phiên** là HttpOnly và SameSite=Lax. Khi proxy gửi
  `X-Forwarded-Proto: https`, cookie tự bật Secure.
- **Địa chỉ trang** dùng ở `TALKCUT_ALLOWED_ORIGINS` phải trùng với địa chỉ
  người dùng gõ trên trình duyệt. Mọi thao tác ghi đến từ trang khác đều bị chặn.
- **Không có proxy:** nếu cần mở thẳng cổng (`BIND_ADDRESS=0.0.0.0`), đặt
  `FORWARDED_ALLOW_IPS=127.0.0.1` để không tin header chuyển tiếp từ người
  dùng. Chỉ làm vậy trong mạng nội bộ, vì khi đó không có HTTPS.

## 5. Tài khoản

Quản trị viên đăng nhập, bấm vào tên mình ở góc dưới bên trái, chọn **Quản lý
tài khoản**. Ở đó có thể:

- Cấp tài khoản mới.
- Đặt lại mật khẩu.
- Khóa hoặc mở khóa tài khoản.
- Đổi vai trò (Biên tập viên / Quản trị viên).

Mật khẩu tạm chỉ hiện một lần. Người dùng phải đổi mật khẩu ở lần đăng nhập đầu.

Lệnh cứu hộ trên máy chủ, ví dụ khi quên mật khẩu quản trị:

```bash
docker compose exec studio python -m backend.auth list
docker compose exec studio python -m backend.auth create-admin <tên>
docker compose exec studio python -m backend.auth reset-password <tên>
```

Bảo mật đăng nhập:

- Mật khẩu lưu bằng scrypt; phiên đăng nhập kéo dài 14 ngày.
- Sai 5 lần từ một địa chỉ, hoặc 20 lần cho một tên trên mọi địa chỉ, thì phải
  chờ 15 phút.
- Khóa tài khoản hoặc đặt lại mật khẩu sẽ đăng xuất mọi phiên của người đó.

Phân quyền:

- Mọi người cùng thấy kho nguồn và clip của nhóm.
- Chỉ người tạo hoặc quản trị viên được xóa nguồn video, video đã xuất, mẫu
  thương hiệu và tác vụ. Khi người tải nguồn lên xóa nguồn, video do người
  khác xuất từ nguồn đó vẫn được giữ.
- Chỉ quản trị viên được đổi cấu hình tăng tốc phần cứng.

## 6. Tinh chỉnh tài nguyên (trong `.env`)

| Biến | Mặc định máy chủ | Ý nghĩa |
|---|---|---|
| `RENDER_WORKERS` | 2 | Số video được dựng cùng lúc |
| `RENDER_THREADS` | 6 | Số luồng ffmpeg cho mỗi lần dựng |
| `RENDER_PRESET` | veryfast | Preset x264 khi xuất (`fast` nét hơn chút, chậm hơn 2–2,7 lần) |
| `FRAMING_WORKERS` | 2 | Số clip được tính khung hình (nhận diện người) cùng lúc |
| `FACE_ENGINE_WORKERS` | 3 | Tiến trình nhận diện khuôn mặt |
| `INGEST_WORKERS` | 1 | Nhập nguồn và tạo bản xem trước |
| `AI_WORKERS` | 2 | Phân tích nội dung bằng Gemini (chủ yếu chờ mạng) |
| `STT_PARALLEL` | 4 | Số đoạn 5 phút gửi nhận dạng giọng nói cùng lúc |
| `PREPARE_FRAMING_TOP` | 6 | Số đoạn AI đề xuất được làm sẵn khung hình (0 = tắt) |
| `PREVIEW_PROXY` | auto | Tạo bản xem trước 1080p cho 4K/AV1/HEVC (`off` = tắt) |
| `STUDIO_MEMORY` / `FACE_ENGINE_MEMORY` | 20g / 6g | Giới hạn RAM của từng container |

Quy tắc chọn số:

- Tổng `RENDER_WORKERS × RENDER_THREADS` cộng `FACE_ENGINE_WORKERS` nên xấp xỉ
  số vCPU.
- Máy 8 vCPU / 16 GB: `RENDER_WORKERS=1`, `RENDER_THREADS=6`,
  `FRAMING_WORKERS=1`, `FACE_ENGINE_WORKERS=2`, `STUDIO_MEMORY=10g`,
  `FACE_ENGINE_MEMORY=4g`.
- Sau khi sửa, chạy `docker compose up -d` để áp dụng.

**Hàng đợi.** Tác vụ được chia thành bốn làn: dựng, khung hình, nhập nguồn và AI.
Nhờ vậy một buổi talkshow dài đang nhận dạng giọng nói không chặn video người
khác đang chờ dựng. Thẻ tác vụ hiện vị trí trong hàng và tên người tạo.

## 7. Sao lưu

Dữ liệu nằm hết trong `/data`: thư mục `DATA_PATH`, hoặc volume
`talkcut-studio_studio-data`. Trong đó gồm:

- `studio.sqlite`: tài khoản, nguồn, clip, tác vụ.
- Thư mục `sources/`, `renders/`, `assets/`.

Sao lưu cơ sở dữ liệu an toàn ngay cả khi đang chạy (nên đặt cron hằng ngày):

```bash
docker compose exec -T studio python -c "import sqlite3,datetime,pathlib; pathlib.Path('/data/backups').mkdir(exist_ok=True); sqlite3.connect('/data/studio.sqlite').backup(sqlite3.connect('/data/backups/studio-'+datetime.date.today().isoformat()+'.sqlite'))"
```

Rồi chép `/data/backups`, `sources/`, `renders/` và `assets/` sang nơi lưu trữ
khác (rsync hằng tuần là đủ).

Để khôi phục:

1. Dừng dịch vụ.
2. Chép file sao lưu thành `/data/studio.sqlite` và xóa `studio.sqlite-wal`,
   `studio.sqlite-shm` cũ.
3. Khởi động lại.

## 8. Kiểm tra sau triển khai

1. Mở `https://talkcut.misa.local`, đăng nhập bằng tài khoản quản trị tạm, đổi
   mật khẩu, rồi cấp một tài khoản biên tập viên.
2. Tải lên một video dài khoảng 30 phút. Có thể thử ngắt mạng giữa chừng: chọn
   lại đúng file đó thì quá trình tải chạy tiếp từ chỗ dừng.
3. Bấm phân tích và ghi thời gian. Mở một đoạn AI đề xuất, xuất video, rồi ghi
   thời gian dựng.
4. Cho 4–5 người cùng xuất clip. Theo dõi tải bằng `docker stats`, và chỉnh
   các biến ở mục 6 nếu RAM hoặc CPU chạm trần.

## 9. Nâng cấp và quay lui

```bash
cd /opt/talkcut
git fetch --tags
# Đợi hàng đợi trống (không còn tác vụ đang chạy), sao lưu như mục 7, rồi:
git checkout <phiên bản, ví dụ v0.13.0>
docker compose up -d --build
```

Để quay lui:

1. `git checkout` phiên bản cũ rồi chạy lại lệnh trên.
2. Nếu bản cũ không chạy đúng với dữ liệu mới, khôi phục bản sao lưu đã tạo
   trước khi nâng cấp (mục 7).

Danh sách phiên bản và trạng thái (RC hay ổn định) xem ở
`memory-bank/releases.md`.

Chỉ nên đưa lên máy chủ thật những bản đã được xác nhận ổn định.
