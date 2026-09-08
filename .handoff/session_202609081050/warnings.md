# Rủi ro tích hợp

- Đây là repo mới. base_commit chưa xác nhận; không suy ra nhánh/máy B đang có baseline_candidate. Cần đối chiếu B trước khi integrate.
- Gói đang chờ người dùng duyệt theo skill handoff; quyền commit/push code đã được cấp riêng.
- Tích hợp schemas + voice_profiles/intro_art/narration trước caller app/editor; frontend main cần IntroEditor, EditorExtras và theme/public logos cùng lúc.
- Giữ .env và toàn bộ /data volume. API key/media không nằm trong GitHub; clone repo không tự có các source/export trên máy A.
- intro_design photo và summary luôn false là thay đổi có chủ ý theo xác nhận người dùng. Export cũ giữ nguyên, cần dựng lại.
- Focus layout stable-v3 dùng cache raw speaker-shots-v2.2. Reaction portrait không chứng minh người trên hình đang nói. Cảnh quay nhầm/phân loại AI chưa có benchmark lớn.
- Giọng sinh vẫn dùng voice nền Google với prompt. Kiểm tra accent thực bằng nghe thử; không cam kết tạo danh tính độc nhất. Forced alignment có thể thất bại; không thay bằng timestamp chia đều.
- Chạy một process worker; Cloud Run cần DB/media/queue bền vững bên ngoài và tách render jobs. VPS public cần authentication/HTTPS/origin config/backup.
