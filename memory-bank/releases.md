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
- `v0.5.0-rc.2`: bản v5 dùng thử đã bổ sung tương thích dữ liệu khi rollback về v4. RC.1 là checkpoint nội bộ trước kiểm tra tương thích; dùng RC.2 cho lượt duyệt này.

### v0.6.0-rc.1 — focus / transparent Intro
Candidate checkpoint with profile-face refinement, stable shot anchors, dirty-state focus fix, transparent PNG compositing and title formatting/drag controls. Mix accepted in v5 is preserved. Previous v0.5.0-rc.2 remains the rollback target; both use the same compatible data schema. See VALIDATION.md for actual-media evidence. Not marked stable until user acceptance.

### v0.7.0-rc.1 — fixed subject selection
Candidate introducing explicit stationary subject framing and separate moving-subject tracking. Retains v0.6.0-rc.1 as rollback checkpoint. Schema adds fields under existing manual mode; older images ignore per-interval locks, so use v7 when those locks are required. No destructive database migration. Await user acceptance before stable promotion.

### v0.8.0-rc.1 — selected face tracking

Candidate adding source-scoped SFace appearance comparison, conservative verified portrait holds and bundled title fonts. Retains v0.7.1-rc.1 as rollback target. No SQLite migration; tracking reference tokens are content-specific and presets remain portable. Await user acceptance before stable promotion.

### v0.9.0-rc.1 — SCRFD + ArcFace tracking

Candidate replacing the selected-subject detector/comparator with the local
SCRFD 10G + ArcFace r50 engine. The checkpoint records both the Studio image
and face-engine image, while media and SQLite remain in the existing volume.
The first use downloads roughly 190 MB of ONNX models into that volume. No
database migration or content-specific preset change. Await user review before
stable promotion.

### v0.9.0-rc.2 — high-resolution YouTube + moving fallback

Candidate preserving `v0.9.0-rc.1` as the preceding rollback point. It prefers
2160p YouTube streams and removes selected-subject portrait stills, so
uncertain shots remain moving footage. Source replacement is additive: the
old local file stays in the volume. No schema migration; await user review
before stable promotion.

### v0.9.0-rc.3 — reliable focus reload

Candidate preserving v0.9.0-rc.2 as its rollback point. It restores the
ordinary reaction-hold image helper that a previous cleanup removed, without
changing selected-subject plans (which explicitly have no static holds).
No SQLite migration; await user review before stable promotion.

### v0.9.0-rc.4 — background face suggestions

Candidate preserving v0.9.0-rc.3 as its rollback point. Adds a persistent
clip-scoped portrait suggestion job using FFmpeg-decoded stills, avoiding the
host OpenCV AV1 seek limitation. No SQLite migration; await user review before
stable promotion.

## v0.11.0-rc.1 — stacked two-frame composite

Candidate preserving `v0.10.0-rc.1` as its rollback point. Adds AI-detected
wide-two-person moments composited into a fixed top/bottom stacked frame with
a gradient seam, gated to only those detected windows; everything else renders
unchanged. New settings `tracking_subject_2`/`stacked_enabled`; no destructive
migration. Validated with 169 Python tests (real ffmpeg, inside Docker), 8 JS
tests, Docker/Vite builds, and a real-engine (SCRFD/ArcFace) probe against a
semi-synthetic fixture built from real face crops — see VALIDATION.md. No
probe against genuine unedited two-person camera footage yet; awaiting user
review before stable promotion.

## v0.10.0-rc.1 — reference style candidate

Dựng nhanh, reference-video templates and native-source tracking recovery.
Validated two real reference analyses, a 22.034-second Full-HD render, background
portrait scan, 159 Python tests and 6 JS tests. See VALIDATION.md. Composition
stacking/B-roll/complex motion remain documented observations, not automatic
reconstruction. This is an RC for user review, not a stable handoff. The local
checkpoint includes both Docker images and a SQLite snapshot; rollback keeps
current media and edits by default.
