# Kiểm tra thực tế

Ngày kiểm tra: 07/09/2026. Môi trường: macOS Apple Silicon, Python 3.12, Docker Desktop; container Linux ARM64.

## Đã kiểm tra

- Frontend production build bằng Vite.
- Bộ kiểm thử: 24 bài về timestamp STT, karaoke đúng từng sự kiện phát âm, escape ASS, crop/zoom, watermark chữ và ảnh, kiểm tra URL YouTube, chống thoát thư mục qua symlink/path traversal, ánh xạ đường dẫn host vào Docker, giới hạn thời gian, deduplicate clip, snapshot render, áp dụng thương hiệu theo lô, lỗi upload và dữ liệu polling gọn.
- Google Gemini 3.8 Flash gọi thực tế bằng key hiện có: thành công.
- Google Gemini 3.5 Transcribe gọi thực tế với file người dùng cung cấp: 176 từ có timestamp, có nhãn giọng nói; Gemini đề xuất 2 clip với thời lượng khoảng 25 và 28 giây.
- Google TTS gọi thực tế: tạo intro tiếng Việt. Nhận dạng lại audio đã tạo cho ra đúng câu: “Một góc nhìn về trách nhiệm và khát vọng của người trẻ. Cùng lắng nghe câu chuyện sau đây.”
- Google Search grounding gọi thực tế: trả 2 nguồn chính thức của Google cho câu hỏi kiểm thử tài liệu model.
- Dựng từ nguồn 576 × 1024 thành MP4 1080 × 1920, H.264, có âm thanh.
- Bản 37,371 giây: thẻ tóm tắt, intro tiếng Việt, phần nói gốc với karaoke, watermark.
- Bản 34,700 giây: ảnh nền intro do upload, AI chọn vùng chữ, Google TTS, phần nói với karaoke, watermark, nhạc thử có ducking, outro 2 giây vốn không có audio. File ghép hoàn chỉnh có audio hợp lệ.
- Tạo fixture ngang 1920 × 1080 từ 8 giây nguồn mẫu, chuyển người nói từ vùng trái sang phải ở giây 4. Gemini xác định hai vùng; OpenCV sửa mốc chuyển sang đúng 4,0 giây theo khung quan sát. File crop cuối 1080 × 1920; kiểm tra khung trước/sau chuyển cảnh.
- Biểu thức crop với 175 keyframe chạy được bằng FFmpeg.
- Kiểm tra trực quan khung tóm tắt, intro, phụ đề, crop ngang và layout background bằng ảnh trích từ MP4 thật.
- Browser: nhập/xem nguồn, bật intro, sửa text, lưu, xếp hàng render, chuyển panel phụ đề/thương hiệu, lưu opacity watermark, thư viện bản xuất và liên kết tải. Không thấy lỗi JavaScript trong lượt kiểm tra.
- Responsive tại 390 × 844: chiều rộng tài liệu bằng chiều rộng viewport, không tràn ngang toàn trang; danh sách clip cuộn ngang riêng.
- Render trực tiếp trong Docker qua hàng đợi API: tạo thêm bản 37,834 giây, 1080 × 1920, H.264, audio AAC; file tải xuống được lấy từ container.
- Docker image build thành công; dịch vụ chạy non-root, health endpoint hoạt động; giữ nguồn, 2 clip và các bản xuất sau recreate container. Cổng host bind ở loopback.

## Cập nhật kiểm tra 08/09/2026

- 94 bài Python và 4 bài JavaScript đạt; frontend production build và Docker build đạt. Có kiểm thử FFmpeg thật với 1.200 mốc crop và 300 khoảng giữ toàn khung, tránh giới hạn độ sâu biểu thức trên clip dài.
- Nguồn thực tế: tọa đàm VnExpress 43:01, 1920 × 1080, 8.704 từ đã có trong thư viện. Giữ dữ liệu người dùng và sao lưu SQLite trước cập nhật.
- Google phân tích audio và hình ảnh hai đoạn thật: cảnh toàn 32 giây (từ 19:38) và cảnh cận 20 giây (từ 25:14). Đã dựng cả hai thành 1080 × 1920 có audio, kiểm tra ảnh trích: cảnh toàn theo khách mời bên phải, cảnh cận giữ đầy đủ mặt MC, cảnh người nghe giữ toàn hình và tiếp tục audio.
- Phân tích focus hoàn tất cho clip “Chiến lược R&D và bài toán ưu đãi thuế công nghệ cao”, từ 25:10.28 đến 30:01.18. Editor và render dùng chung cache phiên bản `speaker-shots-v2.2`.
- Browser thật: kiểm tra câu/cụm lời thoại, tua theo câu, crop đúng người trong khung ở 25:15.40; AI gợi ý lời dẫn, hai lớp intro, đổi cách viết tiêu đề, kéo vị trí, lưu và tải lại. Bố cục intro được kiểm tra bằng PNG 1080 × 1920 của bộ dựng: toàn bộ chữ nằm ngoài logo MISA News.
- Google Kore tạo mẫu chào 4,72 giây; STT nhận dạng lại đúng các từ trong câu mẫu người dùng yêu cầu. Kiểm tra audio mẫu trong trình duyệt và bảng bản đọc/trace.
- Bộ chuẩn hóa TTS kiểm thử năm, ngày, số lượng, thập phân, tiền, giờ, dấu tăng/giảm, khoảng số, số văn bản, mapping cố định và các trường hợp mơ hồ cần duyệt; bản đọc tách khỏi văn bản hiển thị. Kiểm tra cache giọng và việc hủy hiệu lực bản duyệt khi đổi lời dẫn.
- Xuất hoàn chỉnh qua hàng đợi Docker: 310,034 giây, 1080 × 1920, H.264/AAC, 133,16 MB. Có thẻ tóm tắt, intro hai lớp + voice off, talk gốc 290,9 giây với karaoke/focus, outro, nhạc nền ducking và watermark. Job `c7d2eb3d10ec470abd8fa004cefdd783` hoàn tất 100%; export `840fc0b9018a4e6c92efd39f57aa718a` trong thư viện. Bản sao: `../talkcut-vnexpress-fullhd.mp4`.
- Ảnh trích từ nội dung thật tại giây 8/20/94,75 xác nhận lần lượt chân dung MC đủ mặt, khách mời bên phải cảnh toàn và cảnh người nghe giữ toàn hình.
- Giải mã toàn bộ MP4 cuối bằng FFmpeg không báo lỗi; endpoint tải trả HTTP 206 đúng byte range. Sau recreate cuối, health `ok`, bản xuất còn trong volume. Kiểm tra tua từ intro sang cảnh 00:19 đưa video đến đúng 25:29.447 sau khi tải metadata.

## Giới hạn còn lại

- Chưa đo precision/recall phân loại cảnh hoặc người nói trên một tập tọa đàm lớn. Kiểm tra trực quan ở các mốc mẫu không bảo đảm mọi frame trong nguồn dài đều đúng.
- Chưa benchmark xử lý nhiều giờ trên kho nguồn lớn hoặc khả năng chọn đúng người nói trong cảnh nhiều người nói chồng.
- Không đo sai số forced alignment thủ công trên từng từ. Mốc từ là kết quả STT, có thể cần sửa/duyệt với nguồn khó.
- Crop và ảnh intro được dùng chung giữa preview/render; nhạc, voice off và chuyển đoạn cần duyệt trên MP4 cuối. AI phân loại chưa chắc chắn sẽ giữ toàn hình; không tự xóa audio hoặc suy diễn một chân dung không hiện diện trong source.
- Chưa triển khai toàn bộ workflow SSML/NER/fact-check/danh bạ doanh nghiệp của tài liệu TTS tham khảo. Google có thể thay đổi ngữ điệu giữa các lần sinh audio.

## Cập nhật v3 — 08/09/2026: photo intro, voice profile và theme

- 102 test Python, 4 test JavaScript đạt; Vite và Docker production build đạt. Bổ sung kiểm tra profile, atempo thật, cache voice, alignment theo token gốc và retry mốc lỗi, crop an toàn, photo/highlight, tách cache clip và tắt caption không tắt audio.
- Google tạo audio thật cho profile nữ/miền Nam/người đi làm/tin tức/trung tính/1,2x: 9,576083 giây. 45 token hiển thị căn vào audio; lượt đầu có mốc lỗi được từ chối, lượt tiếp thành công. Code thêm duration hint và một lần retry có kiểm tra, không chia đều timestamp. Chưa chấm accent vùng miền bằng hội đồng nghe.
- Browser thật: profile/tiêu đề/ảnh được lưu qua reload, ba freeze frame tải được, AI gợi ý tiêu đề thành công; audio intro phát đủ 9,576 giây với karaoke đang đổi từ. Light/Dark dùng đúng logo MISA kèm tagline và accent #ff7300; đã xem ảnh chụp cả hai chế độ.
- Kiểm tra PNG từ intro.mp4 tại giây 2: ảnh chân dung, tiêu đề ngắn với highlight cam, karaoke riêng; không còn thẻ tóm tắt hoặc khối lời dẫn tĩnh. Preview và export cùng photo renderer.
- Trên 618 mốc focus của clip thực tế, tổng dịch chuyển ngang giữa mẫu cùng scene giảm 8,3889 → 0,5739 đơn vị chuẩn hóa (93,16%). Đây là diagnostic độ rung crop, không phải độ chính xác xác định người nói. Ảnh main.mp4 tại 8/20/94,75 giây giữ đủ mặt MC, khách mời trong cảnh toàn, và chân dung người nghe.
- Job `8f4a43c6f4384f9ea35f62fce316e4aa` hoàn tất 100%, export `0edbf27cba1b42c99baad5512a7c3127`: 302,867 giây, 1080 × 1920, H.264 có audio, 129.956.642 byte. Intro ảnh + voice/karaoke, talk gốc 290,9 giây, outro, music ducking và watermark. Không có summary card. Bản sao ngoài Git: `../talkcut-v3-fullhd.mp4`.
- Endpoint media trả HTTP 206, byte range 0–1023/129956642. Các source, clip và export cũ được giữ trong volume, SQLite có snapshot pre-v3-backup.sqlite.
- Source scan trước publication không phát hiện key Google, token GitHub hoặc private key; `.env`, runtime DB và video/audio không tracked.
- Giải mã toàn bộ MP4 cuối bằng FFmpeg `-v error -f null -` thành công, không báo lỗi.

## Cập nhật v4 — 08/09/2026: intro đúng lớp, sửa lời thoại trực tiếp, giảm giật

- 107 test Python và 5 test JavaScript đạt; Docker/Vite production build đạt. Có test FFmpeg thật về giữ hình, hòa trộn sau cut, giữ số frame/thời lượng và hiệu chỉnh mốc cut theo video gốc.
- PNG intro từ MP4 thật tại giây 2: chân dung trên, artwork MISA News phủ phần dưới, logo đầy đủ, tiêu đề trắng/cam trực tiếp trên nền xanh không có hộp đen; karaoke ở trên logo. Vùng alpha trống trong PNG 4500×8000 được xử lý trước khi đặt artwork, tránh lỗi banner bị thu nhỏ ở đầu khung.
- Nguồn 25 fps có cut thật tại 15,760 giây, trong khi proxy 6 fps cho mốc 15,833. Đã hiệu chỉnh theo frame gốc, bỏ các thay đổi crop do ranh giới phân tích. Video thử thật 8 giây xác nhận frame hòa trộn và frame sau cut giữ đúng chân dung, không lóe bàn/ghế trống.
- Clip có 60 cut camera quan sát được; giữ hình cho một cảnh người nghe ngắn 94,04–95,44 giây, còn 59 điểm hòa trộn. Không tự xóa audio hoặc thay toàn bộ cảnh quay gốc. Ảnh main.mp4 tại 94,5 giây xác nhận giữ hình khách mời. Mức giảm chuyển cảnh phụ thuộc cảnh trám thực tế; chưa chứng minh trên kho video lớn.
- Browser bản cuối: sửa cả câu `1` thành `một` rồi bấm Lưu trực tiếp; backend lưu đúng chữ và giữ mốc 1510,6–1510,9. Chuyển sang theo khung phụ đề, sửa lại `1` rồi Lưu trực tiếp; dữ liệu gốc được khôi phục. Không cần nút Sửa chữ hoặc mở từng từ.
- Job `a6a26e1d73d54f758ae59b78081a9d49` hoàn tất 100%; export `8ef839c948664b1b8e40986c7e1a3d44`: 302,367 giây, 1080×1920, H.264 30 fps/AAC, 133.747.786 byte. Có intro voice/karaoke, talk 290,9 giây, outro, music/watermark. Bản sao ngoài Git: `../talkcut-v4-fullhd.mp4`.
- Giải mã toàn bộ MP4 cuối thành công, không báo lỗi; endpoint tải trả HTTP 206, bytes 0–1023/133747786. Sau triển khai UI cuối còn đủ 2 nguồn, 7 clip, 6 bản xuất.
- Đã chạy rollback về image build từ commit 200b2ef rồi trở lại bản phát triển, giữ database/media. Snapshot pre-v4-backup.sqlite và image v0.3.0-rc.1 là dự phòng có lỗi đã biết, không phải stable. Bản v4 là release candidate, chỉ chốt stable/handoff khi người dùng xác nhận dùng ổn.
