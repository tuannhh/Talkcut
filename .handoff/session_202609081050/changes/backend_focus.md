# backend/focus.py — modified

## Lý do
Người dùng báo crop giật và cảnh vô nghĩa; yêu cầu ổn định mà giữ đúng mặt.
Nguồn: yêu cầu người dùng 08/09/2026, xác nhận intro mới và diff `7450657..8ffc086`.

## Thay đổi
**Anchor:** cached; enrich_reactions; prepared_track

**Before:** Tâm theo từng mẫu; cảnh người nghe thường chuyển sang toàn hình.

**After:** Khóa tâm khả thi theo cảnh, smoothing có chặn an toàn; một mặt rõ trên reaction giữ chân dung nhưng không đổi nhãn speaker.

## Phụ thuộc
OpenCV; geometry; cache raw speaker-shots-v2.2. Không chứng minh độ chính xác nhận diện bằng chỉ số jitter.
