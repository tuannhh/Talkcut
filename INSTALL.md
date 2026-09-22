# Cài đặt TalkCut Studio trên Windows

Hướng dẫn cài TalkCut Studio lên máy Windows ở nhà. Toàn bộ ứng dụng chạy trong
Docker nên **không cần cài Python / Node / FFmpeg** — chỉ cần Docker Desktop.

Có 2 cách. Nếu chỉ muốn thử nhanh tối nay → dùng **Cách 1** (bộ cài dựng sẵn).

---

## Bước 0 — Cài Docker Desktop (bắt buộc, làm 1 lần)

1. Tải **Docker Desktop for Windows**: https://www.docker.com/products/docker-desktop/
2. Cài đặt, chọn backend **WSL 2** (mặc định). Nếu Windows nhắc bật WSL2, làm theo
   rồi khởi động lại máy.
3. Mở Docker Desktop, chờ tới khi góc dưới bên trái báo **"Engine running"**.

> Máy cần khoảng **8 GB RAM** trở lên và ~10 GB trống trên ổ đĩa.

---

## Cách 1 — Bộ cài dựng sẵn (nhanh, khuyên dùng để thử tối nay)

Cách này dùng image đã build sẵn nên **không phải chờ build ~20 phút**.

Bạn cần copy về máy nhà **thư mục bộ cài** gồm các file/thư mục sau (lấy từ thư
mục dự án hiện tại):

```
start.bat
stop.bat
compose.yaml
compose.gpu.yaml
.env.example
scripts\start.ps1
talkcut-images.tar.gz        <-- file image ~2GB (nằm trong thư mục dist\)
```

> `talkcut-images.tar.gz` nằm ở `dist\talkcut-images.tar.gz`. Copy nó ra **cùng
> cấp** với `start.bat` (thư mục gốc bộ cài), đừng để trong `dist\`.

Các bước ở máy nhà:

1. Copy cả thư mục bộ cài (kèm file `.tar.gz`) vào máy, ví dụ `C:\TalkCut`.
2. Nhấp đúp **`start.bat`**.
3. Lần đầu, script sẽ tạo file `.env` và **mở Notepad** — dán **GEMINI_API_KEY**
   của bạn vào dòng `GEMINI_API_KEY=`, lưu lại (Ctrl+S), đóng Notepad, quay lại
   cửa sổ đen nhấn **Enter**.
4. Script tự nạp image (~vài phút cho lần đầu), tự phát hiện GPU, rồi mở trình
   duyệt tại **http://localhost:8092**.

Xong. Những lần sau chỉ cần nhấp `start.bat` là chạy ngay.

---

## Cách 2 — Dựng từ mã nguồn (không cần chép file 2GB)

Dùng khi máy nhà có internet và bạn muốn tải mã nguồn về build tại chỗ.

1. Cài **Git for Windows**: https://git-scm.com/download/win
2. Mở PowerShell / Git Bash, tải mã nguồn:
   ```bash
   git clone https://github.com/tuannhh/Talkcut.git
   cd Talkcut
   ```
3. Nhấp đúp **`start.bat`** (hoặc chạy `scripts\start.sh` trong Git Bash).
4. Điền `GEMINI_API_KEY` vào `.env` như Cách 1.
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
