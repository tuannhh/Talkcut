# Phiên bản và rollback

- `v0.3.0-rc.1`: commit 200b2ef; bản dự phòng trước sửa v4, còn lỗi intro/crop đã được người dùng báo. Không gọi là stable.
- `v0.4.0-rc.1`: bản sửa đang được kiểm tra và dùng thử. Chưa có bản nào được người dùng chấp nhận stable.

## Chu kỳ

Sửa → test + build + kiểm tra media thật → commit bản RC → người dùng dùng thử. Khi người dùng xác nhận ổn, chốt version stable và handoff phần đó; sau đó mới phát triển tiếp. Không yêu cầu duyệt tài liệu handoff sau mỗi lần sửa.

## Lệnh tại root ứng dụng

```sh
python3 scripts/versions.py list
python3 scripts/versions.py checkpoint v0.4.0-rc.1
python3 scripts/versions.py rollback v0.3.0-rc.1
python3 scripts/versions.py development
```

Checkpoint yêu cầu Git sạch và hàng đợi rảnh, build từ đúng checkout, tạo tag và SQLite snapshot. Chỉ sau khi được người dùng xác nhận ổn mới dùng `checkpoint v0.4.0 --accepted` trên checkout đã có version tương ứng. Tag cần được push khi công bố. Không ghi đè checkpoint cũ.

Rollback đổi image đang chạy, giữ checkout phát triển và dữ liệu hiện tại. start.sh tiếp tục dùng image đã chọn cho đến khi chạy development. Ảnh Docker/snapshot local không được đưa lên GitHub; chuyển máy cần build từ tag và sao lưu toàn bộ volume media + SQLite. Không tự khôi phục snapshot DB cũ lên dữ liệu mới vì sẽ mất chỉnh sửa sau checkpoint.

- `v0.5.0-rc.1`: crop dọc xuyên suốt, bàn dựng theo phần, preset và Mix 0,65 giây. Bản dùng thử kế tiếp; giữ `v0.4.0-rc.1` để rollback. Chỉ chốt stable sau khi người dùng xác nhận dùng ổn.
