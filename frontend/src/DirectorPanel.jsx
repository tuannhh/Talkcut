import React from 'react';
import {roleLabels} from './studio-helpers.mjs';

// Fully automatic framing: the AI finds every person, who speaks, and who hosts.
// The only choices left to the editor are style switches and a role override.
export function DirectorPanel({clip,plan,job,media,setting,onPrepare,busy}){
 const s=clip.settings,pending=['queued','running'].includes(job?.status),ready=!!plan?.director;
 return <div className="director-panel">
  {!ready&&<p className="helper">AI tự nhận ra từng người, ai đang nói, ai là MC hay khách mời, rồi dựng khung dọc 9:16 như một biên tập viên: luôn giữ trọn người nói trong khung, ghép hai người khi máy quay cảnh toàn và cắt khoảng lặng.</p>}
  {pending&&<div className="quick-progress" role="status"><p>{job.message}</p><progress max="100" value={job.progress}/></div>}
  {!pending&&job?.status==='failed'&&!ready&&<p role="alert">{job.error}</p>}
  {!ready&&!pending&&<button className="primary full" disabled={busy} onClick={onPrepare}>Để AI dựng khung hình</button>}
  {ready&&<>
   <p className="director-note">✓ {plan.note}</p>
   {plan.cast?.length>0&&<div className="cast-list">{plan.cast.slice(0,4).map(c=><figure key={c.id} className={'cast-card '+c.role}>
    {c.thumbnail?<img src={media(c.thumbnail)} alt={roleLabels[c.role]}/>:<span className="cast-empty"/>}
    <figcaption><strong>{roleLabels[c.role]}</strong><small>{c.speech>=1?`Nói ${Math.round(c.speech)} giây`:'Chủ yếu lắng nghe'}</small></figcaption>
   </figure>)}</div>}
   {plan.cast?.length>=2&&<button className="secondary small" onClick={()=>setting('swap_roles',!s.swap_roles)}>Đổi vai MC ↔ khách mời</button>}
  </>}
  <label className="quick-checkbox"><input type="checkbox" checked={s.stacked_enabled!==false} onChange={e=>setting('stacked_enabled',e.target.checked)}/>Ghép khung khi quay cảnh toàn: khách mời ở trên, MC ở dưới</label>
  <label className="quick-checkbox"><input type="checkbox" checked={s.silence_trim!==false} onChange={e=>setting('silence_trim',e.target.checked)}/>Cắt khoảng lặng và tiếng ậm ừ{ready&&s.silence_trim!==false&&plan.removed_seconds?` · rút ${plan.removed_seconds.toFixed(1)} giây`:''}</label>
  <label className="quick-checkbox"><input type="checkbox" checked={s.punch_in!==false} onChange={e=>setting('punch_in',e.target.checked)}/>Đổi cỡ khung xen kẽ ở chỗ cắt khoảng lặng để nhát cắt không bị giật hình</label>
 </div>;
}
