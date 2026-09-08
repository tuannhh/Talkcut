import React,{useRef,useEffect} from 'react';
import {focusAt,focusGeometry} from './studio-helpers.mjs';

export function MotionPreview({video,clip,plan,points,info,media}){
 const canvas=useRef();const s=clip.settings;
 useEffect(()=>{
  const v=video.current,out=canvas.current;if(!v||!out)return;
  const ctx=out.getContext('2d'),W=360,H=640;out.width=W;out.height=H;
  const count=Math.max(2,Math.round((s.transition_seconds||0)*30)),history=[];
  const holds=s.calm_short_shots?plan?.holds||[]:[],images=new Map();
  for(const h of holds){const im=new Image();im.onload=()=>{last=-1;draw();};im.src=media(h.path);images.set(h.start,im);}
  let last=-1,frameId,disposed=false;
  const cuts=(plan?.visual_cuts||points.filter((p,i)=>i&&(p.cut||p.scene!==points[i-1].scene)).map(p=>p.time)).filter(t=>!holds.some(h=>t>=h.start&&t<h.end-.01));
  function draw(){
   if(disposed||v.readyState<2)return;
   const t=v.currentTime-clip.start,index=Math.round(t*30);
   if(index===last)return;
   if(last<0||index<last||index-last>10)history.length=0;
   last=index;
   const frame=document.createElement('canvas');frame.width=W;frame.height=H;const c=frame.getContext('2d');c.fillStyle='#000';c.fillRect(0,0,W,H);
   const hold=holds.find(h=>t>=h.start&&t<h.end),im=hold&&images.get(hold.start);
   if(im?.complete&&im.naturalWidth)c.drawImage(im,0,0,W,H);
   else{
    let p=s.crop_mode==='auto'?focusAt(points,t):{mode:s.crop_mode==='fit'?'fit':'crop',x:s.crop_mode==='manual'?s.crop_x:.5,y:.5};
    if(!p.cw||s.crop_mode!=='auto')p=focusGeometry(info,s,p);
    if(p.mode==='fit'){const scale=Math.min(W/v.videoWidth,H/v.videoHeight),w=v.videoWidth*scale,h=v.videoHeight*scale;c.drawImage(v,(W-w)/2,(H-h)/2,w,h);}
    else{const cw=p.cw/info.width*v.videoWidth,ch=p.ch/info.height*v.videoHeight,x=Math.max(0,Math.min(v.videoWidth-cw,p.x*v.videoWidth-cw/2)),y=Math.max(0,Math.min(v.videoHeight-ch,p.y*v.videoHeight-ch/2));c.drawImage(v,x,y,cw,ch,0,0,W,H);}
   }
   history.push(frame);while(history.length>count)history.shift();
   const mixing=s.transition_seconds>0&&cuts.some(cut=>t>=cut&&t<cut+count/30);
   ctx.clearRect(0,0,W,H);
   if(mixing&&history.length>1){ctx.globalCompositeOperation='lighter';ctx.globalAlpha=1/history.length;for(const f of history)ctx.drawImage(f,0,0);ctx.globalCompositeOperation='source-over';ctx.globalAlpha=1;}
   else ctx.drawImage(frame,0,0);
  }
  const refresh=()=>{last=-1;draw();};const tick=()=>{draw();frameId=v.requestVideoFrameCallback(tick);};
  v.addEventListener('seeked',refresh);v.addEventListener('loadeddata',refresh);v.addEventListener('timeupdate',draw);
  draw();if(v.requestVideoFrameCallback)frameId=v.requestVideoFrameCallback(tick);
  return()=>{disposed=true;if(frameId)v.cancelVideoFrameCallback(frameId);v.removeEventListener('seeked',refresh);v.removeEventListener('loadeddata',refresh);v.removeEventListener('timeupdate',draw);};
 },[clip.id,clip.start,clip.end,plan,points,s.crop_mode,s.crop_x,s.crop_zoom,s.calm_short_shots,s.transition_seconds,info.width,info.height]);
 return <canvas ref={canvas} className="motion-preview" aria-label="Xem trước crop ổn định và chuyển cảnh hòa trộn"/>;
}
