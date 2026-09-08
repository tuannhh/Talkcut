"""Gemini voice direction, following AI Motion Studio's single-speaker contract."""
from .schemas import VoiceProfile


def instruction(profile):
    p = VoiceProfile.model_validate(profile).model_dump()
    gender = {'male': 'nam', 'female': 'nữ'}[p['gender']]
    region = {'bac': 'miền Bắc', 'trung': 'miền Trung, tiếng Việt rõ ràng', 'nam': 'miền Nam'}[p['region']]
    age = {'thanhnien': 'trẻ trung của thanh niên', 'trungnien': 'chín chắn, từng trải của người trung niên', 'nguoidilam': 'tự tin, chuyên nghiệp của người đi làm'}[p['age']]
    style = {'tintuc': 'tin tức hiện đại, gọn gàng, dứt khoát', 'thoisu': 'thời sự trang trọng, có điểm nhấn', 'tvc': 'TVC quảng cáo cuốn hút, có nhấn nhá'}[p['style']]
    mood = {'neutral': 'trung tính', 'cheerful': 'vui vẻ, tươi tắn', 'energetic': 'năng động, tràn đầy năng lượng'}[p['mood']]
    return f'Bạn là MỘT phát thanh viên {gender}, giọng {region}, chất giọng {age}, phong cách {style}, tâm trạng {mood}. Đọc ở tốc độ bình thường. Giữ đúng một giọng từ đầu đến cuối, không nhập vai kể cả câu trích dẫn. Đọc NGUYÊN VĂN nội dung, không thêm bớt hoặc bình luận. Chỉ đọc:\n'
