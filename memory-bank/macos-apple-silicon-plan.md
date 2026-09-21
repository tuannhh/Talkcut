# Kế hoạch tối ưu TalkCut cho macOS Apple Silicon — đánh giá khả thi, kiến trúc, roadmap

_Ngày lập: 2026-09-21. Trạng thái: **đánh giá + plan, CHƯA implement.** Máy đang làm việc là Windows + RTX 3050, nên mọi phần cần chạy trên phần cứng Apple đều được đánh dấu rõ "cần verify trên Mac thật"._

## 0. TL;DR — kết luận

- **Khả thi và đáng làm.** Nhưng "tăng tốc GPU trong Docker trên Mac" là **bất khả thi về nguyên lý** — Docker Desktop trên Apple Silicon không có đường truyền GPU (Metal/ANE) vào Linux container. Muốn dùng phần cứng Mac thì **phải chạy native trên host**, không qua Docker.
- **Không nên fork sang folder riêng.** Phần code tăng tốc chỉ đụng ~4 file và hoàn toàn additive, gated đúng như đường NVIDIA hiện có. Fork sẽ nhân đôi toàn bộ app và trôi lệch (drift) — lựa chọn kỹ thuật kém. Giữ **một codebase**, thêm một "profile tăng tốc theo nền tảng" + một đường chạy native cho Mac.
- **Thắng lợi lớn nhất, chắc chắn nhất trên Mac không phải GPU mà là chạy native**: thoát khỏi thuế ảo hoá của Docker VM + dùng **VideoToolbox** cho render. Đây là phần rủi ro thấp.
- **CoreML/Apple Neural Engine cho face-engine là phần "verify rồi mới chốt"**: có triển vọng nhưng expose qua onnxruntime-node còn mơ hồ; kể cả nếu không dùng được, CPU native trên M-series (ARM NEON) vẫn nhanh hơn hẳn CPU-trong-Docker.

## 1. Ràng buộc nền tảng (nền tảng của mọi quyết định)

**Docker trên Apple Silicon = CPU-only, không có ngoại lệ.**
- Metal cần truy cập phần cứng trực tiếp; không có GPU passthrough vào container. `Hypervisor.framework` của macOS chưa cung cấp virtual GPU. Đây là giới hạn nền tảng, chưa được giải quyết tính đến 2025/2026.
- Chính Docker cũng đi đường này: Docker Model Runner / vLLM-metal **chạy native trên host**, không passthrough. Đây là pattern chuẩn của cả ngành.
- Hệ quả trực tiếp cho TalkCut: đường `compose.gpu.yaml` (device reservation NVIDIA) **không có ý nghĩa gì trên Mac**. Trên Mac, `docker compose up` sẽ luôn là CPU-only và còn gánh thêm chi phí ảo hoá (CPU + filesystem của Docker VM).

Nguồn: xem mục 9.

**Hệ quả kiến trúc:** để tối ưu Mac, ta cần một **đường chạy native** (Python + Node + ffmpeg chạy thẳng trên macOS), song song với đường Docker hiện có (vẫn dùng cho Linux/Windows/NVIDIA và cho người dùng Mac không muốn cài native).

## 2. Các lựa chọn tăng tốc trên Apple Silicon

| Hạng mục | Cơ chế Apple | Đường hiện tại (NVIDIA) | Ghi chú |
|---|---|---|---|
| **Render (encode/decode)** | **VideoToolbox** — `h264_videotoolbox` / `hevc_videotoolbox`, decode `-hwaccel videotoolbox`. Chạy trên media engine chuyên dụng của SoC. | NVENC / NVDEC | ffmpeg Homebrew có sẵn videotoolbox. Rock-solid. |
| **Nhận diện khuôn mặt (SCRFD + ArcFace ONNX)** | **CoreML EP** của onnxruntime → chọn Apple Neural Engine / GPU / CPU. | CUDA EP của onnxruntime-node | Rủi ro: expose qua Node chưa chắc chắn (mục 5). |
| **CPU nền** | onnxruntime CPU EP dùng ARM NEON; M-series CPU rất mạnh | libx264 + onnxruntime CPU | Ngay cả khi bỏ hết GPU, native CPU vẫn hơn Docker CPU. |

Điểm mấu chốt: **VideoToolbox** giải quyết phần render (phần nặng nhất, đã đo được ~1.9x nhờ NVENC trên clip 4K). **CoreML** giải quyết phần face-engine. Hai phần độc lập nhau → có thể làm và nghiệm thu riêng.

## 3. Đánh giá khả thi từng phần

| Thành phần | Khả thi | Công sức | Rủi ro |
|---|---|---|---|
| Chạy native (thoát Docker VM) | **Cao** | Trung bình (script launcher + tài liệu) | Thấp — chỉ là chạy sẵn các process trên host |
| Render qua VideoToolbox | **Cao** | Thấp (~1 file + detection) | Thấp — cần tinh chỉnh bitrate/chất lượng như đã làm với NVENC |
| Face-engine qua CoreML/ANE (Node) | **Trung bình** | Thấp về code, **cao về verify** | onnxruntime-node có expose 'coreml' EP trên darwin-arm64 không? Bao nhiêu op fallback về CPU? |
| Đóng gói `.app` để phát hành | **Trung bình** | Cao | Bundle node + ffmpeg + python; ký (codesign)/notarize |

## 4. Khuyến nghị kiến trúc

### 4.1 Một codebase, KHÔNG fork (khuyến nghị chính)

Phần tăng tốc đã được trừu tượng hoá sẵn từ đợt NVIDIA:
- `backend/media.py` — `_accel_enabled()`, `hwaccel_input_args()`, nhánh trong `encode_args()`.
- `backend/gpu_profile.py` — dò phần cứng + khả năng ffmpeg.
- `face-engine/face.js` / `gpu.js` — `cudaProviders()` + fallback try/catch.

Việc thêm Apple Silicon chỉ là thêm **một nhánh backend nữa** (`videotoolbox` cho render, `coreml` cho ONNX) vào đúng các điểm gated này. Đây là lý do fork là lựa chọn tệ: sẽ copy 95% code giống hệt rồi để hai bản trôi lệch — bất kỳ ai audit cũng sẽ phê bình. Deployment tuy khác (Docker vs native) nhưng **logic tăng tốc thì thống nhất được**.

Mô hình đề xuất: khái quát khái niệm "GPU" hiện tại thành **"render backend"** = một trong `{nvenc, videotoolbox, cpu}`, và **"inference backend"** = một trong `{cuda, coreml, cpu}`. Lớp detect chọn backend theo nền tảng; phần còn lại của app không cần biết.

### 4.2 Lựa chọn táo bạo hơn (cân nhắc, không bắt buộc): gộp face-engine vào backend Python

Tài liệu ONNX Runtime xác nhận **wheel Python macOS chính thức có sẵn CoreML EP** (mảng Python trưởng thành hơn Node ở khoản CoreML). Backend đã là Python. Nếu đường CoreML qua Node **không** verify được, phương án tối ưu dài hạn có thể là chuyển suy luận khuôn mặt vào backend Python dùng `onnxruntime` (CoreML trên Mac, CUDA trên NVIDIA, CPU nơi khác) — **gộp về một ngôn ngữ, một service, CoreML hạng nhất**. Đánh đổi: đây là refactor lớn (viết lại toàn bộ SCRFD/ArcFace pre/post-processing từ JS sang Python), và làm Windows/Linux cũng đổi theo. **Chỉ nên làm nếu bước verify ở mục 5 thất bại.**

## 5. Điểm PHẢI verify trên máy Mac thật (không làm được ở session Windows này)

1. **onnxruntime-node có nhận `executionProviders: ['coreml','cpu']` trên darwin-arm64 không, và có thật sự chạy trên ANE/GPU không (hay âm thầm fallback CPU)?** Đây là rủi ro số một. Cách kiểm: tạo session với 'coreml', chạy SCRFD/ArcFace, đo thời gian + quan sát `powermetrics`/Activity Monitor xem ANE/GPU có tải không.
2. **Bao nhiêu op của SCRFD/ArcFace được CoreML nhận, bao nhiêu fallback CPU** (dựng `MLComputeUnits`, xem log partition của CoreML EP).
3. **Chất lượng & bitrate của `h264_videotoolbox`** so với libx264 crf18 (lặp lại đúng bài học NVENC: hardware encoder kém bit-efficient, phải cap bitrate).
4. **Tốc độ thực tế** render + face-engine trên 1 clip 4K thật, so CPU-native vs VideoToolbox+CoreML.

## 6. Phạm vi thay đổi code (chính xác theo file)

**Tăng tốc (thống nhất trong codebase hiện tại):**
- `backend/gpu_profile.py`: thêm `detect_apple_silicon()` (qua `platform.system()=='Darwin'` + `platform.machine()=='arm64'`, số core/RAM qua `sysctl`); mở rộng `ffmpeg_capabilities()` để dò `videotoolbox` trong `-hwaccels` và `h264_videotoolbox` trong `-encoders`.
- `backend/media.py`: thêm nhánh `videotoolbox` vào `hwaccel_input_args()` (`-hwaccel videotoolbox`) và `encode_args()`. Hình dạng đề xuất (chờ tinh chỉnh trên máy thật):
  `['-c:v','h264_videotoolbox','-b:v','6M','-maxrate','9M','-bufsize','12M','-profile:v','high','-allow_sw','1','-pix_fmt','yuv420p','-r','30', ...audio giữ nguyên...]`
- `backend/config.py` / `accel_settings.py` / `schemas.py` / `app.py`: khái quát `render_accel` để hiểu backend Apple; `/api/accel` trả thêm loại backend đang dùng.
- `face-engine/gpu.js`: thêm `detectAppleSilicon()`.
- `face-engine/face.js`: thêm `coremlProviders()` cạnh `cudaProviders()`; `createSession` thử CoreML trên Mac / CUDA trên NVIDIA / fallback CPU (pattern try-catch đã có sẵn).
- `face-engine/pool.js`: trên Apple Silicon chia worker theo performance-core (bộ nhớ hợp nhất), không theo VRAM.
- `frontend/src/main.jsx`: nhãn "Tăng tốc phần cứng" đã data-driven; chỉ cần hiện đúng tên "Apple Silicon (VideoToolbox + Neural Engine)" khi backend là Apple. Thay đổi nhỏ.

**Deployment (phần kiến trúc thật sự):**
- `scripts/run-macos.sh` (mới): kiểm/ cài ffmpeg có videotoolbox (`brew install ffmpeg`); tạo venv + cài `requirements.txt`; `npm ci` trong `face-engine`; `npm run build` frontend; chạy face-engine (127.0.0.1:3210) + uvicorn (8092) với `FACE_ENGINE_URL=http://127.0.0.1:3210`, `RENDER_ACCEL=auto`, `FACE_ENGINE_ACCEL=auto`, `DATA_DIR`/`SOURCE_ROOT` trỏ vào thư mục host.
- `config.py` đã hỗ trợ `DATA_DIR` env (mặc định `ROOT/data`) → native dùng thư mục host, gần như không phải sửa.
- Docker vẫn giữ cho Mac như phương án CPU-only dự phòng (người không muốn cài native).
- Về sau: đóng gói `.app` (PyInstaller/py2app + bundle node + bundle ffmpeg + codesign/notarize) cho người dùng không kỹ thuật.

## 7. Roadmap theo phase

- **Phase 0 — Verify (cần 1 máy Apple Silicon).** Kiểm 4 điểm ở mục 5 bằng script nhỏ, độc lập, trước khi viết code sản phẩm. Đây là cổng quyết định: kết quả CoreML định đoạt chọn 4.1 hay 4.2.
- **Phase 1 — Chạy native + VideoToolbox (thắng lợi chắc chắn).** Launcher native; nhánh videotoolbox cho render; tinh chỉnh bitrate; đo tốc độ. Không phụ thuộc CoreML.
- **Phase 2 — Face-engine CoreML.** Nếu Phase 0 pass: thêm nhánh coreml vào face.js. Nếu fail: kích hoạt phương án 4.2 (đánh giá lại công sức trước khi làm).
- **Phase 3 — Đóng gói & phát hành `.app`** (tuỳ chọn, nếu cần đưa cho người không kỹ thuật).

## 8. Rủi ro & phương án dự phòng

- **CoreML qua Node không expose được** → dùng CPU native (vẫn nhanh hơn Docker) hoặc chuyển sang 4.2 (Python face-engine).
- **Nhiều op fallback CPU khiến CoreML không lời** → chấp nhận CPU native cho face-engine, chỉ lấy VideoToolbox cho render (phần render vẫn là phần nặng nhất).
- **Chất lượng videotoolbox kém** → cap bitrate như NVENC; nếu vẫn kém, để render mặc định libx264 native và chỉ bật videotoolbox khi người dùng chọn.
- **Không có Mac để test** (thực trạng hiện tại) → toàn bộ code có thể viết + kiểm cú pháp trên Windows, nhưng **không nghiệm thu runtime được**; phải có một máy Apple Silicon cho Phase 0.

## 9. Nguồn tham chiếu

- Docker/Apple Silicon không có GPU passthrough: Docker blog "Docker Model Runner Adds vLLM Support on macOS" (chạy native trên host); Red Hat Developer "How we improved AI inference on macOS Podman containers"; apple/container Discussion #62 "GPU passthrough availability?".
- onnxruntime CoreML EP: onnxruntime.ai/docs/execution-providers/CoreML-ExecutionProvider.html — "Official macOS Python wheels include the CoreML EP"; "official macOS arm64 C/C++ / Java / Node.js CPU packaging jobs also pass `--use_coreml`" (biên dịch sẵn) nhưng mục Usage chỉ liệt kê C/C++/Obj-C/C#/Java → expose Node chưa được khẳng định rõ.

## 10. Quyết định cần bạn chốt

1. **Có sẵn/mượn được một máy Apple Silicon để chạy Phase 0 không?** Đây là điều kiện tiên quyết — không có thì mọi thứ dừng ở mức "viết code mù, không nghiệm thu được".
2. **Đồng ý hướng một-codebase (4.1) thay vì fork** không?
3. **Thứ tự git**: nên commit đợt gộp NVIDIA (đã test) vào `main` trước, rồi mới nhánh `macos-apple-silicon` từ đó — để công việc Mac không lẫn với công việc NVIDIA đang dang dở. Chờ bạn xác nhận đã hài lòng với bản NVIDIA để tôi commit trước.
