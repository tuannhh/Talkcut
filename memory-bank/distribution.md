# Bộ cài TalkCut cho người không chuyên kỹ thuật

Trạng thái: yêu cầu đã được người dùng xác nhận ngày 2026-09-09; chưa triển khai bộ cài. Ưu tiên hoàn thiện và được người dùng chấp nhận bản ổn định trước. v0.7.1-rc.1 vẫn là ứng viên, không phải bản stable.

## Hướng đóng gói đã chọn

Một bộ cài Windows `TalkCut-Setup.exe` điều phối toàn bộ quá trình: kiểm tra máy, cài thành phần còn thiếu, khởi động ứng dụng và tạo shortcut. Giữ kiến trúc Docker hiện tại; không chuyển sang backend native chỉ để tránh Docker. Python, Node, FFmpeg, thư viện xử lý và giao diện được đóng sẵn trong image Linux của TalkCut. Không cài các runtime này rời lên Windows; không build image hoặc cài npm/pip trên máy người dùng.

Docker Desktop và WSL 2 là các thành phần cấp máy; trình cài xử lý riêng với payload chính thức được kiểm tra chữ ký/hash và phiên bản tương thích. Đánh giá điều kiện phân phối payload của bên thứ ba trước khi phát hành. Nếu cần tải thành phần từ nguồn chính thức, vẫn thực hiện trong cùng trình cài với tiến độ rõ ràng. Internet được người dùng xác nhận là điều kiện sử dụng.

## Luồng cài đặt và sử dụng

1. Kiểm tra phiên bản Windows/kiến trúc CPU, RAM, dung lượng SSD, ảo hóa, WSL, Docker có sẵn và cổng ứng dụng. Không thay đổi hoặc xóa môi trường Docker khác của người dùng.
2. Cài thành phần thiếu, hiển thị điều khoản cần chấp thuận, giải thích yêu cầu quyền hệ thống. Nếu Windows cần khởi động lại, lưu tiến trình và tiếp tục sau reboot. Nếu BIOS tắt ảo hóa hoặc chính sách IT chặn, hướng dẫn cụ thể; không tuyên bố mọi máy đều cài không cần tương tác.
3. Nạp image TalkCut phát hành cho Windows x86-64/Linux amd64 (không dùng nhầm image arm64 đang chạy trên Mac), tạo vùng dữ liệu bền vững và shortcut. Đợi healthcheck rồi mới mở giao diện.
4. Lần mở đầu: chọn thư mục lưu video, nhập Gemini API key, kiểm tra quyền truy cập các model dùng cho nội dung/STT/TTS. Phân biệt lỗi key, model, hạn mức và kết nối. Không nhúng API key của nhà phát triển. Che key trong UI/log/chẩn đoán và loại khỏi preset/gói chia sẻ.
5. Những lần sau: bấm biểu tượng TalkCut; launcher tự khởi động Docker nếu cần, mở ứng dụng khi sẵn sàng, báo lỗi bằng tiếng Việt dễ hiểu. Không yêu cầu dùng terminal.
6. Cập nhật giữ video, preset và cấu hình. Backup trước migration; rollback app chỉ khi schema tương thích, phục hồi snapshot là hành động riêng. Không tự xóa dữ liệu khi gỡ ứng dụng hoặc gỡ Docker đang dùng chung.

## Cấu hình Windows dự kiến

Đây là mục tiêu kỹ thuật cho một tác vụ dựng Full HD tại một thời điểm, chưa phải cấu hình đã benchmark trên Windows. Cần xác nhận lại trước khi công bố bộ cài ổn định.

| Thành phần | Tối thiểu dự kiến cho TalkCut | Khuyến nghị |
| --- | --- | --- |
| Hệ điều hành | Windows 11 64-bit x86-64, bản còn được Microsoft và Docker hỗ trợ | Windows 11 64-bit được cập nhật |
| CPU | 4 nhân, hỗ trợ SLAT và VT-x/AMD-V, bật ảo hóa | 8 nhân trở lên |
| RAM hệ thống | 16 GB | 32 GB trở lên |
| Ổ đĩa | SSD, còn trống ít nhất 50 GB cho môi trường và dự án nhỏ | NVMe SSD, còn trống ít nhất 150 GB |
| GPU | Không bắt buộc GPU rời; pipeline hiện tại dùng CPU | GPU rời không phải điều kiện; chưa cam kết tăng tốc GPU |
| Mạng | Internet ổn định, truy cập Google AI và nguồn video | Kết nối băng rộng ổn định |
| Google AI | Gemini API key có quyền truy cập model và quota phù hợp | Theo dõi quota/chi phí khi dùng nhiều video |

Dung lượng thực tế phụ thuộc source, bản xuất, cache và các phiên bản giữ lại. Không coi 50 GB là đủ cho mọi video. Trình cài và ứng dụng phải kiểm tra dung lượng trước tác vụ lớn. Mức Docker 8 GB RAM chỉ là ngưỡng nền tảng, không đủ bằng chứng để quảng cáo TalkCut dựng Full HD ổn định ở 8 GB.

## Điều kiện hoàn thành trước phát hành

- Chốt stable từ các luồng thực tế: thêm nguồn, phụ đề, intro alpha/TTS, khóa chủ thể, Mix, preset và xuất Full HD.
- Build và thử trên Windows sạch, cả máy đã có Docker; kiểm tra quyền hệ thống, reboot/resume, thiếu dung lượng, mất mạng, key sai, quota hết, cổng bận.
- Đo CPU/RAM/đĩa/thời gian dựng với video tọa đàm dài; điều chỉnh bảng cấu hình theo kết quả, không hứa thời gian render trước khi đo.
- Xác minh image amd64, fonts tiếng Việt, đường dẫn Windows có dấu/khoảng trắng, thư mục nguồn và file lớn.
- Kiểm tra cài mới, nâng cấp, rollback, gỡ cài giữ dữ liệu; ký bộ cài và phát hành checksum.

## Nguồn tham khảo (kiểm tra 2026-09-09)

- Docker Windows requirements và tùy chọn cài đặt: https://docs.docker.com/desktop/setup/install/windows-install/
- WSL 2, quyền hệ thống khi cài: https://docs.docker.com/desktop/setup/install/windows-permission-requirements/
- Docker WSL backend: https://docs.docker.com/desktop/features/wsl/
