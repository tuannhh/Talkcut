"""Reusable presentation settings, without copying another clip's content."""
from pydantic import BaseModel, Field
from .schemas import Settings
from . import store

CONTENT = {'tracking_subject','crop_locks','crop_x','crop_y','intro_text','intro_title_text','intro_title_highlight','intro_approval_id',
           'intro_image_asset','intro_frame_time','intro_image_x','intro_image_y','intro_image_zoom'}

class PresetRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    settings: Settings

def styles(settings):
    return {k:v for k,v in Settings.model_validate(settings).model_dump().items() if k not in CONTENT}

def validate_assets(settings):
    from .editor import asset
    for field,kind in [('intro_asset','image'),('outro_asset','video'),('music_asset','audio'),('watermark_asset','image')]:
        if settings.get(field):asset(settings[field],kind)

def save(body, id=None):
    name=body.name.strip()
    if not name:raise ValueError('Nhập tên preset.')
    settings=styles(body.settings.model_dump());validate_assets(settings)
    if id:
        store.get(id,'preset')
        return store.update(id,name=name,settings=settings)
    return store.create('preset',{'name':name,'settings':settings})

def apply(id, settings):
    preset=store.get(id,'preset');saved=styles(preset['settings']);validate_assets(saved)
    return Settings.model_validate({**settings,**saved}).model_dump()
