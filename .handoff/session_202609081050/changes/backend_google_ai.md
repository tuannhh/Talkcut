# backend/google_ai.py — modified

## Lý do
Dùng model TTS của Google theo mô tả giống dự án tham khảo.
Nguồn: yêu cầu người dùng 08/09/2026, xác nhận intro mới và diff `7450657..8ffc086`.

## Thay đổi
**Anchor:** tts

**Before:** Chỉ text và tên giọng.

**After:** Nhận direction tùy chọn và truyền vào prompt tổng hợp.

## Phụ thuộc
voice_profiles.instruction; Gemini TTS REST.
