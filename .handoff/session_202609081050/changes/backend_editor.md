# backend/editor.py — modified

## Lý do
Thay frame cũ bằng ảnh/tiêu đề/karaoke và giữ voice nếu ẩn phụ đề.
Nguồn: yêu cầu người dùng 08/09/2026, xác nhận intro mới và diff `7450657..8ffc086`.

## Thay đổi
**Anchor:** intro_card; still_segment; render

**Before:** Intro ảnh có đoạn lời dẫn tĩnh; audio không có karaoke intro.

**After:** Photo renderer dùng chung preview/export; ASS theo audio; intro im lặng không bắt buộc lời dẫn.

## Phụ thuộc
intro_art.photo_card; narration.align_display; Settings.
