from typing import Literal
from pydantic import BaseModel, Field, model_validator


class Word(BaseModel):
    text: str = Field(min_length=1, max_length=150)
    start: float = Field(ge=0, allow_inf_nan=False)
    end: float = Field(gt=0, allow_inf_nan=False)
    speaker: str = ''

    @model_validator(mode='after')
    def valid(self):
        if self.end <= self.start:
            raise ValueError('Mốc kết thúc phải sau mốc bắt đầu.')
        return self


class VoiceProfile(BaseModel):
    age: Literal['thanhnien', 'trungnien', 'nguoidilam'] = 'nguoidilam'
    gender: Literal['male', 'female'] = 'female'
    region: Literal['bac', 'trung', 'nam'] = 'bac'
    style: Literal['tintuc', 'thoisu', 'tvc'] = 'tintuc'
    mood: Literal['neutral', 'cheerful', 'energetic'] = 'neutral'
    speed: Literal[1, 1.2] = 1


class Settings(BaseModel):
    @model_validator(mode='before')
    @classmethod
    def migrate_removed_summary(cls, value):
        if isinstance(value, dict):
            value={**value, 'summary_enabled':False}
        return value

    summary_enabled: bool = False
    summary_seconds: float = Field(default=3, ge=1, le=10)
    intro_enabled: bool = False
    intro_design: Literal['legacy', 'photo'] = 'photo'
    intro_caption_enabled: bool = True
    intro_caption_y: float = Field(default=.53, ge=.08, le=.95)
    intro_caption_x: float = Field(default=.5, ge=.1, le=.9)
    intro_background_scale: float = Field(default=1, ge=.5, le=1.5)
    calm_short_shots: bool = True
    transition_seconds: float = Field(default=.24, ge=0, le=.5)
    intro_title_text: str = Field(default='', max_length=180)
    intro_title_highlight: str = Field(default='', max_length=100)
    intro_title_highlight_color: str = Field(default='#ff7300', pattern=r'^#[0-9a-fA-F]{6}$')
    intro_image_asset: str | None = None
    intro_frame_time: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    intro_image_x: float = Field(default=.5, ge=0, le=1)
    intro_image_y: float = Field(default=.5, ge=0, le=1)
    intro_image_zoom: float = Field(default=1, ge=1, le=3)
    intro_background_enabled: bool = False
    intro_background_height: float = Field(default=.25, ge=.1, le=.6)
    intro_voice_mode: Literal['prebuilt', 'designed'] = 'prebuilt'
    intro_voice_profile: VoiceProfile = Field(default_factory=VoiceProfile)
    intro_text: str = Field(default='', max_length=700)
    intro_asset: str | None = None
    intro_color: str = Field(default='#ffffff', pattern=r'^#[0-9a-fA-F]{6}$')
    intro_size: int = Field(default=66, ge=28, le=100)
    intro_x: float = Field(default=.5, ge=.1, le=.9)
    intro_y: float = Field(default=.32, ge=.12, le=.8)
    intro_width: float = Field(default=.8, ge=.3, le=.9)
    intro_title_enabled: bool = True
    intro_title_color: str = Field(default='#ffffff', pattern=r'^#[0-9a-fA-F]{6}$')
    intro_title_size: int = Field(default=72, ge=28, le=110)
    intro_title_x: float = Field(default=.5, ge=.1, le=.9)
    intro_title_y: float = Field(default=.70, ge=.12, le=.83)
    intro_title_width: float = Field(default=.8, ge=.3, le=.9)
    intro_title_case: Literal['original', 'upper'] = 'original'
    intro_approval_id: str | None = None
    intro_voice: str = Field(default='Kore', pattern=r'^[A-Za-z]{2,30}$')
    intro_tts: bool = True
    intro_seconds: float = Field(default=5, ge=2, le=30)
    outro_asset: str | None = None
    music_asset: str | None = None
    music_volume: float = Field(default=0.12, ge=0, le=0.6)
    watermark_kind: Literal['none', 'text', 'image'] = 'text'
    watermark_text: str = Field(default='GÓC DOANH NGHIỆP', max_length=80)
    watermark_asset: str | None = None
    watermark_x: float = Field(default=0.5, ge=0, le=1)
    watermark_y: float = Field(default=0.12, ge=0, le=1)
    watermark_opacity: float = Field(default=0.55, ge=0.05, le=1)
    watermark_scale: float = Field(default=0.32, ge=0.05, le=0.8)
    caption_enabled: bool = True
    caption_size: int = Field(default=62, ge=32, le=92)
    caption_y: float = Field(default=0.73, ge=0.3, le=0.83)
    caption_color: str = Field(default='#dfff00', pattern=r'^#[0-9a-fA-F]{6}$')
    caption_words: int = Field(default=5, ge=2, le=9)
    crop_mode: Literal['auto', 'center', 'manual', 'fit'] = 'auto'
    crop_x: float = Field(default=0.5, ge=0, le=1)
    crop_zoom: float = Field(default=1.0, ge=1, le=2)
    brand_color: str = Field(default='#ff7300', pattern=r'^#[0-9a-fA-F]{6}$')


class AnalyzeRequest(BaseModel):
    focus: str = Field(default='Quản trị doanh nghiệp, kinh doanh, thuế, tài chính, bài học thực tiễn', max_length=1500)
    min_seconds: int = Field(default=30, ge=8, le=180)
    max_seconds: int = Field(default=90, ge=15, le=300)

    @model_validator(mode='after')
    def valid(self):
        if self.min_seconds > self.max_seconds:
            raise ValueError('Thời lượng tối thiểu không được lớn hơn tối đa.')
        return self


class ImportRequest(BaseModel):
    kind: Literal['youtube', 'path']
    value: str = Field(min_length=1, max_length=2048)


class BatchBrand(BaseModel):
    clip_ids: list[str] = Field(min_length=1, max_length=80)
    settings: Settings


class ClipEdit(BaseModel):
    title: str = Field(max_length=180)
    summary: str = Field(max_length=600)
    start: float = Field(ge=0, allow_inf_nan=False)
    end: float = Field(gt=0, allow_inf_nan=False)
    settings: Settings = Field(default_factory=Settings)
    words: list[Word] | None = Field(default=None, max_length=4000)

    @model_validator(mode='after')
    def valid(self):
        if not 1 <= self.end - self.start <= 600:
            raise ValueError('Clip phải dài từ 1 đến 600 giây.')
        return self
