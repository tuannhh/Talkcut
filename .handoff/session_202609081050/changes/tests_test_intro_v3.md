# tests/test_intro_v3.py — added

## Lý do
Kiểm chứng voice/crop/render mới, đặc biệt mốc không hợp lệ và tốc độ.
Nguồn: yêu cầu người dùng 08/09/2026, xác nhận intro mới và diff `7450657..8ffc086`.

## Thay đổi
**Anchor:** v3 regression tests

**Before:** Chưa có test cho thay đổi mới.

**After:** 8 test về migration, profile, FFmpeg 1.2x/cache, alignment retry, crop an toàn, photo/highlight, cache clip và caption-off.

## Phụ thuộc
pytest; FFmpeg; Pillow; FastAPI TestClient; monkeypatch Google chỉ trong test.

## Vị trí chèn
Giữ đường dẫn `tests/test_intro_v3.py` trong root source A; đọc/copy cùng các phụ thuộc nêu trên.
