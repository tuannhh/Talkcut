from pathlib import Path
from PIL import ImageFont

ROOT=Path(__file__).parent/'fonts'

def title_font(settings,size):
    family=settings.get('intro_title_font','DejaVu Sans')
    bold=settings.get('intro_title_bold',True);italic=settings.get('intro_title_italic',False)
    if family in ('Google Sans','Barlow'):
        slug,prefix=('googlesans','GoogleSans') if family=='Google Sans' else ('barlow','Barlow')
        suffix='BoldItalic' if bold and italic else 'Bold' if bold else 'Italic' if italic else 'Regular'
        return ImageFont.truetype(str(ROOT/slug/f'{prefix}-{suffix}.ttf'),size)
    if family in ('Open Sans','Roboto'):
        slug,prefix=('opensans','OpenSans') if family=='Open Sans' else ('roboto','Roboto')
        f=ImageFont.truetype(str(ROOT/slug/(prefix+('-Italic' if italic else '')+'[wdth,wght].ttf')),size)
        axes=f.get_variation_axes();f.set_variation_by_axes([(700 if bold else 400) if a['name']==b'Weight' else a['default'] for a in axes])
        return f
    suffix='-BoldOblique' if bold and italic else '-Bold' if bold else '-Oblique' if italic else ''
    path=Path('/usr/share/fonts/truetype/dejavu/DejaVuSans'+suffix+'.ttf')
    if path.exists():return ImageFont.truetype(str(path),size)
    from .editor import font
    return font(size)
