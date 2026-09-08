# tests/test_editing_v2.py — modified

## Lý do
Giữ test preview legacy có fixture không có source khi default chuyển sang photo.
Nguồn: yêu cầu người dùng 08/09/2026, xác nhận intro mới và diff `7450657..8ffc086`.

## Thay đổi
**Anchor:** test_intro_preview_uses_same_renderer_and_safe_bounds

**Before:** Fixture dùng Settings mặc định.

**After:** Chỉ định intro_design legacy cho test cũ; test photo mới tách riêng.

## Phụ thuộc
Settings; test_intro_v3.py.
