import React,{useEffect,useState} from 'react';

export function TrackingSubjects({clip,api,media,onSelect,jobs}){
 const [items,setItems]=useState([]),[loading,setLoading]=useState(false),[error,setError]=useState('');
 const scanJob=(jobs||[]).find(job=>job.kind==='subject-gallery'&&job.target===clip.id);
 async function load(){const result=await api(`/clips/${clip.id}/subjects`);setItems(result.items||[]);return result.items||[];}
 async function scan(refresh=false){setLoading(true);setError('');try{await api(`/clips/${clip.id}/subjects/scan${refresh?'?refresh=true':''}`,{method:'POST'});}catch(e){setError(e.message);}finally{setLoading(false);}}
 useEffect(()=>{let active=true;setItems([]);setError('');(async()=>{try{const cached=await load();if(active&&!cached.length)await scan();}catch(e){active&&setError(e.message);}})();return()=>{active=false;};},[clip.id]);
 useEffect(()=>{if(scanJob?.status!=='completed')return;load().catch(e=>setError(e.message));},[clip.id,scanJob?.id,scanJob?.status]);
 const working=loading||['queued','running'].includes(scanJob?.status);
 return <div className="tracking-subjects"><h3>Chọn chủ thể để AI theo dõi</h3><p className="helper">AI tự tìm các khuôn mặt rõ trong chính đoạn clip này. Chọn một khuôn mặt, AI sẽ tự bắt đầu theo dõi qua các góc máy.</p>
  {working&&<div className="subject-scan-status"><span>{scanJob?.message||'Đang tìm khuôn mặt rõ trong đoạn…'}</span><progress max="100" value={scanJob?.progress||8}/></div>}
  {error&&<p role="status">{error}</p>}
  {!working&&!items.length&&<div className="subject-empty"><p>Chưa tìm thấy khuôn mặt đủ rõ trong đoạn này.</p><button className="secondary small" onClick={scan}>Quét lại khuôn mặt</button></div>}
  <div className="subject-gallery">{items.map((s,i)=><button key={s.id} disabled={working} className={clip.settings.tracking_subject===s.id?'selected':''} aria-label={'Chọn khuôn mặt '+(i+1)} onClick={()=>onSelect(s.id)}><img src={media(s.path)} alt={'Khuôn mặt gợi ý '+(i+1)}/><span>{(s.time-clip.start).toFixed(0)}s</span></button>)}</div>
  {items.length>0&&!working&&<button className="text-action" onClick={()=>scan(true)}>Gợi ý lại khuôn mặt</button>}
  {clip.settings.tracking_subject&&<><p className="helper">Đã chọn chủ thể. AI sẽ giữ đúng người này khi chuyển góc máy; cảnh chưa đủ chắc chắn vẫn dùng video đang chuyển động và được đánh dấu cần duyệt.</p><button className="secondary small" onClick={()=>onSelect(null)}>Bỏ chọn chủ thể</button></>}
 </div>;
}
