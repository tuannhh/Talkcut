# frontend/src/theme.css — added

## Lý do
Giữ bố cục hiện có, thêm Light/Dark và tone cam người dùng yêu cầu.
Nguồn: yêu cầu người dùng 08/09/2026, xác nhận intro mới và diff `7450657..8ffc086`.

## Thay đổi
**Anchor:** data-theme tokens; intro controls

**Before:** Chưa có file theme riêng.

**After:** Nền trung tính hai chế độ; accent #ff7300; logo/ảnh/profile controls và preview overlays.

## Phụ thuộc
styles.css; main root dataset; IntroEditor/IntroCanvas.

## Vị trí chèn
Giữ đường dẫn `frontend/src/theme.css` trong root source A; đọc/copy cùng các phụ thuộc nêu trên.
