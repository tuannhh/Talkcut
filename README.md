# TalkCut Studio

Ứng dụng cá nhân biến video tọa đàm thành nhiều clip dọc. Giao diện tiếng Việt, chạy Docker, sử dụng Google API. Không áp dụng MISA Design System hoặc MISA Backend Standards.

## Mở ứng dụng

Trên máy đã cài đặt: **http://localhost:8092**.

```sh
cp .env.example .env
# Điền GEMINI_API_KEY và SOURCE_DIR trong .env
./scripts/start.sh
```

Nếu `.env` đã tồn tại, giữ nguyên file và chạy `./scripts/start.sh`. Docker Desktop cần đang chạy. Dữ liệu nằm trong Docker volume `talkcut-studio_studio-data`, được giữ khi khởi động lại hoặc build lại. Cổng chỉ mở trên máy local. Không chạy nhiều worker Uvicorn cho phiên bản này.

Các model mặc định:

| Công việc | Model / công cụ |
|---|---|
| Chọn đoạn, viết tiêu đề và tóm tắt, hiểu video, bố trí intro | `gemini-3.8-flash` |
| Nhận dạng nguyên văn, phân biệt giọng nói, mốc từng từ | `gemini-3.5-transcribe` |
| Giọng đọc intro tiếng Việt | `gemini-3.1-flash-tts-preview` |
| Đối chiếu nội dung theo yêu cầu | Google Search grounding qua Gemini |
| Hiệu chỉnh vị trí khuôn mặt | OpenCV, xử lý local |
| Crop, karaoke, ghép video, nhạc và watermark | FFmpeg + libass |

Key đặt trong `.env`, chỉ đọc ở backend. File này bị loại khỏi Git, Docker build context và gói ZIP mã nguồn. Không cần nhập lại key trong trình duyệt. Nội dung âm thanh, proxy video và ảnh intro được gửi tới Google khi thực hiện chức năng AI tương ứng; file nguồn và bản xuất được lưu local. File audio tạm trên Google được yêu cầu xóa sau nhận dạng.

## Quy trình sử dụng

1. **Thêm nguồn video** bằng upload, link YouTube hoặc đường dẫn file. Hỗ trợ nguồn ngang và dọc; thư viện giữ nhiều nguồn riêng biệt.
2. **Tìm đoạn hay**: nhập chủ đề, thời lượng tối thiểu/tối đa. Có sẵn gợi ý quản trị, thuế, tài chính hoặc mọi nội dung nổi bật. AI phân tích toàn bộ lời thoại và đề xuất số clip tùy chất lượng nội dung.
3. **Duyệt clip**: nghe đoạn gốc, xem lý do chọn và ghi chú ngữ cảnh. Điểm 0–100 là đánh giá biên tập, không phải cam kết hiệu quả lên kênh. Sửa đầu/cuối clip bằng giây. Khi đổi khoảng cắt, lời thoại trong khoảng mới được tải lại từ transcript nguồn.
4. **Nội dung**: tạo intro từ khung đầu tiên, một trong ba ảnh gợi ý hoặc ảnh upload; crop/di chuyển/phóng ảnh, đặt nền thương hiệu chồng lên phía dưới nếu cần. Sửa hoặc nhờ AI gợi ý tiêu đề, đổi màu/highlight/cỡ/vị trí và viết hoa. Lời mở đầu được đọc bằng voice có sẵn hoặc giọng tạo theo tùy chọn; karaoke intro bật/tắt riêng. Chọn outro tùy ý. Không còn thẻ tóm tắt riêng hoặc đoạn lời dẫn tĩnh trên intro.
5. **Phụ đề**: từng từ sáng theo mốc STT. Đổi màu, cỡ chữ, vị trí và số từ mỗi cụm. Sửa trực tiếp cả ô câu/cụm; giữ mốc phát âm. Chữ thêm dùng chung mốc gần nhất. Bấm thời gian để nghe lại.
6. **Thương hiệu**: tự động bám người nói, căn giữa, crop thủ công hoặc giữ toàn khung. Có phóng khung để căn lại nguồn dọc. Watermark chữ hoặc hình, kéo vị trí và chỉnh độ hiện/kích thước. Chọn nhạc nền; âm lượng tự giảm khi có lời nói. Có thể áp dụng watermark/phụ đề/nhạc/outro hiện tại cho các clip đã chọn.
7. **Lưu**, rồi **Dựng Full HD** hoặc chọn nhiều clip và **Dựng đã chọn**. Mỗi tác vụ chụp lại cấu hình tại thời điểm bắt đầu; việc sửa tiếp không làm thay đổi bản đang dựng.
8. Trong **Video đã xuất**, phát bản hoàn chỉnh rồi tải MP4. Các lần dựng trước được giữ lại.

Google Search là thao tác riêng, có nguồn liên kết. Kết quả đối chiếu không tự sửa lời người nói hoặc chèn vào video. Với nội dung thuế, cần duyệt điều kiện áp dụng, thời điểm và ngoại lệ trong ngữ cảnh gốc.

## Đường dẫn nguồn trong Docker

Ví dụ `.env`:

```dotenv
SOURCE_DIR=/Users/tuanbui/Downloads
```

Thư mục này được mount chỉ đọc tại `/sources`. Có thể nhập:

```text
/sources/toa-dam.mp4
```

Hoặc dán đường dẫn tuyệt đối tương ứng trên máy:

```text
/Users/tuanbui/Downloads/toa-dam.mp4
```

Đường dẫn ngoài thư mục mount và symlink trỏ ra ngoài bị từ chối. Đổi `SOURCE_DIR` rồi chạy lại `docker compose up -d` nếu chuyển kho nguồn. Upload không phụ thuộc thư mục này. Không sửa hoặc xóa file gốc.

## Chất lượng và giới hạn thực tế

- Xuất **1080 × 1920, 30 fps, H.264, AAC 48 kHz stereo**. Nguồn nhỏ hơn Full HD được upscale; việc xuất 1080p không khôi phục chi tiết đã mất. File mẫu cung cấp có độ phân giải 576 × 1024.
- Karaoke dùng mốc từ thật từ Google STT, không chia thời lượng đều giả lập. Các mốc và chữ vẫn có thể sai khi nhiều người nói chồng, tiếng ồn hoặc thuật ngữ khó. Có trình sửa và nghe lại.
- Với nguồn ngang, Gemini phân tích proxy video có tiếng, OpenCV hiệu chỉnh vị trí mặt trên khung thực, FFmpeg nội suy crop. Nguồn dọc không phóng giữ bố cục gốc; bật phóng để AI có vùng dịch chuyển. Không có cam kết theo đúng người nói trong mọi cảnh đông người, che mặt hoặc nói chồng.
- Khung editor dùng chung dữ liệu crop AI với bản xuất khi phân tích focus hoàn tất; intro dùng ảnh từ cùng bộ dựng. Xem bản MP4 để duyệt âm thanh, chuyển đoạn và chất lượng cuối trước đăng kênh.
- Mỗi nguồn tối đa 10 GB / 8 giờ (cấu hình dung lượng bằng `MAX_UPLOAD_GB`), outro tối đa 120 giây. Phân tích audio theo phần 5 phút và lưu cache; chọn đoạn theo cửa sổ 15 phút có phần giao nhau.
- Một hàng đợi xử lý tuần tự giúp tránh nhiều lần render chiếm hết CPU/RAM. Tác vụ bị gián đoạn được đánh dấu để thử lại, giữ transcript đã xong. Có retry với lỗi mạng/rate limit tạm thời.
- YouTube dùng yt-dlp, Node 24 và EJS. Video riêng tư, giới hạn vùng, yêu cầu đăng nhập/chống bot có thể không tải được. Công cụ không vượt CAPTCHA hay đăng nhập; dùng file nguồn khi gặp trường hợp này. Đã kiểm tra biên tập nguồn VnExpress 43 phút có sẵn trong thư viện người dùng.
- Mỗi lần phân tích, bám chủ thể, dựng intro voice hoặc tìm nguồn có thể dùng quota/tính phí Google API của key cấu hình. Không có dữ liệu giả thay thế khi API lỗi; lỗi hiển thị trong hàng đợi.

## Kiến trúc

```text
React + Vite → FastAPI → SQLite + hàng đợi nền
                           ├─ Google STT / Gemini / TTS / Search
                           ├─ OpenCV
                           └─ FFmpeg → MP4 tải xuống
```

- `backend/google_ai.py`: adapter Google REST, không ghi key vào log.
- `backend/pipeline.py`: nhập nguồn, cache transcript, chọn clip, hàng đợi và retry.
- `backend/editor.py`: intro ảnh + TTS/karaoke, tracking, crop, ASS từng từ, concat, watermark, ducking.
- `backend/app.py`: API, upload streaming, giới hạn đường dẫn, tài nguyên, bản xuất.
- `frontend/src/`: giao diện studio responsive.
- `tests/test_core.py`: các kiểm tra thời gian, crop, dữ liệu model, giới hạn đường dẫn và API.

SQLite, asset và video nằm trong `/data`. Giữ volume khi cập nhật. Sao lưu toàn bộ volume để giữ cả nội dung video và cơ sở dữ liệu.

## Phát triển và kiểm thử

Python 3.12 và FFmpeg có libass/font tiếng Việt; Node 24.

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
npm ci --prefix frontend
npm run build --prefix frontend
SOURCE_ROOT=/duong/dan/nguon .venv/bin/uvicorn backend.app:app --host 127.0.0.1 --port 8092
```

```sh
PYTHONPATH=. .venv/bin/pytest -q tests
```

Để sửa giao diện có tự reload, chạy backend như trên và `npm run dev --prefix frontend` (cổng 5192, proxy API về 8092).

Xem [VALIDATION.md](VALIDATION.md) để biết những gì đã kiểm tra thực tế và giới hạn chưa kiểm thử.

## Tài liệu kỹ thuật tham chiếu

- [Gemini 3.8 Flash](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash)
- [Google Transcribe: timestamps và diarization](https://ai.google.dev/gemini-api/docs/transcribe)
- [Google text-to-speech](https://ai.google.dev/gemini-api/docs/speech-generation)
- [FFmpeg filters](https://ffmpeg.org/ffmpeg-filters.html)
- [yt-dlp JavaScript runtime / EJS](https://github.com/yt-dlp/yt-dlp/wiki/EJS)

Dự án `ai-motion-studio` được dùng để tham khảo cách cấu hình watermark theo tọa độ tâm, độ mờ, kích thước và cách gọi Google TTS. Đây là ứng dụng độc lập; không sửa dự án tham khảo.

## Cập nhật 08/09/2026: người nói, lời thoại và intro

- **AI theo chủ thể** chuẩn bị một bản theo dõi khi mở clip. Màn hình hiển thị tiến độ; trong lúc chờ giữ toàn khung. Sau khi xong, bản xem trước và bản xuất dùng chung vị trí crop và quy tắc chuyển cảnh. Lần sau dùng lại kết quả đã lưu; đổi mốc cắt cần chuẩn bị lại.
- AI nghe audio, quan sát môi và chia cảnh thành: người nói, người nghe, cảnh trám, nghi quay nhầm, hình lỗi, chuyển cảnh, kết cảnh hoặc chưa chắc chắn. Bấm danh sách cảnh trong tab Thương hiệu để nghe/xem lại. Crop người nói khi có bằng chứng; cảnh người nghe có một mặt rõ được giữ chân dung ổn định mà vẫn ghi nhãn người nghe. Cảnh trám/lỗi/không chắc chắn giữ toàn hình. Không tự bỏ audio hoặc cắt đoạn talk chỉ vì camera quay sang người khác.
- Dò mặt chỉ tinh chỉnh vị trí hình học, không chọn danh tính người nói. Bbox khuôn mặt có khoảng chừa đầu/tóc; mặt không vừa khung sẽ chuyển sang giữ toàn hình. Mốc cut được tinh chỉnh theo proxy 6 fps; đây vẫn là phân tích AI cần duyệt, không phải bảo đảm phân loại đúng mọi cảnh quay.
- **Lời thoại** mặc định hiển thị theo câu/cụm (ngắt theo dấu câu, khoảng nghỉ, người nói và giới hạn độ dài). Có chế độ theo khung phụ đề. Bấm mốc thời gian để tua; sửa ngay trong textarea ở cả hai chế độ, không cần mở từng từ. Các mốc gốc được giữ; chữ thêm chia sẻ một khoảng phát âm có sẵn. Không tự ước lượng lại timestamp khi sửa chính tả.
- **Intro mới**: một ảnh dọc, tiêu đề ngắn và karaoke tùy chọn; lời dẫn chỉ dùng để đọc. Khung đầu tiên và hai mốc khác trong clip được trích bằng FFmpeg, không tạo ảnh giả. Ảnh nền thương hiệu đặt ở dưới, chồng lên freeze frame; giữ alpha của PNG, không thu nhỏ cả canvas trong suốt thành logo tí hon. Chữ nằm trực tiếp trên nền, không có hộp đen. Preview PNG dùng cùng bộ dựng với MP4.
- **Giọng đọc**: “Sử dụng voice có sẵn của Google” hoặc “Tạo sinh giọng đọc theo tùy chọn”. Chọn tuổi, giới tính, Bắc/Trung/Nam, tin tức/thời sự/TVC, tâm trạng và 1x/1,2x. Gemini dùng giọng nền với chỉ dẫn biểu cảm, không huấn luyện một danh tính giọng mới. Tốc độ 1,2x áp dụng bằng FFmpeg giữ cao độ. Có nghe mẫu và nghe lời mở đầu.
- **Karaoke intro**: căn token hiển thị với audio thật sau đổi tốc độ, giữ nguyên chữ gốc khi bản đọc mở rộng số/từ viết tắt. Nếu mốc không hợp lệ, thử lại một lần; lỗi tiếp sẽ dừng và hướng dẫn xử lý, không chia đều thời gian giả. Tắt phụ đề vẫn giữ voice.
- **Crop ổn định**: khóa tâm crop trong từng cảnh khi vẫn chứa đủ mặt; dùng vùng chết/làm mượt có giới hạn an toàn nếu chủ thể di chuyển. Mốc cut được tinh chỉnh theo frame video gốc. Có hòa trộn ngắn tại cut và tùy chọn giữ hình qua cảnh người nghe chớp ngắn; tiếng và mốc phụ đề không bị rút ngắn.
- **Giao diện**: Light mode/Dark mode lưu theo trình duyệt, màu nhấn #ff7300, đúng hai logo MISA kèm tagline người dùng cung cấp.

### Quy ước đọc riêng cho TTS

Bộ chuẩn hóa `backend/tts_normalizer/` tham khảo `VOICE_OFF_TTS_RULES_UPDATED_v4.md` phiên bản `2026.09.04-r4`. Quy ước được thực hiện bằng code xác định, tách văn bản gốc/hiển thị/bản đọc. Không viết đè phụ đề hoặc transcript.

Hỗ trợ năm theo ngữ cảnh, năm rút gọn, ngày/tháng/năm, số văn bản, số lượng, số thập phân đọc từng chữ số, tăng/giảm, bullet, khoảng số, thời gian AM/PM, tỷ lệ/phân số, tiền VND, identifier có ngữ cảnh và toàn bộ mapping cố định ở mục 23.1. TB được phân loại theo từng lần xuất hiện thành Trưởng ban hoặc trung bình; thiếu bằng chứng sẽ giữ nguyên và yêu cầu kiểm tra. Tên/từ tiếng Anh được giữ nguyên, không tự phiên âm. URL/code và các trường hợp mơ hồ được bảo vệ và cảnh báo.

Bấm **Kiểm tra cách đọc theo quy ước** để xem bản đọc và lịch sử biến đổi. Có thể sửa bản đọc rồi **Dùng bản đọc này**, sau đó **Lưu** clip. Nếu có cảnh báo chưa được duyệt, TTS không chạy; thông báo chỉ rõ cách xử lý. Khi lời dẫn đổi, bản duyệt cũ mất hiệu lực. Đây là bộ quy tắc cho intro của TalkCut, không triển khai toàn bộ workflow fact-check/SSML/NER/danh bạ doanh nghiệp trong tài liệu tham khảo.

Cập nhật từ điển trong `backend/tts_normalizer/approved_pronunciations.json`, tăng `version`, bổ sung test rồi build lại Docker. Cùng văn bản + phiên bản quy ước tạo cùng bản đọc và trace; bản audio do Google sinh có thể thay đổi về ngữ điệu.

### Dữ liệu và tương thích

Settings mới có giá trị mặc định khi đọc clip cũ. Giữ nguyên source, transcript, clip, watermark, nhạc, outro và bản xuất cũ. Cache phân tích raw `speaker-shots-v2.2` được dùng lại và bổ sung layout `stable-v3`; không cần gọi lại Google chỉ để làm mượt crop. Có bản sao SQLite trước nâng cấp ở `/data/pre-v2-backup.sqlite` trong volume Docker. Các bản xuất cũ không tự thay đổi; dựng lại để áp dụng các tính năng mới.

Kiểm thử:

```sh
python -m pytest tests -q
node --test frontend/src/studio-helpers.test.mjs
```

## Chạy local hay máy chủ?

Khuyến nghị hiện tại: Docker local cho cá nhân có source trên máy. VPS có SSD bền vững phù hợp khi cần chạy 24/7 hoặc dùng từ nhiều máy, sau khi thêm đăng nhập/HTTPS/backup. Cloud Run cần tách API và render worker, chuyển media sang object storage, DB và hàng đợi ra ngoài; không đưa nguyên SQLite + local volume + worker nền hiện tại lên service. Xem [kiến trúc và nguồn tham chiếu](memory-bank/architecture.md).

[Memory bank](memory-bank/README.md) lưu quyết định và bằng chứng kiểm tra. Skill handoff đã có tại máy tác giả; gói `.handoff/` lưu intent để bàn giao, trạng thái duyệt ghi trong manifest.

## Các bản dùng thử và bản ổn định

`rc` là bản dùng thử. Chỉ chốt stable/handoff sau khi người dùng xác nhận bản chạy ổn; sau đó mới phát triển tiếp. Đã có mốc dự phòng v0.3.0-rc.1 (còn các lỗi đã báo), không gọi mốc đó là stable. Xem [quy trình version và rollback](memory-bank/releases.md).

```sh
python3 scripts/versions.py list
python3 scripts/versions.py rollback v0.3.0-rc.1
python3 scripts/versions.py development
```

Rollback đổi Docker image, giữ dữ liệu và checkout phát triển. `start.sh` giữ phiên bản đã chọn. Không tự ghi đè SQLite hiện tại bằng snapshot cũ. Khi chuyển máy, cần mang theo volume dữ liệu hoặc restore backup; Git chỉ chứa mã nguồn.

### Thiết lập theo phần và preset

Bàn dựng chia thành **Intro**, **Nội dung chính**, **Outro**, **Dùng chung**. Trong Nội dung chính, chọn **AI focus & Mix** để chỉnh crop dọc và độ mềm chuyển cảnh; chọn **Phụ đề** để sửa lời thoại trực tiếp.

Ở đầu Bàn dựng, bấm **Lưu preset**, đặt tên rồi lưu. Sang clip khác, chọn preset → **Áp dụng** → **Lưu**. Preset dùng lại bố cục, giọng, phụ đề, Mix, watermark, nhạc và outro; giữ riêng lời dẫn, tiêu đề, ảnh nhân vật, mốc cắt. Nếu bật intro mà clip chưa có lời dẫn, AI gợi ý lời dẫn mới theo clip. Preset lưu trong volume dữ liệu, tồn tại sau khi khởi động lại Docker.

Mix mặc định 0,65 giây, điều chỉnh tới 1,2 giây. “Giữ hình qua cảnh chèn ngắn” giảm thay đổi góc máy, giữ nguyên lời nói. Trong lúc AI đối chiếu người nói, bản xem trước tạm crop theo khuôn mặt và ghi rõ trạng thái.
