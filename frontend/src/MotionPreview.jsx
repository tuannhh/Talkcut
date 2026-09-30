import React,{useRef,useEffect} from 'react';
import {focusAt,focusGeometry,staticCenter,stackedWindowAt,removedAt,sourceRect} from './studio-helpers.mjs';

// Mirrors backend/stacked_view.py: a 220px seam band (of 1920) blurred from the
// stacked image itself and faded in with a (1-d)^1.4 alpha profile.
const SEAM=Math.round(220*1280/1920),SEAM_MARGIN=60;

export function MotionPreview({video,clip,plan,points,info,media,stacked,removed}){
 const canvas=useRef();const s=clip.settings;
 useEffect(()=>{
  const v=video.current;if(!v||!s.sound_effect||s.sound_effect==='none')return;
  const audio=new Audio('/api/sound-effects/'+s.sound_effect);
  const play=()=>{if(v.currentTime-clip.start<.25&&!v.muted){audio.currentTime=0;audio.volume=v.volume;audio.play().catch(()=>{});}};
  const stop=()=>audio.pause();v.addEventListener('play',play);v.addEventListener('pause',stop);
  return()=>{audio.pause();v.removeEventListener('play',play);v.removeEventListener('pause',stop);};
 },[clip.id,clip.start,s.sound_effect]);
 useEffect(()=>{
  const v=video.current,out=canvas.current;if(!v||!out)return;
  const ctx=out.getContext('2d'),W=720,H=1280;out.width=W;out.height=H;
  const buffers=Array.from({length:3},()=>{const c=document.createElement('canvas');c.width=W;c.height=H;return c;});
  const seam=document.createElement('canvas');seam.width=W;seam.height=SEAM+2*SEAM_MARGIN;
  let previous=null,outgoing=null,activeCut=null;
  const director=!!plan?.director;
  const holds=!director&&(s.calm_short_shots||plan?.reference_tracking)&&plan?.framing_mode===s.crop_mode?plan?.holds||[]:[],images=new Map();
  for(const h of holds){const im=new Image();im.onload=()=>{last=-1;draw();};im.src=media(h.path);images.set(h.start,im);}
  let last=-1,frameId,disposed=false;
  const cuts=(plan?.visual_cuts||points.filter((p,i)=>i&&(p.cut||p.scene!==points[i-1].scene)).map(p=>p.time)).filter(t=>!holds.some(h=>t>=h.start&&t<h.end-.01));
  const size={width:v.videoWidth,height:v.videoHeight};
  function fill(c){
   // Export: blurred cover background with the whole frame contained on top.
   const cover=Math.max(W/v.videoWidth,H/v.videoHeight),contain=Math.min(W/v.videoWidth,H/v.videoHeight);
   c.filter='blur(26px)';c.drawImage(v,(W-v.videoWidth*cover)/2,(H-v.videoHeight*cover)/2,v.videoWidth*cover,v.videoHeight*cover);c.filter='none';
   c.drawImage(v,(W-v.videoWidth*contain)/2,(H-v.videoHeight*contain)/2,v.videoWidth*contain,v.videoHeight*contain);
  }
  function drawStacked(window){
   const half=H/2;size.width=v.videoWidth;size.height=v.videoHeight;
   for(const [part,y0] of [[window.top,0],[window.bottom,half]]){const r=sourceRect(info,size,part);ctx.drawImage(v,r.x,r.y,r.w,r.h,0,y0,W,half);}
   const sc=seam.getContext('2d'),top=half-SEAM/2;
   sc.clearRect(0,0,W,seam.height);sc.globalCompositeOperation='source-over';sc.filter='blur(52px)';
   sc.drawImage(out,0,top-SEAM_MARGIN,W,seam.height,0,0,W,seam.height);sc.filter='none';
   const fade=sc.createLinearGradient(0,SEAM_MARGIN,0,SEAM_MARGIN+SEAM);
   for(let i=0;i<=10;i++){const d=Math.abs(i/10-.5)*2;fade.addColorStop(i/10,`rgba(0,0,0,${(.92*Math.pow(1-d,1.4)).toFixed(3)})`);}
   sc.globalCompositeOperation='destination-in';sc.fillStyle=fade;sc.fillRect(0,0,W,seam.height);
   sc.globalCompositeOperation='source-over';
   ctx.drawImage(seam,0,SEAM_MARGIN,W,SEAM,0,top,W,SEAM);
  }
  function draw(){
   if(disposed||v.readyState<2)return;
   const t=v.currentTime-clip.start,index=Math.round(t*30);
   // The export removes these pauses from picture and sound: playback skips them too.
   const gap=!v.paused&&removedAt(removed,t);
   if(gap){v.currentTime=clip.start+gap[1]+.001;return;}
   if(index===last)return;
   if(last<0||index<last||index-last>10){previous=null;outgoing=null;activeCut=null;}
   last=index;
   const frame=buffers.find(b=>b!==previous&&b!==outgoing);const c=frame.getContext('2d');c.fillStyle='#000';c.fillRect(0,0,W,H);
   const hold=holds.find(h=>t>=h.start&&t<h.end),im=hold&&images.get(hold.start);
   if(hold&&!im?.naturalWidth){if(previous)ctx.drawImage(previous,0,0);else{ctx.fillStyle='#111';ctx.fillRect(0,0,W,H);}return;}
   if(im?.complete&&im.naturalWidth)c.drawImage(im,0,0,W,H);
   else{
    let p=s.crop_mode==='auto'?focusAt(points,t,director):{mode:s.crop_mode==='fit'?'fit':'crop',...(s.crop_mode==='manual'?staticCenter(s,clip.start+t):{x:.5,y:.5})};
    if(!p.cw||s.crop_mode!=='auto')p=focusGeometry(info,s,p);
    if(p.mode==='fit'){if(director)fill(c);else{const scale=Math.min(W/v.videoWidth,H/v.videoHeight),w=v.videoWidth*scale,h=v.videoHeight*scale;c.drawImage(v,(W-w)/2,(H-h)/2,w,h);}}
    else{size.width=v.videoWidth;size.height=v.videoHeight;const r=sourceRect(info,size,p);c.drawImage(v,r.x,r.y,r.w,r.h,0,0,W,H);}
   }
   const cutIndex=cuts.findIndex((cut,i)=>t>=cut&&t<cut+Math.min(s.mix_seconds||0,(cuts[i+1]-cut)*.8||s.mix_seconds||0));
   const cut=cutIndex>=0?cuts[cutIndex]:null;
   if(cut!==activeCut){outgoing=cut!==null?previous:null;activeCut=cut;}
   ctx.globalAlpha=1;ctx.drawImage(frame,0,0);
   if(outgoing&&cut!==null){const duration=Math.min(s.mix_seconds,(cuts[cutIndex+1]-cut)*.8||s.mix_seconds);ctx.globalAlpha=Math.max(0,1-(t-cut)/duration);ctx.drawImage(outgoing,0,0);ctx.globalAlpha=1;}
   previous=frame;
   // Drawn last, like the export overlay: replaces the single crop in two-person shots.
   const window=s.crop_mode==='auto'&&director?stackedWindowAt(stacked,t):null;
   if(window)drawStacked(window);
  }
  const refresh=()=>{last=-1;draw();};const tick=()=>{draw();frameId=v.requestVideoFrameCallback(tick);};
  v.addEventListener('seeked',refresh);v.addEventListener('loadeddata',refresh);v.addEventListener('timeupdate',draw);
  draw();if(v.requestVideoFrameCallback)frameId=v.requestVideoFrameCallback(tick);
  return()=>{disposed=true;if(frameId)v.cancelVideoFrameCallback(frameId);v.removeEventListener('seeked',refresh);v.removeEventListener('loadeddata',refresh);v.removeEventListener('timeupdate',draw);};
 },[clip.id,clip.start,clip.end,plan,points,s.crop_mode,s.crop_x,s.crop_y,JSON.stringify(s.crop_locks),s.crop_zoom,s.calm_short_shots,s.mix_seconds,JSON.stringify(stacked),JSON.stringify(removed),info.width,info.height]);
 return <canvas ref={canvas} className="motion-preview" aria-label="Xem trước khung hình AI đạo diễn, giống bản xuất"/>;
}
