# Thay đổi cấp hệ thống

## Dependencies / ENV / database
Không thêm package hoặc ENV. SQLite vẫn dùng JSON records; Settings bổ sung default và ép summary_enabled=false. Giữ volume và media; không tự sửa export cũ. Logo supplied được thêm vào frontend/public.

## Luồng nghiệp vụ
Profile → chuẩn hóa bản đọc → Gemini TTS → atempo → align display token → preview audio + ASS export. Caption off chỉ tắt chữ. Ảnh freeze/upload → photo_card → PNG preview và video intro cùng renderer. Raw focus → reaction visual refinement → face-safe stable geometry → preview và FFmpeg.

## Config
Dark/Light lưu localStorage, accent #ff7300. Runtime vẫn một worker local. Xem memory-bank/architecture.md cho phương án triển khai. Không chuyển nguyên local SQLite/volume lên Cloud Run.
