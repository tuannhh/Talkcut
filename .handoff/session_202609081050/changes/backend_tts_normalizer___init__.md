# backend/tts_normalizer/__init__.py — modified

## Lý do
Nghe mẫu phải dùng đúng profile người dùng chọn.
Nguồn: yêu cầu người dùng 08/09/2026, xác nhận intro mới và diff `7450657..8ffc086`.

## Thay đổi
**Anchor:** VoicePreviewRequest

**Before:** Request có voice nhưng không có mode/profile.

**After:** Thêm mode và VoiceProfile; giữ nguyên quy ước chuẩn hóa hiện có.

## Phụ thuộc
schemas.VoiceProfile; app.preview_tts.
