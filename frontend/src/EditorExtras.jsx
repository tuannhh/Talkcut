import React,{useState,useEffect,useMemo,useRef} from 'react';
import {Play,MagicWand,Check,CircleNotch} from '@phosphor-icons/react';
import {wordGroups} from './studio-helpers.mjs';
const fmt=n=>`${Math.floor(n/60).toString().padStart(2,'0')}:${(n%60).toFixed(2).padStart(5,'0')}`;

function TranscriptRow({group,time,onSeek,onEdit,onDirty}){
 const original=group.map(w=>w.text).join(' '),[text,setText]=useState(original),[editing,setEditing]=useState(false);
 useEffect(()=>{if(!editing)setText(original);},[original,editing]);
 return <article className={time>=group[0].start&&time<group.at(-1).end?'speaking':''}><header><button onClick={()=>onSeek(group[0].start)}>{fmt(group[0].start)} → {fmt(group.at(-1).end)}</button><span>{group[0].speaker||'Lời thoại'}</span></header><textarea className="sentence-input" aria-label={'Lời thoại tại '+fmt(group[0].start)} value={text} rows={Math.max(2,Math.ceil(text.length/40))} onFocus={()=>setEditing(true)} onChange={e=>{setText(e.target.value);onDirty();}} onBlur={()=>{if(text!==original)onEdit(group,text);setEditing(false);}}/></article>;
}
export function Transcript({words,time,onSeek,onEdit,frameWords,onDirty}){
 const [mode,setMode]=useState('sentence');
 const groups=useMemo(()=>wordGroups(words,mode==='sentence'?28:frameWords,mode==='sentence'?10:100),[words,mode,frameWords]);
 return <><div className="transcript-modes"><button className={mode==='sentence'?'active':''} onClick={()=>setMode('sentence')}>Theo câu</button><button className={mode==='frame'?'active':''} onClick={()=>setMode('frame')}>Theo khung phụ đề</button></div><p className="helper">Sửa trực tiếp trong ô. Bấm mốc thời gian để nghe lại. Chữ thêm dùng chung nhịp với từ gần nhất; các mốc phát âm gốc được giữ.</p><div className="sentence-editor">{groups.map(g=><TranscriptRow key={mode+':'+g[0].start} group={g} time={time} onSeek={onSeek} onEdit={onEdit} onDirty={onDirty}/>)}</div></>;
}
export function TextControls({prefix,label,settings,onChange,Slider}){
 return <details className="text-controls"><summary>{label} · kiểu chữ & vị trí</summary><label className="field"><span>Màu chữ {label.toLowerCase()}</span><input aria-label={'Màu chữ '+label} type="color" value={settings[prefix+'_color']} onChange={e=>onChange(prefix+'_color',e.target.value)}/></label><Slider label={'Cỡ chữ '+label} min={28} max={prefix==='intro'?100:110} step={2} value={settings[prefix+'_size']} format={v=>v+' px'} onChange={v=>onChange(prefix+'_size',v)}/><Slider label={'Vị trí ngang '+label} min={.1} max={.9} value={settings[prefix+'_x']} onChange={v=>onChange(prefix+'_x',v)}/><Slider label={'Vị trí dọc '+label} min={.12} max={prefix==='intro'?.8:.83} value={settings[prefix+'_y']} onChange={v=>onChange(prefix+'_y',v)}/><Slider label={'Độ rộng '+label} min={.3} max={.9} value={settings[prefix+'_width']} onChange={v=>onChange(prefix+'_width',v)}/></details>;
}
export function VoiceControls({settings,onChange,post,notify,media}){
 const [working,setWorking]=useState(''),[plan,setPlan]=useState(null),[spoken,setSpoken]=useState(''),[audio,setAudio]=useState(null);
 const generation=useRef(0);
 useEffect(()=>{generation.current++;setPlan(null);setSpoken('');setAudio(null);},[settings.intro_text,settings.intro_voice,settings.intro_voice_mode,JSON.stringify(settings.intro_voice_profile)]);
 async function run(key,fn){setWorking(key);const token=generation.current;try{await fn(()=>token===generation.current);}catch(e){notify(e.message,true);}finally{setWorking('');}}
 async function listen(sample){await run(sample?'sample':'listen',async current=>{const result=await post('/tts/preview',{voice:settings.intro_voice,mode:settings.intro_voice_mode,profile:settings.intro_voice_profile,...(sample?{}:{text:settings.intro_text,approval_id:settings.intro_approval_id})});if(current())setAudio(result.path);});}
 return <div className="voice-controls"><p className="helper">{settings.intro_voice_mode==='designed'?'Giọng tạo theo tùy chọn.':'Giọng dựng sẵn của Google.'} Nút nghe mẫu đọc: “Chào mừng bạn đến với công cụ cắt video tự động bằng AI của MISA”.</p><div className="voice-buttons"><button className="secondary small" disabled={!!working} onClick={()=>listen(true)}>{working==='sample'?<CircleNotch className="spin"/>:<Play/>}Nghe mẫu giọng</button><button className="secondary small" disabled={!!working||!settings.intro_text.trim()} onClick={()=>listen(false)}>{working==='listen'?<CircleNotch className="spin"/>:<Play/>}Nghe lời mở đầu</button></div>{audio&&<audio key={audio} controls autoPlay src={media(audio)}/>}<button className="secondary small full" disabled={!!working||!settings.intro_text.trim()} onClick={()=>run('normalize',async current=>{const p=await post('/tts/normalize',{text:settings.intro_text});if(current()){setPlan(p);setSpoken(p.tts_text);}})}><MagicWand/>Kiểm tra cách đọc theo quy ước</button>{plan&&<div className="tts-review"><span className="tiny-label">BẢN CHỈ DÙNG ĐỂ ĐỌC · {plan.pronunciation_dictionary_version}</span><textarea aria-label="Bản đọc TTS" value={spoken} onChange={e=>setSpoken(e.target.value)} rows={5}/>{plan.warnings.length>0&&<p className="tts-warning">Cần kiểm tra: {plan.warnings.join(', ')}. Bạn có thể sửa cách đọc ở trên; chữ trên video vẫn giữ nguyên.</p>}<details><summary>{plan.spans.length} mục trong lịch sử chuẩn hóa</summary>{plan.spans.map((s,i)=><p key={i}>{s.original} → {s.normalized} <small>{s.category} · {s.rule_id}</small></p>)}</details><button className="primary small full" disabled={!!working||!spoken.trim()} onClick={()=>run('approve',async current=>{const result=await post('/tts/approve',{text:settings.intro_text,tts_text:spoken});if(current()){onChange('intro_approval_id',result.id);notify('Đã duyệt cách đọc. Bấm Lưu để dùng cho bản dựng.');}})}><Check/>Dùng bản đọc này</button></div>}{settings.intro_approval_id&&<p className="helper"><Check/>Đã duyệt bản đọc cho lời mở đầu hiện tại.</p>}</div>;
}

function DraggableTitle({card,media,settings,setting,disabled}){
 const node=useRef(),drag=useRef();
 useEffect(()=>{if(node.current)node.current.style.transform='';},[card.title_path]);
 function start(e,layer){
  e.preventDefault();e.currentTarget.setPointerCapture(e.pointerId);
  const box=node.current.parentElement.getBoundingClientRect();
  drag.current={x:e.clientX,y:e.clientY,box,layer,dx:0,dy:0};
 }
 function move(e){
  const d=drag.current;if(!d)return;
  d.dx=Math.max(.1-settings.intro_title_x,Math.min(.9-settings.intro_title_x,(e.clientX-d.x)/d.box.width));
  d.dy=Math.max(.12-settings.intro_title_y,Math.min(.83-settings.intro_title_y,(e.clientY-d.y)/d.box.height));
  node.current.style.transform=`translate(${d.dx*d.box.width}px,${d.dy*d.box.height}px)`;
 }
 function end(){const d=drag.current;if(!d)return;drag.current=null;setting('intro_title_x',settings.intro_title_x+d.dx);setting('intro_title_y',settings.intro_title_y+d.dy);}
 return <div ref={node} className="title-drag-surface"><img className="intro-rendered" src={media(card.title_path)} alt="" draggable={false}/>{!disabled&&card.layers.map(layer=><div key={layer.prefix} className="intro-drag-handle" role="button" tabIndex={0} aria-label="Di chuyển tiêu đề clip" title="Kéo tiêu đề; dùng các thanh vị trí để chỉnh chính xác" style={{left:layer.x*100+'%',top:layer.y*100+'%',width:layer.width*100+'%',height:layer.height*100+'%'}} onPointerDown={e=>start(e,layer)} onPointerMove={move} onPointerUp={end} onPointerCancel={()=>{drag.current=null;node.current.style.transform='';}}/>)}</div>;
}

export function IntroCanvas({clip,post,media,moveText,notify,imageDrag,setting,stopImageDrag}){
 const [card,setCard]=useState(null),[sound,setSound]=useState(null),[time,setTime]=useState(0),[busy,setBusy]=useState(false);
 const audio=useRef(),drag=useRef(null),voiceGeneration=useRef(0),s=clip.settings;
 const signature=JSON.stringify([clip.id,clip.title,clip.start,clip.end,s]);
 const voiceSignature=JSON.stringify([clip.id,s.intro_text,s.intro_voice,s.intro_voice_mode,s.intro_voice_profile,s.intro_approval_id,s.intro_caption_enabled]);
 useEffect(()=>{voiceGeneration.current++;audio.current?.pause();setSound(null);setTime(0);},[voiceSignature]);
 useEffect(()=>{let active=true;const timer=setTimeout(()=>{post(`/clips/${clip.id}/intro-preview`,{title:clip.title,summary:clip.summary,start:clip.start,end:clip.end,settings:s,words:[]}).then(r=>active&&setCard(r)).catch(e=>active&&notify(e.message,true));},180);return()=>{active=false;clearTimeout(timer);};},[signature]);
 async function playIntro(){const generation=voiceGeneration.current;setBusy(true);try{const r=await post(`/clips/${clip.id}/intro-audio`,{title:clip.title,summary:clip.summary,start:clip.start,end:clip.end,settings:s,words:[]});if(generation===voiceGeneration.current){setSound(r);setTime(0);}}catch(e){notify(e.message,true);}finally{setBusy(false);}}
 const group=wordGroups(sound?.words||[],s.caption_words,100).find(g=>time>=g[0].start&&time<g.at(-1).end)||[];
 return <div className="intro-preview">{card?<><img className="intro-rendered" src={media(card.base_path||card.path)} alt="Xem trước intro với ảnh đại diện và tiêu đề"/>{card.title_path&&<DraggableTitle card={card} media={media} settings={s} setting={setting} disabled={imageDrag}/>}{imageDrag&&<div className="image-drag-layer" onPointerDown={e=>{e.currentTarget.setPointerCapture(e.pointerId);drag.current={x:e.clientX,y:e.clientY,px:s.intro_image_x,py:s.intro_image_y};}} onPointerMove={e=>{if(e.buttons!==1||!drag.current)return;const r=e.currentTarget.getBoundingClientRect();setting('intro_image_x',Math.max(0,Math.min(1,drag.current.px-(e.clientX-drag.current.x)/r.width)));setting('intro_image_y',Math.max(0,Math.min(1,drag.current.py-(e.clientY-drag.current.y)/r.height)));}}><button onClick={stopImageDrag}>Xong căn ảnh</button></div>}
 {s.intro_caption_enabled&&group.length>0&&<div className="live-caption intro-caption-drag" role="button" tabIndex={0} aria-label="Di chuyển phụ đề intro" onPointerDown={e=>e.currentTarget.setPointerCapture(e.pointerId)} onPointerMove={e=>{if(e.buttons!==1)return;const r=e.currentTarget.parentElement.getBoundingClientRect();setting('intro_caption_x',Math.max(.1,Math.min(.9,(e.clientX-r.left)/r.width)));setting('intro_caption_y',Math.max(.08,Math.min(.95,(e.clientY-r.top)/r.height)));}} style={{left:s.intro_caption_x*100+'%',top:s.intro_caption_y*100+'%',fontSize:`${s.caption_size/1080*100}cqw`}}>{group.map((w,i)=><React.Fragment key={i}><span style={{color:time>=w.start&&time<w.end?s.caption_color:'#fff'}}>{w.text}</span>{' '}</React.Fragment>)}</div>}
 {s.intro_tts&&!imageDrag&&<div className="intro-audio-controls">{sound?<audio ref={audio} controls autoPlay src={media(sound.path)} onTimeUpdate={e=>setTime(e.target.currentTime)}/>:<button disabled={busy} onClick={playIntro}>{busy?<CircleNotch className="spin"/>:<Play/>}{busy?'Đang căn voice và karaoke…':'Phát intro'}</button>}</div>}
 </>:<span className="intro-loading">Đang cập nhật khung intro…</span>}</div>;
}
