# frontend/src/styles.css — modified

## Lý do
Người dùng muốn hai theme với tone #ff7300.
Nguồn: yêu cầu người dùng 08/09/2026, xác nhận intro mới và diff `7450657..8ffc086`.

## Thay đổi
**Anchor:** CSS color variables

**Before:** Nhiều màu xanh hardcode.

**After:** Thay màu nền/viền/chữ bằng token dùng chung; sửa màu alpha sang color-mix.

## Phụ thuộc
theme.css token definitions; video subtitle colors vẫn do settings của clip.
