import React,{useRef,useEffect} from 'react';
import {focusAt,focusGeometry,staticCenter} from './studio-helpers.mjs';

export function MotionPreview({video,clip,plan,points,info,media}){
 const canvas=useRef();const s=clip.settings;
 useEffect(()=>{
  const v=video.current,out=canvas.current;if(!v||!out)return;
  const ctx=out.getContext('2d'),W=360,H=640;out.width=W;out.height=H;
  const buffers=Array.from({length:3},()=>{const c=document.createElement('canvas');c.width=W;c.height=H;return c;});
  let previous=null,outgoing=null,activeCut=null;
  const holds=(s.calm_short_shots||plan?.reference_tracking)&&plan?.framing_mode===s.crop_mode?plan?.holds||[]:[],images=new Map();
  for(const h of holds){const im=new Image();im.onload=()=>{last=-1;draw();};im.src=media(h.path);images.set(h.start,im);}
  let last=-1,frameId,disposed=false;
  const cuts=(plan?.visual_cuts||points.filter((p,i)=>i&&(p.cut||p.scene!==points[i-1].scene)).map(p=>p.time)).filter(t=>!holds.some(h=>t>=h.start&&t<h.end-.01));
  function draw(){
   if(disposed||v.readyState<2)return;
   const t=v.currentTime-clip.start,index=Math.round(t*30);
   if(index===last)return;
   if(last<0||index<last||index-last>10){previous=null;outgoing=null;activeCut=null;}
   last=index;
   const frame=buffers.find(b=>b!==previous&&b!==outgoing);const c=frame.getContext('2d');c.fillStyle='#000';c.fillRect(0,0,W,H);
   const hold=holds.find(h=>t>=h.start&&t<h.end),im=hold&&images.get(hold.start);
   if(hold&&!im?.naturalWidth){if(previous)ctx.drawImage(previous,0,0);else{ctx.fillStyle='#111';ctx.fillRect(0,0,W,H);}return;}
   if(im?.complete&&im.naturalWidth)c.drawImage(im,0,0,W,H);
   else{
    let p=s.crop_mode==='auto'?focusAt(points,t):{mode:s.crop_mode==='fit'?'fit':'crop',...(s.crop_mode==='manual'?staticCenter(s,clip.start+t):{x:.5,y:.5})};
    if(!p.cw||s.crop_mode!=='auto')p=focusGeometry(info,s,p);
    if(p.mode==='fit'){const scale=Math.min(W/v.videoWidth,H/v.videoHeight),w=v.videoWidth*scale,h=v.videoHeight*scale;c.drawImage(v,(W-w)/2,(H-h)/2,w,h);}
    else{const cw=p.cw/info.width*v.videoWidth,ch=p.ch/info.height*v.videoHeight,x=Math.max(0,Math.min(v.videoWidth-cw,p.x*v.videoWidth-cw/2)),y=Math.max(0,Math.min(v.videoHeight-ch,p.y*v.videoHeight-ch/2));c.drawImage(v,x,y,cw,ch,0,0,W,H);}
   }
   const cutIndex=cuts.findIndex((cut,i)=>t>=cut&&t<cut+Math.min(s.mix_seconds||0,(cuts[i+1]-cut)*.8||s.mix_seconds||0));
   const cut=cutIndex>=0?cuts[cutIndex]:null;
   if(cut!==activeCut){outgoing=cut!==null?previous:null;activeCut=cut;}
   ctx.globalAlpha=1;ctx.drawImage(frame,0,0);
   if(outgoing&&cut!==null){const duration=Math.min(s.mix_seconds,(cuts[cutIndex+1]-cut)*.8||s.mix_seconds);ctx.globalAlpha=Math.max(0,1-(t-cut)/duration);ctx.drawImage(outgoing,0,0);ctx.globalAlpha=1;}
   previous=frame;
  }
  const refresh=()=>{last=-1;draw();};const tick=()=>{draw();frameId=v.requestVideoFrameCallback(tick);};
  v.addEventListener('seeked',refresh);v.addEventListener('loadeddata',refresh);v.addEventListener('timeupdate',draw);
  draw();if(v.requestVideoFrameCallback)frameId=v.requestVideoFrameCallback(tick);
  return()=>{disposed=true;if(frameId)v.cancelVideoFrameCallback(frameId);v.removeEventListener('seeked',refresh);v.removeEventListener('loadeddata',refresh);v.removeEventListener('timeupdate',draw);};
 },[clip.id,clip.start,clip.end,plan,points,s.crop_mode,s.crop_x,s.crop_y,JSON.stringify(s.crop_locks),s.crop_zoom,s.calm_short_shots,s.mix_seconds,info.width,info.height]);
 return <canvas ref={canvas} className="motion-preview" aria-label="Xem trước crop ổn định và chuyển cảnh hòa trộn"/>;
}
