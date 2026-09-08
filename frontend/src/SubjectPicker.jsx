import React,{useRef,useState} from 'react';
import {focusGeometry,staticCenter} from './studio-helpers.mjs';
export function SubjectPicker({clip,time,source,plan,media,onApply,onClose}){
 const s=clip.settings,video=useRef(),box=useRef();
 const cuts=plan?.visual_cuts||[];const [t,setTime]=useState(Math.max(clip.start,Math.min(time,clip.end-.01))),[ready,setReady]=useState(false);
 const a=clip.start+(cuts.filter(x=>x<=t-clip.start).at(-1)||0),b=clip.start+(cuts.find(x=>x>t-clip.start)??clip.end-clip.start);
 const [scope,setScope]=useState(cuts.length?'scene':'all'),[start,setStart]=useState(a),[end,setEnd]=useState(b),[x,setX]=useState(staticCenter(s,t).x),[y,setY]=useState(staticCenter(s,t).y);
 const info={width:source.width,height:source.height};const p=focusGeometry(info,s,{x,y});
 const left=(p.x-p.cw/info.width/2)*100,top=(p.y-p.ch/info.height/2)*100;
 function choose(e){const r=box.current.getBoundingClientRect();setX(Math.max(0,Math.min(1,(e.clientX-r.left)/r.width)));setY(Math.max(0,Math.min(1,(e.clientY-r.top)/r.height)));}
 return <><p className="helper">Bấm vào người cần giữ trong khung. Crop 9:16 sẽ đứng yên ở vị trí này; nguồn đổi góc máy thì chọn vị trí cho cảnh đó.</p>
 <div ref={box} className="subject-source" style={{aspectRatio:source.width+'/'+source.height,maxWidth:`min(100%, ${52*source.width/source.height}vh)`,margin:'0 auto'}} onPointerDown={e=>{e.currentTarget.setPointerCapture(e.pointerId);choose(e);}} onPointerMove={e=>{if(e.buttons===1)choose(e);}}>
 <video ref={video} src={media(source.preview_path||source.path)} muted playsInline preload="auto" onLoadedMetadata={e=>{e.target.currentTime=t;}} onSeeked={()=>setReady(true)}/>
 <div className="subject-window" style={{left:left+'%',top:top+'%',width:p.cw/info.width*100+'%',height:p.ch/info.height*100+'%'}}><span>Khung dọc cố định</span></div></div>
 <label className="field"><span>Chọn khung hình nguồn · {t.toFixed(2)} giây</span><input aria-label="Chọn khung hình nguồn" type="range" min={clip.start} max={clip.end-.01} step=".05" value={t} onChange={e=>{const next=Number(e.target.value);setTime(next);setReady(false);if(video.current)video.current.currentTime=next;}}/></label>
 <div className="subject-coordinates"><label>Ngang<input aria-label="Vị trí chủ thể ngang" type="range" min="0" max="1" step=".001" value={x} onChange={e=>setX(Number(e.target.value))}/></label><label>Dọc<input aria-label="Vị trí chủ thể dọc" type="range" min="0" max="1" step=".001" value={y} onChange={e=>setY(Number(e.target.value))}/></label></div>
 <label className="field"><span>Áp dụng vị trí</span><select aria-label="Phạm vi khóa chủ thể" value={scope} onChange={e=>setScope(e.target.value)}>{cuts.length>0&&<option value="scene">Cảnh hiện tại ({a.toFixed(2)}–{b.toFixed(2)} giây nguồn)</option>}<option value="range">Khoảng thời gian tự chọn</option><option value="all">Toàn clip · một góc máy cố định</option></select></label>
 {scope==='range'&&<div className="subject-coordinates"><label>Từ giây nguồn<input type="number" aria-label="Khóa từ giây" min={clip.start} max={clip.end} step=".01" value={start} onChange={e=>setStart(Number(e.target.value))}/></label><label>Đến giây nguồn<input type="number" aria-label="Khóa đến giây" min={clip.start} max={clip.end} step=".01" value={end} onChange={e=>setEnd(Number(e.target.value))}/></label></div>}
 <button className="primary full" disabled={!ready||(scope==='range'&&(!(end>start)||start<clip.start||end>clip.end))} onClick={()=>{onApply({x,y,start:scope==='scene'?a:start,end:scope==='scene'?b:end,all:scope==='all'});onClose();}}>Khóa khung tại vị trí này</button></>;
}
