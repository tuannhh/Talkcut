"""Deterministic Vietnamese narration normalization based on the user's r4 reference.

Classification claims source spans before pronunciation rendering; offsets always
refer to the untouched source. Unknown/ambiguous spans are preserved for review.
"""
import datetime
import hashlib
import json
import re
import unicodedata
from pathlib import Path
from pydantic import BaseModel, Field

VERSION='talkcut-r4-1.0'
DICTIONARY=json.loads((Path(__file__).parent/'approved_pronunciations.json').read_text())
D='không một hai ba bốn năm sáu bảy tám chín'.split()
LETTERS=dict(zip('AĂÂBCDĐEÊFGHIJKLMNOÔƠPQRSTUƯVWXYZ',['a','á','ớ','bê','xê','dê','đê','e','ê','ép','giê','hát','i','giây','ca','lờ','mờ','nờ','o','ô','ơ','pê','quy','rờ','ét','tê','u','ư','vê','vê kép','ích','i','dét']))
TECH={'AI','CEO','KPI','API','CRM','ERP','SaaS','B2B','IT','R&D','STT','TTS','Full HD','YouTube','Google','BMW','Bosch'}
ENTITIES={'MISA','MISA-AMIS'}
LEGAL={'NĐ-CP','QĐ-TTg','TT-BTC','UBND','HĐND','QH','NQ-CP'}

class NormalizeRequest(BaseModel):
    text:str=Field(min_length=1,max_length=2000)
    context_tags:list[str]=Field(default_factory=list,max_length=20)
    overrides:dict[str,str]=Field(default_factory=dict,max_length=100)

class VoicePreviewRequest(BaseModel):
    voice:str=Field(default='Kore',pattern=r'^[A-Za-z]{2,30}$')
    text:str=Field(default='Chào mừng bạn đến với công cụ cắt video tự động bằng AI của MISA',min_length=1,max_length=2000)
    approval_id:str|None=None

class ApprovalRequest(BaseModel):
    text:str=Field(min_length=1,max_length=2000)
    tts_text:str=Field(min_length=1,max_length=4000)


def digits(s):return ' '.join(D[int(c)] for c in s if c.isdigit())

def year(s):
    s=str(s); n=int(s[-2:])
    if len(s)==4 and 1<=n<=9:
        return ('hai lẻ ' if s[:2]=='20' else digits(s[:2])+' linh ')+('tư' if n==4 else D[n])
    parts=[D[int(c)] for c in s]
    if s[-1]=='4':parts[-1]='tư'
    if s[-1]=='5':parts[-1]='lăm'
    return ' '.join(parts)


def quantity(value):
    n=int(str(value).replace('.',''))
    if n==0:return D[0]
    if n<0:return 'âm '+quantity(-n)
    groups=[]
    while n:
        groups.append(n%1000);n//=1000
    scales=['','nghìn','triệu','tỷ','nghìn tỷ','triệu tỷ','tỷ tỷ']
    if len(groups)>len(scales):raise ValueError('Số quá lớn')
    out=[]
    for i in range(len(groups)-1,-1,-1):
        g=groups[i]
        if not g:continue
        h,t,u=g//100,g//10%10,g%10
        full=i<len(groups)-1
        parts=[]
        if h or full:parts += [D[h],'trăm']
        if t>1:parts += [D[t],'mươi']
        elif t==1:parts+=['mười']
        elif (h or full) and u:parts+=['linh']
        if u:
            parts += ['mốt' if u==1 and t>1 else 'lăm' if u==5 and t>0 else 'tư' if u==4 and t!=1 and (t>1 or h or full) else D[u]]
        if scales[i]:parts.append(scales[i])
        out.append(' '.join(parts))
    return ' '.join(out)


def numeric(s):
    if ',' in s:
        a,b=s.split(',');return digits(a.replace('.',''))+' phẩy '+digits(b)
    return quantity(s)


def legal(s):return ' '.join(LETTERS.get(c.upper(),c) for c in s if c not in '-/')


def normalize(text, context_tags=None, overrides=None):
    if not text.strip() or len(text)>2000:raise ValueError('Lời đọc cần từ 1 đến 2.000 ký tự.')
    spans=[]; claimed=[False]*len(text);tags=set(context_tags or []);overrides=overrides or {}
    def add(a,b,category,spoken,rule,warning=None):
        if a==b or any(claimed[a:b]):return
        claimed[a:b]=[True]*(b-a)
        spans.append({'start':a,'end':b,'original':text[a:b],'normalized':spoken,'category':category,'rule_id':rule,'confidence':0 if warning else 1,'warning_codes':[warning] if warning else []})
    def scan(pattern,category,render,rule,flags=0):
        for m in re.finditer(pattern,text,flags):
            if any(claimed[m.start():m.end()]):continue
            try:
                result=render(m)
                if result is None:continue
                spoken,warning=result if isinstance(result,tuple) else (result,None)
                add(m.start(),m.end(),category,spoken,rule,warning)
            except (ValueError,OverflowError):add(m.start(),m.end(),category,m[0],rule,'INVALID_'+category)
    # Protected source spans have priority even over explicit pronunciation overrides.
    scan(r'```[\s\S]*?```|`[^`]*`|https?://[^\s]+|[\w.+-]+@[\w.-]+\.\w+|(?<!\S)/(?:[\w.-]+/)+[\w.-]+|\b[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\b|\bv\d+\.\d+\.\d+(?:[.-]\w+)*\b','PROTECTED',lambda m:(m[0],'PROTECTED_CONTENT'),'PROTECT_001')
    # Dotted thousands are numeric, not versions unless prefixed by v (fixed below in tests).
    scan(r'(?m)^\s*[-+*•]\s+','BULLET',lambda m:'','BULLET_001')
    def phrases(entries,category,rule):
        if not entries:return
        pattern=r'(?<!\w)(?:'+'|'.join(re.escape(k) for k in sorted(entries,key=len,reverse=True))+r')(?!\w)'
        scan(pattern,category,lambda m:entries[m[0]],rule)
    for k,v in overrides.items():
        if not k or len(k)>120 or not v.strip() or len(v)>300:raise ValueError('Cách đọc tùy chỉnh không hợp lệ.')
    phrases({k:v for k,v in DICTIONARY['entries'].items() if ' ' in k},'ENTITY','APPROVED_PRONUNCIATION_001')
    phrases({k:k for k in TECH|ENTITIES},'ENTITY','ENTITY_PRESERVE_001')
    # Protect alphanumeric identifiers before any constituent number/acronym.
    scan(r'(?<!\w)(?=[\w-]*[A-Za-z])(?=[\w-]*\d)[A-Za-z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)+\b|\b[A-Z]{2,}\d+[A-Z0-9]*\b','CODE',lambda m:(m[0],'PROTECTED_CODE'),'CODE_001')
    def date(m):
        d,mo,y=[int(m[i]) for i in (1,2,3)];datetime.date(y,mo,d)
        return ('mùng ' if d<10 else '')+quantity(d)+' tháng '+('tư' if mo==4 else quantity(mo))+' năm '+year(str(y))
    scan(r'(?<!\d)(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})(?!\d)','DATE',date,'DATE_001')
    def time(m):
        h=int(m[1]);minute=int(m[2] or 0);ampm=m[3]
        if h>23 or minute>59 or (ampm and not 1<=h<=12):raise ValueError()
        return quantity(h)+' giờ'+(' '+quantity(minute)+' phút' if minute else '')+(' sáng' if ampm=='AM' else ' tối' if ampm else '')
    scan(r'\b(\d{1,2}h\d{2})\s*[-–—]\s*(\d{1,2}h\d{2})\b','TIME_RANGE',lambda m:normalize(m[1])['tts_text']+' đến '+normalize(m[2])['tts_text'],'TIME_RANGE_001')
    scan(r'\b(\d{1,2})(?:[h:](\d{2})|\s+(AM|PM))\b','TIME',time,'TIME_001')
    def month(m):
        mo=int(m[1])
        if not 1<=mo<=12:raise ValueError()
        return 'tháng '+('tư' if mo==4 else quantity(mo))+' năm '+year(m[2])
    scan(r'\btháng\s+(\d{1,2})/(\d{4})\b','MONTH_YEAR',month,'MONTH_YEAR_001',re.I)
    def document(m):
        serial,y,suffix=m[1],m[2],m[3]
        before=text[max(0,m.start()-20):m.start()]
        if not suffix and len(serial)<=2 and 1<=int(serial)<=12 and not re.search(r'(số|Số)\s*$',before):return m[0],'AMBIGUOUS_MONTH_DOCUMENT'
        return (digits(serial) if len(serial)>=3 else quantity(serial))+' '+year(y)+(' '+legal(suffix) if suffix else '')
    scan(r'(?<!\w)(\d{1,5})/(\d{4})(?:/([A-Za-zĐđ]+(?:-[A-Za-zĐđ]+)*))?(?!\w)','DOCUMENT_ID',document,'DOCUMENT_ID_001')
    scan(r'(?i)\b(?:điện thoại|mã số thuế|MST|CCCD|tài khoản|hotline)\s*:?\s*\d[\d .-]{4,}\d','IDENTIFIER',lambda m:re.sub(r'\d[\d .-]*\d',lambda x:digits(x[0]),m[0]),'IDENTIFIER_001')
    scan(r'\b0\d{7,}\b','IDENTIFIER',lambda m:(m[0],'UNKNOWN_IDENTIFIER'),'IDENTIFIER_UNKNOWN_001')
    def ratio(m):
        prefix=text[max(0,m.start()-30):m.start()].lower()
        if m[2]==':' and (m[1],m[3]) in [('16','9'),('9','16'),('4','3'),('1','1')]:return quantity(m[1])+' trên '+quantity(m[3])
        if 'phân số' in prefix:return quantity(m[1])+' phần '+quantity(m[3])
        if 'tỷ lệ' in prefix:return quantity(m[1])+' trên '+quantity(m[3])
        return m[0],'AMBIGUOUS_RATIO'
    scan(r'(?<![\d/])(\d{1,3})([:/])(\d{1,3})(?![\d/])','RATIO',ratio,'RATIO_001')
    num=r'\d+(?:\.\d+)*(?:,\d+)?'
    def yrange(m):return year(m[1])+' đến '+year(m[2])
    scan(r'\b((?:18|19|20)\d{2})\s*[-–—]\s*((?:18|19|20)\d{2})\b','YEAR_RANGE',yrange,'YEAR_RANGE_001')
    scan(r'(?<!\w)('+num+r')\s*[-–—]\s*('+num+r')(%?)','RANGE',lambda m:numeric(m[1])+' đến '+numeric(m[2])+(' phần trăm' if m[3] else ''),'RANGE_001')
    # Contextual years are classified before the generic quantity renderer.
    scan(r'(?i)\b(?:năm|niên độ|giai đoạn)\s+(\d{4})\b','YEAR',lambda m:m[0][:-4]+year(m[1]),'YEAR_001')
    # Malformed grouping is preserved as one span, never partially normalized.
    def badnumber(m):
        s=m[0].split(',')[0]
        return (m[0],'INVALID_THOUSANDS') if '.' in s and not re.fullmatch(r'\d{1,3}(?:\.\d{3})+',s) else None
    scan(r'(?<!\w)'+num,'NUMBER',badnumber,'NUMBER_VALIDATE_001')
    scan(r'(?<!\w)([+−-])('+num+r')(%?)','SIGNED_NUMBER',lambda m:('tăng ' if m[1]=='+' else 'giảm ')+numeric(m[2])+(' phần trăm' if m[3] else ''),'SIGN_PERCENT_001')
    scan(r'(?<!\w)('+num+r')\s*(VNĐ|VND|đ|₫)(?!\w)','CURRENCY',lambda m:numeric(m[1])+' đồng','CURRENCY_001')
    scan(r'(?<!\w)('+num+r')(%?)(?!\w)','QUANTITY',lambda m:numeric(m[1])+(' phần trăm' if m[2] else ''),'QUANTITY_001')
    phrases({k:legal(k) for k in LEGAL},'VI_LEGAL_ACRONYM','LEGAL_001')
    def tb(m):
        after=text[m.end():m.end()+60].lstrip()
        if re.match(r'(Pháp chế|Nhân sự|Tài chính|Kế toán|Kiểm soát|Truyền thông)\b',after) or 'org_title' in tags:return 'Trưởng ban'
        if re.match(r'[+−-]?\d',after) or tags&{'metric','statistic','average'}:return 'trung bình'
        return m[0],'AMBIGUOUS_TB_MEANING'
    scan(r'\bTB\b','CONTEXTUAL_ABBREVIATION',tb,'APPROVED_TB_CONTEXT_001')
    entries=DICTIONARY['entries']
    def approved(m):
        key=m[0]
        if key in {'AM','SM','CT','DN','GP','VP'} and not tags&{'business_internal','org_title','product'}:
            if key=='AM' and re.match(r'\s+phụ trách khách hàng',text[m.end():]):return entries[key]
            return key,'AMBIGUOUS_SHORT_ACRONYM'
        return entries[key]
    scan(r'(?<!\w)(?:'+'|'.join(re.escape(k) for k in sorted(entries,key=len,reverse=True))+r')(?!\w)','APPROVED_PRONUNCIATION',approved,'APPROVED_PRONUNCIATION_001')
    phrases(overrides,'USER_PRONUNCIATION','USER_APPROVED_001')
    scan(r'\b[A-ZĐ]{2,}\b','UNKNOWN_ACRONYM',lambda m:(m[0],'UNKNOWN_ACRONYM'),'UNKNOWN_001')
    # Normalize decomposed Unicode only at rendering; offsets remain in original text.
    for m in re.finditer(r'\S+',text):
        if not any(claimed[m.start():m.end()]) and unicodedata.normalize('NFC',m[0])!=m[0]:
            add(m.start(),m.end(),'UNICODE',unicodedata.normalize('NFC',m[0]),'UNICODE_NFC_001')
    for span in spans:
        if span['category'] in {'ENTITY','APPROVED_PRONUNCIATION','CONTEXTUAL_ABBREVIATION','UNKNOWN_ACRONYM'} and span['original'] in overrides:
            span.update(normalized=overrides[span['original']], rule_id='USER_APPROVED_001', confidence=1, warning_codes=[])
    spans.sort(key=lambda s:s['start'])
    parts=[];cursor=0
    for s in spans:parts += [text[cursor:s['start']],s['normalized']];cursor=s['end']
    parts.append(text[cursor:])
    warnings=sorted({c for s in spans for c in s['warning_codes']})
    return {'source_text':text,'display_text':text,'tts_text':''.join(parts),'spans':spans,'warnings':warnings,'requires_review':bool(warnings),'normalizer_version':VERSION,'pronunciation_dictionary_version':DICTIONARY['version'],'locale':'vi-VN','source_hash':hashlib.sha256(text.encode()).hexdigest()}
