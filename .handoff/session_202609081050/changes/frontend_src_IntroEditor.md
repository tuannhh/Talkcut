# frontend/src/IntroEditor.jsx — added

## Lý do
Đơn giản hóa intro và cho đủ tùy chọn voice/ảnh/tiêu đề.
Nguồn: yêu cầu người dùng 08/09/2026, xác nhận intro mới và diff `7450657..8ffc086`.

## Thay đổi
**Anchor:** IntroEditor; profiles

**Before:** Điều khiển nằm trong main và theo hai lớp chữ tĩnh.

**After:** Component ảnh gợi ý/upload/pan, title editable/AI/highlight/case, voice profiles, karaoke toggle.

## Phụ thuộc
main Field/Slider/Toggle/AssetPicker; EditorExtras.VoiceControls; intro APIs.

## Vị trí chèn
Giữ đường dẫn `frontend/src/IntroEditor.jsx` trong root source A; đọc/copy cùng các phụ thuộc nêu trên.
