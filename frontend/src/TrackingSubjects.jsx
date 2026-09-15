import React,{useEffect,useState} from 'react';

export function TrackingSubjects({clip,api,media,onSelect,jobs,disabled=false,field='tracking_subject',title='Chọn chủ thể để AI theo dõi',helper='AI tự tìm các khuôn mặt rõ trong chính đoạn clip này. Chọn một khuôn mặt, AI sẽ tự bắt đầu theo dõi qua các góc máy.',selectedHelper='Đã chọn chủ thể. AI sẽ giữ đúng người này khi chuyển góc máy; cảnh chưa đủ chắc chắn vẫn dùng video đang chuyển động và được đánh dấu cần duyệt.'}){
 const [items,setItems]=useState([]),[loading,setLoading]=useState(false),[error,setError]=useState('');
 const scanJob=(jobs||[]).find(job=>job.kind==='subject-gallery'&&job.target===clip.id);
 const selectedId=clip.settings[field];
 async function load(){const result=await api(`/clips/${clip.id}/subjects`);setItems(result.items||[]);return result.items||[];}
 async function scan(refresh=false){setLoading(true);setError('');try{await api(`/clips/${clip.id}/subjects/scan${refresh?'?refresh=true':''}`,{method:'POST'});}catch(e){setError(e.message);}finally{setLoading(false);}}
 useEffect(()=>{let active=true;setItems([]);setError('');setLoading(true);(async()=>{try{const result=await api(`/clips/${clip.id}/subjects`);if(!active)return;setItems(result.items||[]);if(!result.scanned&&!['queued','running','failed'].includes(scanJob?.status))await scan();}catch(e){active&&setError(e.message);}finally{active&&setLoading(false);}})();return()=>{active=false;};},[clip.id]);
 useEffect(()=>{if(scanJob?.status!=='completed')return;load().catch(e=>setError(e.message));},[clip.id,scanJob?.id,scanJob?.status]);
 const working=loading||['queued','running'].includes(scanJob?.status);
 return <div className="tracking-subjects"><h3>{title}</h3><p className="helper">{helper}</p>
  {working&&<div className="subject-scan-status"><span>{scanJob?.message||'Đang tìm khuôn mặt rõ trong đoạn…'}</span><progress max="100" value={scanJob?.progress||8}/></div>}
  {(error||scanJob?.status==='failed')&&<p role="status">{error||scanJob.error}</p>}
  {!working&&!items.length&&<div className="subject-empty"><p>Chưa có khuôn mặt gợi ý cho đoạn này.</p><button className="secondary small" onClick={()=>scan(true)}>Quét lại khuôn mặt</button></div>}
  <div className="subject-gallery">{items.map((s,i)=><button key={s.id} disabled={working||disabled} className={selectedId===s.id?'selected':''} aria-label={'Chọn khuôn mặt '+(i+1)} onClick={()=>onSelect(s.id)}><img src={media(s.path)} alt={'Khuôn mặt gợi ý '+(i+1)}/><span>{(s.time-clip.start).toFixed(0)}s</span></button>)}</div>
  {items.length>0&&!working&&<button className="text-action" onClick={()=>scan(true)}>Gợi ý lại khuôn mặt</button>}
  {selectedId&&<><p className="helper">{selectedHelper}</p><button disabled={disabled} className="secondary small" onClick={()=>onSelect(null)}>Bỏ chọn chủ thể</button></>}
 </div>;
}
