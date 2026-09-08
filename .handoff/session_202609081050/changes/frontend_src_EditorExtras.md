# frontend/src/EditorExtras.jsx — modified

## Lý do
Xem trước cần karaoke thật và tránh audio cũ sau khi sửa nội dung.
Nguồn: yêu cầu người dùng 08/09/2026, xác nhận intro mới và diff `7450657..8ffc086`.

## Thay đổi
**Anchor:** VoiceControls; IntroCanvas

**Before:** Intro hai lớp kéo thả và nghe giọng có sẵn.

**After:** Gửi profile; phát audio/timings; kéo ảnh/title; bỏ khối caption rỗng; bỏ response audio cũ.

## Phụ thuộc
intro-preview/intro-audio/tts APIs; wordGroups; theme.css.
