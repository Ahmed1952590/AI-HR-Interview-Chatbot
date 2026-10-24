import { FormEvent, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, fmtDate, fmtDuration } from '../api'
import { useAuth } from '../auth'

export function Dashboard() {
  const { user } = useAuth()
  const [stats, setStats] = useState<any>(null)
  const [recent, setRecent] = useState<any[]>([])
  useEffect(() => {
    api('/interview/stats').then(setStats).catch(() => {})
    api('/interview/history').then((h) => setRecent(h.slice(0, 5))).catch(() => {})
  }, [])
  return (
    <>
      <div className="head">
        <div>
          <h1>Welcome back, {user?.name.split(' ')[0]}</h1>
          <p className="muted">Practice one question at a time and compare your answer with the ideal one.</p>
        </div>
        <Link className="btn" to="/interview/new">Start new interview</Link>
      </div>

      <div className="grid">
        <div className="stat"><b>{stats?.total ?? '–'}</b><span>Interviews</span></div>
        <div className="stat"><b>{stats?.answered ?? '–'}</b><span>Questions answered</span></div>
        <div className="stat"><b>{stats?.skipped ?? '–'}</b><span>Questions skipped</span></div>
        <div className="stat"><b>{stats ? fmtDuration(stats.avg_duration) : '–'}</b><span>Average duration</span></div>
      </div>

      <div className="two">
        <div className="card">
          <h2>Your profile</h2>
          <p><b>Target job role:</b> {user?.target_role || <span className="muted">not set</span>}</p>
          <p><b>Experience level:</b> {user?.experience || <span className="muted">not set</span>}</p>
          <p><b>Industry:</b> {user?.industry || <span className="muted">not set</span>}</p>
          <p><b>Interview language:</b> {user?.language}</p>
          <Link className="btn light small" to="/profile">Edit profile settings</Link>
        </div>
        <div className="card">
          <h2>Recent interviews</h2>
          {recent.length === 0 ? <p className="muted">No interviews yet. Start your first one to see it here.</p> : (
            <div className="table-wrap"><table>
              <thead><tr><th>Date</th><th>Role</th><th>Answered</th><th></th></tr></thead>
              <tbody>{recent.map((r) => (
                <tr key={r.id}><td>{fmtDate(r.date)}</td><td>{r.role}</td><td>{r.answered}/{r.num_questions}</td><td><Link to={`/history/${r.id}`}>Review</Link></td></tr>
              ))}</tbody>
            </table></div>
          )}
        </div>
      </div>
    </>
  )
}

export function Profile() {
  const { user, setUser, logout } = useAuth()
  const nav = useNavigate()
  const [opts, setOpts] = useState<any>({ roles: [], experiences: [] })
  const [f, setF] = useState({ name: user?.name || '', target_role: user?.target_role || '', experience: user?.experience || '', industry: user?.industry || '', language: user?.language || 'English' })
  const [pw, setPw] = useState({ current_password: '', new_password: '' })
  const [msg, setMsg] = useState(''); const [error, setError] = useState('')
  useEffect(() => { api('/options').then(setOpts).catch(() => {}) }, [])
  const set = (k: string) => (e: any) => setF({ ...f, [k]: e.target.value })

  const save = async (e: FormEvent) => {
    e.preventDefault(); setMsg(''); setError('')
    try { setUser(await api('/profile', { method: 'PUT', body: f })); setMsg('Profile saved') } catch (err: any) { setError(err.message) }
  }
  const changePw = async (e: FormEvent) => {
    e.preventDefault(); setMsg(''); setError('')
    try { await api('/profile/password', { method: 'PUT', body: pw }); setMsg('Password changed'); setPw({ current_password: '', new_password: '' }) } catch (err: any) { setError(err.message) }
  }
  const remove = async () => {
    if (!confirm('Delete your account and all interview history? This cannot be undone.')) return
    await api('/profile', { method: 'DELETE' }); await logout(); nav('/login')
  }
  return (
    <>
      <div className="head"><div><h1>Profile & settings</h1><p className="muted">{user?.email}</p></div></div>
      {msg && <div className="ok">{msg}</div>}{error && <div className="error">{error}</div>}
      <div className="two">
        <form className="card" onSubmit={save}>
          <h2>Personal details</h2>
          <label>Full name<input required value={f.name} onChange={set('name')} /></label>
          <label>Target job role
            <input list="roles" value={f.target_role} onChange={set('target_role')} placeholder="e.g. DevOps Engineer" />
            <datalist id="roles">{opts.roles.map((r: string) => <option key={r} value={r} />)}</datalist>
          </label>
          <label>Experience level
            <input list="exps" value={f.experience} onChange={set('experience')} placeholder="e.g. Fresher" />
            <datalist id="exps">{opts.experiences.map((r: string) => <option key={r} value={r} />)}</datalist>
          </label>
          <label>Industry<input value={f.industry} onChange={set('industry')} placeholder="e.g. Fintech" /></label>
          <label>Preferred interview language
            <select value={f.language} onChange={set('language')}><option>English</option><option>Turkish</option></select>
          </label>
          <button className="btn">Save changes</button>
        </form>
        <div>
          <form className="card" onSubmit={changePw}>
            <h2>Change password</h2>
            <label>Current password<input type="password" required value={pw.current_password} onChange={(e) => setPw({ ...pw, current_password: e.target.value })} /></label>
            <label>New password<input type="password" required minLength={6} value={pw.new_password} onChange={(e) => setPw({ ...pw, new_password: e.target.value })} /></label>
            <button className="btn">Update password</button>
          </form>
          <div className="card">
            <h2>Account</h2>
            <div className="row">
              <button className="btn ghost" onClick={async () => { await logout(); nav('/login') }}>Log out</button>
              <button className="btn danger" onClick={remove}>Delete my account</button>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
