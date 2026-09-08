# backend/app.py — modified

## Lý do
Nối các điều khiển intro/voice và crop mới với backend.
Nguồn: yêu cầu người dùng 08/09/2026, xác nhận intro mới và diff `7450657..8ffc086`.

## Thay đổi
**Anchor:** intro_frames; intro_title; intro_audio; get_focus

**Before:** Preview hai lớp; TTS chỉ nhận tên giọng; focus raw.

**After:** API ảnh gợi ý, tiêu đề, audio kèm mốc; trả focus prepared và kiểm tra asset ảnh.

## Phụ thuộc
intro_art; narration; schemas.Settings.
