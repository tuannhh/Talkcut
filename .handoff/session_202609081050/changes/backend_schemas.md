# backend/schemas.py — modified

## Lý do
Lưu lựa chọn mới và loại bỏ summary frame theo xác nhận người dùng.
Nguồn: yêu cầu người dùng 08/09/2026, xác nhận intro mới và diff `7450657..8ffc086`.

## Thay đổi
**Anchor:** VoiceProfile; Settings.migrate_removed_summary

**Before:** Summary mặc định bật; không có photo/profile settings.

**After:** Summary luôn tắt; profile literal; ảnh/tiêu đề/highlight/karaoke/tọa độ được validate.

## Phụ thuộc
Backend render và frontend phải dùng cùng tên trường.
