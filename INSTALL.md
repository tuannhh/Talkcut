# Cài đặt TalkCut Studio trên Windows

Hướng dẫn cài TalkCut Studio lên máy Windows ở nhà. Toàn bộ ứng dụng chạy trong
Docker nên **không cần cài Python / Node / FFmpeg** — chỉ cần Docker Desktop.

Có 3 cách. Đơn giản nhất → **Cách 1** (bộ cài một file `.exe`, có shortcut).

---

## Bước 0 — Cài Docker Desktop (bắt buộc, làm 1 lần)

1. Tải **Docker Desktop for Windows**: https://www.docker.com/products/docker-desktop/
2. Cài đặt, chọn backend **WSL 2** (mặc định). Nếu Windows nhắc bật WSL2, làm theo
   rồi khởi động lại máy.
3. Mở Docker Desktop, chờ tới khi góc dưới bên trái báo **"Engine running"**.

> Máy cần khoảng **8 GB RAM** trở lên và ~10 GB trống trên ổ đĩa. Docker Desktop
> **không nằm trong** bộ cài (giấy phép của Docker không cho đóng gói lại, và
> Docker cần quyền admin + WSL2 khi cài lần đầu). Nếu chưa có Docker, bộ cài
> `.exe` sẽ tự nhắc và mở trang tải Docker chính chủ.

---

## Cách 1 — Bộ cài một file `.exe` (khuyên dùng)

File **`TalkCutStudio-Setup.exe`** (~2GB) đã gói sẵn ứng dụng + image dựng sẵn.

1. Copy `TalkCutStudio-Setup.exe` sang máy, **nhấp đúp** để cài (không cần quyền
   admin — cài vào thư mục người dùng).
2. Cài xong sẽ có **lối tắt "TalkCut Studio"** trên **Desktop** và **Start Menu**.
3. Nhấp đúp lối tắt để chạy. Lần đầu: mở Notepad để dán **GEMINI_API_KEY**, lưu,
   Enter → tự kiểm tra checksum, nạp image, nhận GPU, mở **http://localhost:8092**.
4. Những lần sau chỉ cần nhấp lối tắt là chạy ngay.

> Bộ cài chỉ đặt file + tạo lối tắt. Việc nạp image (~vài phút) diễn ra ở **lần
> chạy đầu tiên** qua lối tắt, cần Docker Desktop đang chạy.

Gỡ cài: **Settings → Apps** (hoặc Start Menu → "Gỡ cài đặt") — chỉ xoá file ứng
dụng, **không** xoá dữ liệu/clip (nằm trong Docker volume).

---

## Cách 2 — Thư mục dựng sẵn (không cần bộ cài `.exe`)

Dùng image đã build sẵn, chạy trực tiếp bằng `start.bat`, không phải build.

Toàn bộ bộ cài đã được đóng gói sẵn trong **một thư mục**:
`dist\talkcut-install\` gồm:

```
start.bat
stop.bat
compose.yaml
compose.gpu.yaml
.env.example
scripts\start.ps1
talkcut-images.tar.gz          <-- image dựng sẵn (~2GB)
talkcut-images.tar.gz.sha256   <-- checksum để tự kiểm tra file khi copy
INSTALL.md
```

Các bước ở máy nhà:

1. Copy **cả thư mục `talkcut-install`** (giữ nguyên cấu trúc, kèm cả 2 file
   `.tar.gz` và `.sha256`) vào máy, ví dụ `C:\TalkCut`.
2. Nhấp đúp **`start.bat`**.
3. Lần đầu, script sẽ tạo file `.env` và **mở Notepad** — dán **GEMINI_API_KEY**
   của bạn vào dòng `GEMINI_API_KEY=`, lưu lại (Ctrl+S), đóng Notepad, quay lại
   cửa sổ đen nhấn **Enter**.
4. Script tự kiểm tra checksum (báo ngay nếu file bị hỏng khi copy), nạp image
   (~vài phút cho lần đầu), tự phát hiện GPU, rồi mở trình duyệt tại
   **http://localhost:8092**.

Xong. Những lần sau chỉ cần nhấp `start.bat` là chạy ngay.

---

## Cách 3 — Dựng từ mã nguồn (không cần chép file 2GB)

Dùng khi máy nhà có internet và bạn muốn tải mã nguồn về build tại chỗ.

1. Cài **Git for Windows**: https://git-scm.com/download/win
2. Mở PowerShell / Git Bash, tải mã nguồn:
   ```bash
   git clone https://github.com/tuannhh/Talkcut.git
   cd Talkcut
   ```
3. Nhấp đúp **`start.bat`** (hoặc chạy `scripts\start.sh` trong Git Bash).
4. Điền `GEMINI_API_KEY` vào `.env` như trên.
5. Lần đầu sẽ **build ~15–20 phút** (biên dịch FFmpeg, tải thư viện CUDA, npm…).
   Các lần sau chạy ngay.

---

## Điền khóa và cấu hình (file `.env`)

`start.bat` tự tạo `.env` từ `.env.example`. Các mục hay dùng:

| Dòng | Ý nghĩa |
|------|---------|
| `GEMINI_API_KEY=` | **Bắt buộc** cho các tính năng AI (bóc lời/STT, TTS, sinh nội dung). Dán khóa Gemini của bạn. |
| `SOURCE_DIR=./sources` | Thư mục video nguồn để duyệt sẵn. Mặc định `./sources` chạy tốt mọi máy. Muốn trỏ nơi khác dùng gạch chéo xuôi: `C:/Users/TênBạn/Videos`. |
| `PORT=8092` | Cổng web. Đổi nếu 8092 đã bị dùng. |
| `RENDER_THREADS=4` | Số luồng render (CPU). |

> Không có `GEMINI_API_KEY` thì phần dựng/ghép video vẫn chạy, nhưng các bước AI
> sẽ báo lỗi cho tới khi bạn điền khóa (rồi chạy lại `start.bat`).

---

## GPU NVIDIA (tùy chọn — nhanh hơn nhiều)

App chạy tốt trên **CPU**. Nếu máy nhà có **card NVIDIA**, có thể bật tăng tốc
GPU (render NVENC + nhận diện khuôn mặt CUDA):

1. Cài **driver NVIDIA mới nhất** cho Windows (bản có hỗ trợ WSL2).
2. Trong **Docker Desktop → Settings → Resources → WSL Integration**: bật.
   Docker Desktop bản mới hỗ trợ GPU qua WSL2 sẵn, không cần cài thêm.
3. Chạy lại `start.bat`. Script tự phát hiện: nếu thấy GPU sẽ báo *"Đã phát hiện
   GPU NVIDIA — bật tăng tốc GPU"*; nếu không, tự chạy CPU (không lỗi).

> Không có GPU cũng không sao — vẫn dùng đầy đủ tính năng, chỉ chậm hơn khi render.

---

## Dùng, tắt, cập nhật

- **Mở lại:** nhấp `start.bat` → tự mở http://localhost:8092
- **Tắt:** nhấp `stop.bat` (dữ liệu vẫn được giữ trong Docker volume).
- **Xem log khi có sự cố:** mở PowerShell tại thư mục bộ cài rồi chạy:
  ```bash
  docker compose logs -f
  ```
- **Cập nhật bản mới:** thay `talkcut-images.tar.gz` mới (Cách 1) hoặc `git pull`
  rồi chạy lại `start.bat` (Cách 2).

---

## Xử lý sự cố thường gặp

| Hiện tượng | Cách xử lý |
|-----------|-----------|
| `start.bat` báo chưa cài Docker | Cài Docker Desktop (Bước 0), mở lên chờ *Engine running*. |
| Cửa sổ đen báo Docker chưa chạy rồi tự chờ | Bình thường — script đang tự bật Docker Desktop, chờ 1–2 phút. |
| Mở http://localhost:8092 chưa lên | Chờ thêm 1–2 phút (lần đầu khởi tạo lâu). Kiểm tra `docker compose logs -f`. |
| Cổng 8092 bận | Sửa `PORT=` trong `.env` sang số khác (vd 8093) rồi chạy lại. |
| Không nhận GPU | Kiểm tra driver NVIDIA + WSL2; nếu vẫn không có vẫn chạy CPU bình thường. |
| Muốn xóa sạch làm lại | `docker compose down -v` (⚠️ xóa cả dữ liệu trong volume). |

---

Nếu kẹt ở bước nào, chụp lại nội dung cửa sổ đen (hoặc `docker compose logs`) để
tiện chẩn đoán.

---

## (Dành cho người build) Đóng gói lại bộ cài

**Tạo bộ cài một file `.exe`** (khuyên dùng) — cài Inno Setup một lần
(`winget install JRSoftware.InnoSetup`), rồi nhấp đúp **`build-installer.bat`** ở
thư mục gốc dự án (tự đóng gói image nếu chưa có; thêm `/build` để build image
trước):

```bat
build-installer.bat          REM tạo dist\TalkCutStudio-Setup.exe (~2GB)
build-installer.bat /build   REM build image từ mã nguồn rồi tạo .exe
```

**Chỉ tạo thư mục dựng sẵn** (không cần Inno Setup) — nhấp đúp **`build-bundle.bat`**:

```bat
build-bundle.bat            REM đóng gói image :latest hiện có -> dist\talkcut-install\
build-bundle.bat /build     REM build image từ mã nguồn rồi đóng gói
```

`build-bundle` cho ra `dist\talkcut-install\` (`.tar.gz` + `.sha256` + launcher +
compose + INSTALL.md). `build-installer` gói chính thư mục đó thành một file `.exe`
kèm lối tắt. File `.exe` và thư mục bundle nằm trong `dist\` (đã bị git bỏ qua).

