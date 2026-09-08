import React,{useState,useEffect} from 'react';
import {Sparkle,Image as ImageIcon,CircleNotch,Play,ArrowsOutCardinal} from '@phosphor-icons/react';
import {VoiceControls} from './EditorExtras.jsx';

const profiles=[
 ['age','Độ tuổi',[['thanhnien','Thanh niên'],['trungnien','Trung niên'],['nguoidilam','Người đi làm']]],
 ['gender','Giới tính',[['female','Nữ'],['male','Nam']]],
 ['region','Miền',[['bac','Bắc'],['trung','Trung'],['nam','Nam']]],
 ['style','Phong cách đọc',[['tintuc','Tin tức'],['thoisu','Thời sự'],['tvc','TVC – quảng cáo']]],
 ['mood','Tâm trạng',[['neutral','Trung tính'],['cheerful','Vui vẻ'],['energetic','Năng động']]],
 ['speed','Tốc độ đọc',[[1,'Bình thường · 1x'],[1.2,'Nhanh · 1,2x']]],
];
export function IntroEditor({clip,setting,setPreview,suggestIntro,busy,assets,refresh,post,notify,media,Field,Slider,Toggle,AssetPicker,onUpload,onImageDrag}){
 const s=clip.settings,[frames,setFrames]=useState([]),[loading,setLoading]=useState('');
 const body=()=>({title:clip.title,summary:clip.summary,start:clip.start,end:clip.end,settings:s,words:[]});
 async function run(name,fn){setLoading(name);try{await fn();}catch(e){notify(e.message,true);}finally{setLoading('');}}
 async function thumbnails(regenerate=false){await run('frames',async()=>{const r=await post(`/clips/${clip.id}/intro-frames${regenerate?'?refresh=true':''}`,body());setFrames(r.frames);await refresh();});}
 useEffect(()=>{let active=true;setFrames([]);post(`/clips/${clip.id}/intro-frames`,body()).then(r=>active&&setFrames(r.frames)).catch(e=>active&&notify(e.message,true));return()=>{active=false;};},[clip.id,clip.start,clip.end]);
 return <div className="intro-editor">
  <div className="intro-section-heading"><ImageIcon/><strong>Hình ảnh intro</strong><span>9:16</span></div>
  <Toggle label="Ảnh nền intro phía dưới" checked={s.intro_background_enabled} onChange={v=>setting('intro_background_enabled',v)}/>
  {s.intro_background_enabled&&<><AssetPicker label="Ảnh nền intro" kind="image" value={s.intro_asset} assets={assets} onChange={v=>setting('intro_asset',v)} onUpload={()=>onUpload('intro_asset')}/><Slider label="Kích thước ảnh nền" min={.5} max={1.5} value={s.intro_background_scale} format={v=>Math.round(v*100)+'%'} onChange={v=>setting('intro_background_scale',v)}/><p className="helper">Nền được đặt chồng lên phần dưới của ảnh nhân vật. PNG trong suốt giữ nguyên phần nhìn xuyên qua.</p></>}
  <div className="freeze-heading"><span>Ảnh đại diện từ clip</span><button className="text-action" disabled={!!loading} onClick={()=>thumbnails(true)}>{loading==='frames'?<CircleNotch className="spin"/>:<Sparkle/>}Gợi ý 3 ảnh khác</button></div>
  <div className="freeze-grid">{frames.map((f,i)=><button key={f.id} className={s.intro_image_asset===f.id||(!s.intro_image_asset&&i===0)?'selected':''} onClick={()=>{setting('intro_image_asset',f.id);setting('intro_image_x',.5);setting('intro_image_y',.5);setting('intro_image_zoom',1);setPreview('intro');}}><img src={media(f.path)} alt={'Freeze frame '+(i+1)}/><span>{i===0?'Khung đầu tiên':'Ảnh '+(i+1)}</span></button>)}</div>
  {!frames.length&&<p className="helper">Đang lấy khung hình đầu và hai gợi ý trong clip…</p>}
  <AssetPicker label="Ảnh nhân vật hoặc PNG phủ lên freeze frame" kind="image" value={s.intro_image_asset} assets={assets.filter(a=>a.source_time==null||(a.source_id===clip.source_id&&a.source_time>=clip.start&&a.source_time<clip.end))} onChange={v=>{setting('intro_image_asset',v);setPreview('intro');}} onUpload={()=>onUpload('intro_image_asset')}/>
  <button className="secondary small full" onClick={()=>{setPreview('intro');onImageDrag();}}><ArrowsOutCardinal/>Kéo ảnh để căn khung</button>
  <details className="text-controls"><summary>Crop và vị trí ảnh</summary><Slider label="Phóng ảnh intro" min={1} max={3} step={.05} value={s.intro_image_zoom} format={v=>v.toFixed(2)+'×'} onChange={v=>setting('intro_image_zoom',v)}/><Slider label="Dịch ảnh ngang" value={s.intro_image_x} onChange={v=>setting('intro_image_x',v)}/><Slider label="Dịch ảnh dọc" value={s.intro_image_y} onChange={v=>setting('intro_image_y',v)}/></details>
  <div className="section-divider"/><div className="intro-section-heading"><strong>Tiêu đề trên video</strong><button className="text-action" disabled={!!loading} onClick={()=>run('title',async()=>{const r=await post(`/clips/${clip.id}/intro-title`,body());setting('intro_title_text',r.title);setPreview('intro');})}><Sparkle/>AI gợi ý</button></div>
  <Field label="Nội dung tiêu đề"><textarea rows={2} maxLength={180} value={s.intro_title_text} placeholder={clip.title} onChange={e=>setting('intro_title_text',e.target.value)}/></Field>
  <div className="title-case-buttons">{[['original','Viết bình thường'],['upper','VIẾT HOA']].map(([v,label])=><button key={v} className={s.intro_title_case===v?'active':''} onClick={()=>setting('intro_title_case',v)}>{label}</button>)}</div>
  <Field label="Từ cần highlight"><input placeholder="Ví dụ: công nghệ cao" value={s.intro_title_highlight} maxLength={100} onChange={e=>setting('intro_title_highlight',e.target.value)}/></Field>
  <div className="title-colors"><label>Màu chữ<input aria-label="Màu chữ tiêu đề" type="color" value={s.intro_title_color} onChange={e=>setting('intro_title_color',e.target.value)}/></label><label>Màu highlight<input aria-label="Màu highlight tiêu đề" type="color" value={s.intro_title_highlight_color} onChange={e=>setting('intro_title_highlight_color',e.target.value)}/></label></div>
  <div className="title-toolbar" role="toolbar" aria-label="Định dạng tiêu đề">
   <label>Cỡ chữ<input aria-label="Cỡ chữ tiêu đề" type="number" min={28} max={110} value={s.intro_title_size} onChange={e=>{const v=Number(e.target.value);if(v>=28&&v<=110)setting('intro_title_size',v);}}/></label>
   <select aria-label="Căn lề tiêu đề" value={s.intro_title_align||'center'} onChange={e=>setting('intro_title_align',e.target.value)}>{[['left','Căn trái'],['center','Căn giữa'],['right','Căn phải'],['justify','Căn đều hai bên']].map(([v,label])=><option key={v} value={v}>{label}</option>)}</select>
   {[['bold','Đậm','B'],['italic','Nghiêng','I'],['underline','Gạch chân','U']].map(([key,label,text])=><button key={key} aria-label={label+' tiêu đề'} aria-pressed={!!s['intro_title_'+key]} className={s['intro_title_'+key]?'active':''} onClick={()=>setting('intro_title_'+key,!s['intro_title_'+key])} style={{fontWeight:key==='bold'?800:400,fontStyle:key==='italic'?'italic':'normal',textDecoration:key==='underline'?'underline':'none'}}>{text}</button>)}
  </div>
  <details className="text-controls"><summary>Vị trí tiêu đề</summary><Slider label="Tiêu đề ngang" min={.1} max={.9} value={s.intro_title_x} onChange={v=>setting('intro_title_x',v)}/><Slider label="Tiêu đề dọc" min={.12} max={.83} value={s.intro_title_y} onChange={v=>setting('intro_title_y',v)}/><Slider label="Độ rộng tiêu đề" min={.3} max={.9} value={s.intro_title_width} onChange={v=>setting('intro_title_width',v)}/></details>
  <p className="helper">Kéo tiêu đề trực tiếp trên hình để đổi vị trí.</p>
  <div className="section-divider"/><div className="intro-section-heading"><strong>Lời mở đầu & giọng đọc</strong><button className="text-action" disabled={!!busy} onClick={suggestIntro}><Sparkle/>AI gợi ý</button></div>
  <Field label="Lời mở đầu"><textarea rows={3} maxLength={700} value={s.intro_text} onChange={e=>setting('intro_text',e.target.value)}/></Field>
  <Toggle label="Đọc lời mở đầu" checked={s.intro_tts} onChange={v=>setting('intro_tts',v)}/>
  {s.intro_tts?<><div className="voice-mode-options" role="radiogroup" aria-label="Cách tạo giọng đọc">{[['prebuilt','Sử dụng voice có sẵn của Google'],['designed','Tạo sinh giọng đọc theo tùy chọn']].map(([v,label])=><label key={v}><input type="radio" name="voice-mode" checked={s.intro_voice_mode===v} onChange={()=>setting('intro_voice_mode',v)}/><span>{label}</span></label>)}</div>
   {s.intro_voice_mode==='prebuilt'?<Field label="Chất giọng Google"><select value={s.intro_voice} onChange={e=>setting('intro_voice',e.target.value)}>{['Kore','Puck','Charon','Aoede','Fenrir','Leda','Orus','Zephyr'].map(v=><option key={v}>{v}</option>)}</select></Field>:<div className="voice-profile-grid">{profiles.map(([key,label,options])=><Field key={key} label={label}><select value={s.intro_voice_profile[key]} onChange={e=>setting('intro_voice_profile',{...s.intro_voice_profile,[key]:key==='speed'?Number(e.target.value):e.target.value})}>{options.map(([v,t])=><option key={v} value={v}>{t}</option>)}</select></Field>)}<p className="helper">Gemini tạo giọng theo mô tả. Nghe thử để chọn ngữ điệu và vùng miền phù hợp.</p></div>}
   <Toggle label="Hiển thị phụ đề karaoke ở Intro" checked={s.intro_caption_enabled} onChange={v=>setting('intro_caption_enabled',v)}/><Slider label="Vị trí phụ đề intro" min={.08} max={.95} value={s.intro_caption_y} onChange={v=>setting('intro_caption_y',v)}/><Slider label="Phụ đề intro ngang" min={.1} max={.9} value={s.intro_caption_x} onChange={v=>setting('intro_caption_x',v)}/><p className="helper">Kéo phụ đề trên khung để đặt trên logo hoặc dưới tiêu đề. Karaoke dùng kiểu chữ trong tab Phụ đề. Lời dẫn không còn hiển thị thành một khối chữ tĩnh.</p><VoiceControls settings={s} onChange={setting} post={post} notify={notify} media={media}/>
   <button className="secondary small full" disabled={!!loading} onClick={()=>run('play',async()=>{await post(`/clips/${clip.id}/intro-audio`,body());setPreview('intro');notify('Đã chuẩn bị karaoke intro. Bấm Phát intro trên khung hình.');})}><Play/>{loading==='play'?'Đang chuẩn bị karaoke…':'Chuẩn bị nghe và xem karaoke'}</button>
  </>:<Slider label="Thời lượng intro" value={s.intro_seconds} min={2} max={30} step={1} format={v=>v+' giây'} onChange={v=>setting('intro_seconds',v)}/>}
 </div>;
}
