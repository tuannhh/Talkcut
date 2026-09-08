# backend/intro_art.py — added

## Lý do
Người dùng yêu cầu freeze frame, upload ảnh, crop/pan và tiêu đề đơn giản.
Nguồn: yêu cầu người dùng 08/09/2026, xác nhận intro mới và diff `7450657..8ffc086`.

## Thay đổi
**Anchor:** freeze; first_frame; suggestions; photo_card

**Before:** Chưa có module ảnh intro.

**After:** Trích ba ảnh thật; một canvas 9:16; band thương hiệu tùy chọn; title/highlight; khóa sinh ảnh và chỉ tạo asset sau khi ghi file.

## Phụ thuộc
FFmpeg; Pillow; focus.prepared_track; editor font/asset/wrap. Không có focus thì giữ toàn hình, không crop tâm mù.

## Vị trí chèn
Giữ đường dẫn `backend/intro_art.py` trong root source A; đọc/copy cùng các phụ thuộc nêu trên.
