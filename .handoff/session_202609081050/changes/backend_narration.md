# backend/narration.py — modified

## Lý do
Giọng tùy chọn và karaoke cần theo audio thực, đúng quy ước đọc.
Nguồn: yêu cầu người dùng 08/09/2026, xác nhận intro mới và diff `7450657..8ffc086`.

## Thay đổi
**Anchor:** synthesize; align_display

**Before:** Cache theo giọng/text; chưa căn karaoke intro.

**After:** Cache gồm profile; atempo 1.2; căn token gốc vào audio; kiểm tra mốc và retry một lần, không chia đều.

## Phụ thuộc
VoiceProfile; voice_profiles; media.ffmpeg/probe; Google API. Vùng miền là hướng dẫn sinh giọng, cần nghe duyệt.
