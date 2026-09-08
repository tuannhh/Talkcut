export const sceneLabels={speaker:'Người đang nói',reaction:'Cảnh người nghe',broll:'Cảnh trám',wrong_shot:'Có thể quay nhầm',broken:'Hình lỗi / mất nét',transition:'Chuyển cảnh / lia máy',end:'Kết cảnh',uncertain:'Chưa đủ bằng chứng'};
export function wordGroups(words,maxWords=28,maxSeconds=10){
 const groups=[];let group=[];
 for(const w of words){const last=group.at(-1);if(last&&(group.length>=maxWords||w.start-last.end>.7||last.speaker!==w.speaker||/[.!?…][”"']?$/.test(last.text)||w.end-group[0].start>maxSeconds)){groups.push(group);group=[];}group.push(w);}
 if(group.length)groups.push(group);return groups;
}
const clamp=(v,lo,hi)=>Math.max(lo,Math.min(hi,v));
export function focusGeometry(info,settings,p){
 const iw=info.width,ih=info.height,z=settings.crop_zoom||1;
 const cw=Math.max(2,Math.floor(Math.min(iw,ih*9/16)/z/2)*2),ch=Math.max(2,Math.floor(Math.min(ih,iw*16/9)/z/2)*2);
 if(settings.crop_mode==='fit')return {...p,mode:'fit',x:.5,y:.5,cw,ch};
 let cx=p.x??.5,cy=.5;
 if(p.face){const [x1,y1,x2,y2]=p.face,fw=x2-x1,fh=y2-y1;const left=Math.max(0,x1-fw*.15),right=Math.min(1,x2+fw*.15),top=Math.max(0,y1-fh*.5),bottom=Math.min(1,y2+fh*.3);
 if((right-left)*iw>cw||(bottom-top)*ih>ch)return {...p,mode:'crop',x:clamp((x1+x2)/2,cw/iw/2,1-cw/iw/2),y:clamp((y1+y2)/2,ch/ih/2,1-ch/ih/2),cw,ch};
 cx=clamp(cx,right-cw/iw/2,left+cw/iw/2);cy=clamp((y1+y2)/2+ch/ih*.17,bottom-ch/ih/2,top+ch/ih/2);}
 return {...p,mode:'crop',x:(clamp(cx*iw-cw/2,0,iw-cw)+cw/2)/iw,y:(clamp(cy*ih-ch/2,0,ih-ch)+ch/2)/ih,cw,ch};
}
export function focusAt(points,time){
 if(!points?.length)return {mode:'crop',x:.5,y:.5};
 let i=0;while(i+1<points.length&&points[i+1].time<=time)i++;
 const p=points[i],q=points[i+1];if(!q)return p;
 const f=clamp((time-p.time)/Math.max(.01,q.time-p.time),0,1);
 const jump=q.cut||p.scene!==q.scene||p.mode!==q.mode;
 return {...p,x:jump||Math.abs(q.x-p.x)>.18?p.x:p.x+(q.x-p.x)*f,y:jump||Math.abs(q.y-p.y)>.18?p.y:p.y+(q.y-p.y)*f};
}

// Preserve measured timing anchors. Added words share an existing spoken interval;
// never distribute a sentence's duration into invented word timestamps.
export function editTimedGroup(group,text){
 const next=text.trim().split(/\s+/).filter(Boolean),old=group.flatMap((w,i)=>w.text.split(/\s+/).filter(Boolean).map(t=>({text:t,owner:i})));
 if(!next.length)return [];
 if(group.length===next.length)return group.map((w,i)=>({...w,text:next[i]}));
 const dp=Array.from({length:old.length+1},()=>Array(next.length+1).fill(0));
 for(let i=old.length-1;i>=0;i--)for(let j=next.length-1;j>=0;j--)dp[i][j]=old[i].text===next[j]?dp[i+1][j+1]+1:Math.max(dp[i+1][j],dp[i][j+1]);
 const matches=[];let i=0,j=0;
 while(i<old.length&&j<next.length){if(old[i].text===next[j]){matches.push([i,j]);i++;j++;}else if(dp[i+1][j]>=dp[i][j+1])i++;else j++;}
 matches.push([old.length,next.length]);const buckets=group.map(()=>[]);let a=0,b=0;
 for(const [oi,nj] of matches){
  const owners=[...new Set(old.slice(a,oi).map(x=>x.owner))];
  for(let k=b;k<nj;k++){const owner=owners.length?owners[Math.min(owners.length-1,Math.floor((k-b)*owners.length/(nj-b)))]:old[oi]?.owner??old.at(-1)?.owner??0;buckets[owner].push(next[k]);}
  if(oi<old.length)buckets[old[oi].owner].push(next[nj]);a=oi+1;b=nj+1;
 }
 return group.flatMap((w,i)=>buckets[i].length?[{...w,text:buckets[i].join(' ')}]:[]);
}
export function replaceTimedGroup(words,group,text){
 const first=words.indexOf(group[0]);if(first<0)return words;
 return [...words.slice(0,first),...editTimedGroup(group,text),...words.slice(first+group.length)];
}
