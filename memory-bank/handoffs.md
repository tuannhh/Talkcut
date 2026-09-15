# Điểm handoff đã chốt (bản stable)

Danh sách các bản đã được người dùng xác nhận ổn định và chốt bằng
`scripts/versions.py checkpoint <version> --accepted`. Chỉ các bản trong
danh sách này là "handoff" thật sự để quay lại khi cần — các bản `-rc.N`
khác là candidate đang thử, không dùng làm điểm rollback lâu dài.

Lệnh chạy tại thư mục gốc ứng dụng (`C:\MISA-project\Talkcut`), cần Docker
đang chạy và không có tác vụ nào đang xử lý dở. Rollback đổi image container
đang chạy về đúng bản đã chốt, **giữ nguyên database/media hiện tại** (không
tự khôi phục snapshot SQLite cũ đè lên dữ liệu mới sau đó).

Mỗi khi chốt một bản stable mới, thêm mục mới lên **đầu** danh sách này.

## v0.11.0 — 2026-09-15

Ghép khung chồng 2 người (stacked two-frame composite) khi AI phát hiện cảnh
toàn đủ cả hai chủ thể; giữ khung đơn bình thường ở các cảnh khác. Bản stable
đầu tiên của dự án.

```bash
python3 scripts/versions.py rollback v0.11.0
```

Chi tiết: [releases.md](releases.md) mục "v0.11.0 — stacked two-frame
composite (stable, accepted)", [changelog.md](changelog.md) mục "2026-09-15
— v0.11.0 (accepted stable)", bằng chứng kiểm thử tại
[../VALIDATION.md](../VALIDATION.md) mục "v0.11.0-rc.1 — stacked two-frame
composite".
