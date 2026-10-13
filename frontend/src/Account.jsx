import React, {useEffect, useState} from 'react';
import './account.css';

const roleNames = {admin: 'Quản trị viên', editor: 'Biên tập viên'};

async function request(path, options = {}) {
 const r = await fetch('/api' + path, {...options, headers: {'Content-Type': 'application/json'}});
 const data = await r.json().catch(() => ({}));
 if (!r.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Không thực hiện được thao tác.');
 return data;
}
const send = (path, body, method = 'POST') => request(path, {method, body: JSON.stringify(body)});

// First and last word: "Nguyễn Thị Lan" -> "NL".
export const initials = name => { const words = (name || '?').trim().split(/\s+/); return (words[0][0] + (words.length > 1 ? words[words.length - 1][0] : '')).toUpperCase(); };

function Brand({theme}) {
 return <img className="auth-logo" src={'/brand/misa-' + theme + '.png'} alt="MISA – Tin cậy – Tiện ích – Tận tình"/>;
}

export function LoginScreen({onLogin, theme}) {
 const [username, setUsername] = useState(''), [password, setPassword] = useState(''), [error, setError] = useState(''), [busy, setBusy] = useState(false);
 async function submit(e) {
  e.preventDefault(); setBusy(true); setError('');
  try { onLogin((await send('/auth/login', {username, password})).user); }
  catch (err) { setError(err.message); setPassword(''); }
  finally { setBusy(false); }
 }
 return <main className="auth-screen"><form className="auth-card" onSubmit={submit}>
  <Brand theme={theme}/>
  <h1>TalkCut Studio</h1><p>Đăng nhập bằng tài khoản quản trị viên đã cấp cho bạn.</p>
  <label className="field"><span>Tên đăng nhập</span><input autoFocus autoComplete="username" value={username} onChange={e => setUsername(e.target.value)} required/></label>
  <label className="field"><span>Mật khẩu</span><input type="password" autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} required/></label>
  {error && <p className="auth-error" role="alert">{error}</p>}
  <button className="primary full" disabled={busy}>{busy ? 'Đang đăng nhập…' : 'Đăng nhập'}</button>
  <small>Quên mật khẩu? Hãy nhờ quản trị viên đặt lại.</small>
 </form></main>;
}

export function PasswordForm({forced, onDone, onLogout}) {
 const [current, setCurrent] = useState(''), [next, setNext] = useState(''), [again, setAgain] = useState(''), [error, setError] = useState(''), [busy, setBusy] = useState(false);
 async function submit(e) {
  e.preventDefault(); setError('');
  if (next !== again) { setError('Hai lần nhập mật khẩu mới chưa khớp.'); return; }
  setBusy(true);
  try { onDone((await send('/auth/password', {current_password: current, new_password: next})).user); }
  catch (err) { setError(err.message); }
  finally { setBusy(false); }
 }
 return <form className="auth-form" onSubmit={submit}>
  {forced && <p className="auth-note">Mật khẩu hiện tại do quản trị viên cấp. Hãy đặt mật khẩu riêng để tiếp tục.</p>}
  <label className="field"><span>Mật khẩu hiện tại</span><input type="password" autoComplete="current-password" value={current} onChange={e => setCurrent(e.target.value)} required/></label>
  <label className="field"><span>Mật khẩu mới</span><input type="password" autoComplete="new-password" minLength={8} value={next} onChange={e => setNext(e.target.value)} required/><small>Ít nhất 8 ký tự.</small></label>
  <label className="field"><span>Nhập lại mật khẩu mới</span><input type="password" autoComplete="new-password" minLength={8} value={again} onChange={e => setAgain(e.target.value)} required/></label>
  {error && <p className="auth-error" role="alert">{error}</p>}
  <button className="primary full" disabled={busy}>{busy ? 'Đang lưu…' : 'Đổi mật khẩu'}</button>
  {onLogout && <button type="button" className="secondary full" onClick={onLogout}>Đăng xuất</button>}
 </form>;
}

export function ForcedPasswordScreen({user, onDone, onLogout, theme}) {
 return <main className="auth-screen"><div className="auth-card"><Brand theme={theme}/><h1>Chào {user.display_name}</h1><PasswordForm forced onDone={onDone} onLogout={onLogout}/></div></main>;
}

export async function logout() {
 await request('/auth/logout', {method: 'POST'}).catch(() => null);
}

function temporaryPassword() {
 const chars = 'abcdefghjkmnpqrstuvwxyz23456789';
 const values = crypto.getRandomValues(new Uint32Array(10));
 return Array.from(values, v => chars[v % chars.length]).join('');
}

// Administrators issue accounts; a new or reset password must be replaced at first login.
export function UsersPanel({me, notify}) {
 const [users, setUsers] = useState(null), [form, setForm] = useState({username: '', display_name: '', role: 'editor', password: temporaryPassword()}), [issued, setIssued] = useState(null), [busy, setBusy] = useState('');
 const load = () => request('/users').then(setUsers).catch(e => notify(e.message, true));
 useEffect(() => { load(); }, []);
 async function run(key, fn) { setBusy(key); try { await fn(); await load(); } catch (e) { notify(e.message, true); } finally { setBusy(''); } }
 const create = e => { e.preventDefault(); run('create', async () => { const user = await send('/users', form); setIssued({username: user.username, password: form.password}); setForm({username: '', display_name: '', role: 'editor', password: temporaryPassword()}); }); };
 const reset = user => run(user.id, async () => { const password = temporaryPassword(); await send('/users/' + user.id, {password}, 'PUT'); setIssued({username: user.username, password}); });
 const change = (user, body) => run(user.id, () => send('/users/' + user.id, body, 'PUT'));
 return <div className="users-panel">
  {issued && <div className="issued-password" role="status"><strong>Mật khẩu tạm cho {issued.username}</strong><code>{issued.password}</code><small>Gửi riêng cho người dùng. Họ phải đổi mật khẩu ở lần đăng nhập đầu tiên; mật khẩu này không hiển thị lại.</small><button className="secondary small" onClick={() => setIssued(null)}>Đã ghi lại</button></div>}
  <form className="user-create" onSubmit={create}>
   <h3>Cấp tài khoản mới</h3>
   <label className="field"><span>Tên đăng nhập</span><input value={form.username} onChange={e => setForm({...form, username: e.target.value.toLowerCase()})} placeholder="vd: lan.nt" pattern="[a-z0-9._\-]{3,40}" required/></label>
   <label className="field"><span>Họ và tên</span><input value={form.display_name} maxLength={80} onChange={e => setForm({...form, display_name: e.target.value})} placeholder="Nguyễn Thị Lan"/></label>
   <label className="field"><span>Vai trò</span><select value={form.role} onChange={e => setForm({...form, role: e.target.value})}><option value="editor">Biên tập viên</option><option value="admin">Quản trị viên</option></select></label>
   <button className="primary" disabled={busy === 'create'}>Tạo tài khoản</button>
  </form>
  <table className="users-table"><thead><tr><th>Người dùng</th><th>Vai trò</th><th>Trạng thái</th><th/></tr></thead><tbody>
   {(users || []).map(u => <tr key={u.id} className={u.active ? '' : 'locked'}>
    <td><strong>{u.display_name}</strong><small>{u.username}</small></td>
    <td><select aria-label={'Vai trò của ' + u.username} value={u.role} disabled={!!busy || u.id === me.id} onChange={e => change(u, {role: e.target.value})}><option value="editor">{roleNames.editor}</option><option value="admin">{roleNames.admin}</option></select></td>
    <td>{u.active ? (u.must_change_password ? 'Chờ đổi mật khẩu' : 'Đang hoạt động') : 'Đã khóa'}</td>
    <td><div className="user-actions"><button className="secondary small" disabled={!!busy} onClick={() => reset(u)}>Đặt lại mật khẩu</button>
     {u.id !== me.id && <button className="secondary small" disabled={!!busy} onClick={() => change(u, {active: !u.active})}>{u.active ? 'Khóa' : 'Mở khóa'}</button>}</div></td>
   </tr>)}
  </tbody></table>
  {!users && <p className="helper">Đang tải danh sách tài khoản…</p>}
 </div>;
}

export {roleNames};
