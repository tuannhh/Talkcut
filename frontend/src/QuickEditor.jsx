import React,{useState,useEffect,useRef} from 'react';
import {TrackingSubjects} from './TrackingSubjects.jsx';
import {PresetBar} from './PresetBar.jsx';

export function QuickEditor({clip,api,post,media,jobs,notify,onApply,onSubject,onSecondSubject,onPanel,setting,plan,stacked,onPrepare,onPrepareStacked,busy}){
 const [templates,setTemplates]=useState([]),[uploading,setUploading]=useState(false),[selected,setSelected]=useState(''),[applying,setApplying]=useState(false);
 const input=useRef(),currentClip=useRef(clip.id);currentClip.current=clip.id;
 useEffect(()=>{setSelected('');},[clip.id]);
 const templateJobs=jobs.filter(j=>j.kind==='style-template');
 const statusKey=templateJobs.map(j=>j.id+j.status).join('|');
 useEffect(()=>{let alive=true;api('/style-templates').then(r=>alive&&setTemplates(r)).catch(e=>notify(e.message,true));return()=>{alive=false;};},[statusKey]);
 async function upload(file){
  if(!file)return;setUploading(true);
  try{const form=new FormData();form.append('file',file);await api('/style-templates',{method:'POST',body:form});setTemplates(await api('/style-templates'));notify('AI đang học video mẫu. Bạn có thể tiếp tục chỉnh clip.');}
  catch(e){notify(e.message,true);}finally{setUploading(false);if(input.current)input.current.value='';}
 }
 async function apply(item){if(applying)return;const id=clip.id;setApplying(true);try{const r=await post('/style-templates/'+item.id+'/apply',clip.settings);if(currentClip.current!==id)return;await onApply(r.settings);if(currentClip.current!==id)return;setSelected(item.id);notify('Đã áp dụng phong cách dựng cho clip này.');}catch(e){notify(e.message,true);}finally{setApplying(false);}}
 const focusJob=jobs.find(j=>j.kind==='focus'&&j.target===clip.id);
 const pending=['queued','running'].includes(focusJob?.status);
 const stackedJob=jobs.find(j=>j.kind==='stacked-view'&&j.target===clip.id);
 const stackedPending=['queued','running'].includes(stackedJob?.status);
 return <div className="quick-editor">
  <div className="quick-intro"><h3>Dựng clip trong vài bước</h3><p>Chọn người, chọn phong cách. Xem bên trái rồi xuất video.</p></div>
  <section className="quick-step"><div className="quick-step-title"><span>1</span><h3>Giữ ai trong khung hình?</h3></div>
   <TrackingSubjects clip={clip} api={api} media={media} jobs={jobs} onSelect={onSubject} disabled={busy||pending}/>
   {pending&&<div className="quick-progress" role="status"><p>{focusJob.message}</p><progress max="100" value={focusJob.progress}/></div>}
   {focusJob?.status==='failed'&&<p role="alert">{focusJob.error}</p>}
   {!pending&&clip.settings.tracking_subject&&<div className="quick-tracking-state"><p>{plan?'✓ Đã có khung hình theo chủ thể':'Chủ thể đã chọn — chuẩn bị khung hình để xem.'}</p><button disabled={busy} onClick={onPrepare}>{plan?'Cập nhật tracking':'Chuẩn bị khung hình'}</button></div>}
   <button className="text-action" onClick={()=>onPanel('framing')}>Chỉnh crop hoặc kiểm tra từng cảnh</button>
   <label className="quick-checkbox"><input type="checkbox" checked={!!clip.settings.stacked_enabled} disabled={busy} onChange={e=>setting('stacked_enabled',e.target.checked)}/>Ghép khung chồng khi quay cảnh toàn hai người</label>
   {clip.settings.stacked_enabled&&<>
    <p className="helper">Người ở bước 1 giữ vị trí trên. Chọn thêm người sẽ đứng dưới; AI sẽ tự tìm các đoạn cảnh toàn thấy rõ cả hai để ghép khung, cảnh khác giữ khung đơn như bình thường.</p>
    {!clip.settings.tracking_subject&&<p role="alert" className="quick-warn">Chưa chọn người đứng trên (ở bước 1) nên chưa thể ghép khung — video sẽ giữ khung đơn cho tới khi bạn chọn đủ cả hai người.</p>}
    <TrackingSubjects clip={clip} api={api} media={media} jobs={jobs} onSelect={onSecondSubject} disabled={busy||stackedPending} field="tracking_subject_2" title="Chọn người đứng dưới" helper="Chọn một khuôn mặt khác với người ở trên." selectedHelper="Đã chọn người đứng dưới cho khung ghép."/>
    {stackedPending&&<div className="quick-progress" role="status"><p>{stackedJob.message}</p><progress max="100" value={stackedJob.progress}/></div>}
    {stackedJob?.status==='failed'&&<p role="alert">{stackedJob.error}</p>}
    {!stackedPending&&clip.settings.tracking_subject&&!clip.settings.tracking_subject_2&&<p role="alert" className="quick-warn">Chưa chọn người đứng dưới nên chưa thể ghép khung — video sẽ giữ khung đơn cho tới khi bạn chọn đủ hai người.</p>}
    {!stackedPending&&clip.settings.tracking_subject&&clip.settings.tracking_subject_2&&<div className="quick-tracking-state"><p>{!stacked?'Đã chọn cả hai người — chuẩn bị để AI tìm đoạn ghép khung.':stacked.length?`✓ Đã tìm thấy ${stacked.length} đoạn để ghép khung`:'Chưa tìm thấy cảnh toàn nào đủ rõ cả hai người trong clip này — video sẽ giữ khung đơn. Bạn có thể bấm tìm lại.'}</p><button disabled={busy} onClick={onPrepareStacked}>{stacked?'Tìm lại đoạn ghép khung':'Chuẩn bị ghép khung'}</button></div>}
   </>}
  </section>
  <section className="quick-step"><div className="quick-step-title"><span>2</span><h3>Chọn phong cách dựng</h3></div>
   <p className="helper">Học từ clip bạn thích, dùng lại cho các video sau.</p>
   <input ref={input} hidden type="file" accept="video/mp4,video/quicktime,video/webm,.m4v" onChange={e=>upload(e.target.files?.[0])}/>
   <button className="primary full" disabled={uploading} onClick={()=>input.current.click()}>{uploading?'Đang tải video mẫu…':'+ Học phong cách từ video mẫu'}</button>
   <small>MP4 / MOV / WEBM · 2 giây–3 phút · tối đa 512 MB</small>
   <div className="template-cards">{templates.map(item=>{const job=templateJobs.find(j=>j.target===item.id),failed=item.status==='failed'||job?.status==='failed';return <article key={item.id} className={'template-card '+(selected===item.id?'selected':'')}>
    <div className="template-card-head">{item.thumbnail&&<img src={media(item.thumbnail)} alt="Khung hình video mẫu"/>}<div><strong>{item.profile?.name||item.name}</strong><p>{item.profile?.summary||job?.message||'Đang xếp hàng phân tích'}</p></div></div>
    {item.status==='ready'?<><button className="secondary full" disabled={busy||applying} onClick={()=>apply(item)}>{selected===item.id?'Áp dụng lại mẫu':'Dùng cho clip này'}</button><details><summary>Phong cách đã học & phạm vi áp dụng</summary><dl>{[['composition','Bố cục'],['mood','Không khí'],['highlights','Chữ nhấn'],['sound','Âm thanh'],['transitions','Chuyển cảnh']].map(([key,label])=><React.Fragment key={key}><dt>{label}</dt><dd>{item.profile[key]}</dd></React.Fragment>)}</dl><p><b>Tự áp dụng:</b> kiểu, font, màu, cỡ, vị trí và số từ phụ đề; thời gian Mix, chữ nhấn mở đầu và cue âm thanh nếu mẫu có. Crop tiếp tục theo chủ thể bạn chọn.</p>{item.limits?.map((note,i)=><p key={i}>{note}</p>)}<ul>{item.profile.evidence?.map((e,i)=><li key={i}>{e}</li>)}</ul></details></>:failed?<><p role="alert">{item.error||job?.error}</p><button onClick={async()=>{try{await post('/style-templates/'+item.id+'/retry');setTemplates(await api('/style-templates'));}catch(e){notify(e.message,true);}}}>Thử học lại</button></>:<progress max="100" value={job?.progress||3}/>}
   </article>;})}</div>
   <details className="saved-presets"><summary>Mẫu thiết lập đã lưu của kênh</summary><PresetBar clip={clip} api={api} post={post} notify={notify} onApply={onApply}/></details>
  </section>
  <section className="quick-step"><div className="quick-step-title"><span>3</span><h3>Hoàn thiện</h3></div>
   <label className="quick-checkbox"><input type="checkbox" checked={clip.settings.caption_enabled} onChange={e=>setting('caption_enabled',e.target.checked)}/>Hiển thị phụ đề</label>
   <label className="quick-checkbox"><input type="checkbox" checked={!!clip.settings.main_title_enabled} onChange={e=>setting('main_title_enabled',e.target.checked)}/>Tiêu đề nổi bật ở đầu nội dung</label>
   <label>Âm thanh mở đầu<select aria-label="Âm thanh mở đầu" value={clip.settings.sound_effect||'none'} onChange={e=>setting('sound_effect',e.target.value)}>{[['none','Không dùng'],['pop','Pop nhẹ'],['ding','Ding nhẹ'],['whoosh','Whoosh nhẹ']].map(([id,label])=><option key={id} value={id}>{label}</option>)}</select></label>
   <div className="quick-links">{[['intro','Mở đầu & giọng đọc'],['captions','Sửa lời thoại & phụ đề'],['brand','Logo & nhạc nền'],['outro','Video kết thúc'],['story','Tiêu đề & đoạn cắt']].map(([id,label])=><button key={id} onClick={()=>onPanel(id)}>{label}<span>→</span></button>)}</div>
   <p className="helper">Chỉnh sửa là tùy chọn. Nút xuất video luôn ở dưới.</p>
  </section>
 </div>;
}
