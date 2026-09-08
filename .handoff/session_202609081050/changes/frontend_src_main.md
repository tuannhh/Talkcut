# frontend/src/main.jsx — modified

## Lý do
Tích hợp editor mới, bỏ summary và hỗ trợ theme/logo tương ứng.
Nguồn: yêu cầu người dùng 08/09/2026, xác nhận intro mới và diff `7450657..8ffc086`.

## Thay đổi
**Anchor:** App theme state; IntroEditor; focus geometry

**Before:** Một dark theme, logo TalkCut; controls intro cũ.

**After:** Theme lưu localStorage; logo MISA theo theme; IntroEditor/Canvas; nhận geometry prepared.

## Phụ thuộc
theme.css; IntroEditor; public/brand; focus prepared_zoom.
