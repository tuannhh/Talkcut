# backend/voice_profiles.py — added

## Lý do
Các thuộc tính tuổi/giới/miền/phong cách/tâm trạng theo yêu cầu.
Nguồn: yêu cầu người dùng 08/09/2026, xác nhận intro mới và diff `7450657..8ffc086`.

## Thay đổi
**Anchor:** instruction

**Before:** Chưa có prompt profile.

**After:** Một giọng thống nhất, thêm miền Trung; tốc độ thực áp dụng ngoài prompt.

## Phụ thuộc
VoiceProfile; narration; Google TTS giọng nền.

## Vị trí chèn
Giữ đường dẫn `backend/voice_profiles.py` trong root source A; đọc/copy cùng các phụ thuộc nêu trên.
