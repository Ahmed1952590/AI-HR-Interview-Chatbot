import { FormEvent, ReactNode, useEffect, useState } from 'react'
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, fmtDate, fmtDuration } from '../api'

const TEAL = '#14595a'
const AMBER = '#f0a23b'

function ChartCard({ title, children }: { title: string; children: ReactNode }) {
  return <div className="card"><h2>{title}</h2><div style={{ width: '100%', height: 260 }}><ResponsiveContainer>{children as any}</ResponsiveContainer></div></div>
}
const BarC = ({ data, x = 'name', color = TEAL, horizontal = false, width, height }: any) => (
  horizontal ? (
    <BarChart width={width} height={height} data={data} layout="vertical" margin={{ left: 40 }}>
      <CartesianGrid strokeDasharray="3 3" /><XAxis type="number" allowDecimals={false} /><YAxis type="category" dataKey={x} width={120} tick={{ fontSize: 12 }} />
      <Tooltip /><Bar dataKey="count" fill={color} radius={[0, 4, 4, 0]} />
    </BarChart>
  ) : (
    <BarChart width={width} height={height} data={data}>
      <CartesianGrid strokeDasharray="3 3" /><XAxis dataKey={x} tick={{ fontSize: 12 }} /><YAxis allowDecimals={false} /><Tooltip /><Bar dataKey="count" fill={color} radius={[4, 4, 0, 0]} />
    </BarChart>
  )
)

async function download() {
  const blob: Blob = await api('/analytics/export', { blob: true })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob); a.download = 'interview_report.csv'; a.click()
  URL.revokeObjectURL(a.href)
}

/* ---------- Dashboard ---------- */
export function AdminDashboard() {
  const [d, setD] = useState<any>(null)
  const [error, setError] = useState('')
  useEffect(() => { api('/analytics').then(setD).catch((e) => setError(e.message)) }, [])
  if (error) return <div className="error">{error}</div>
  if (!d) return <div className="muted">Loading…</div>
  return (
    <>
      <div className="head"><div><h1>Overview</h1><p className="muted">Active users = users who took an interview in the last 30 days.</p></div>
        <button className="btn light" onClick={download}>Export report (CSV)</button></div>
      <div className="grid">
        <div className="stat"><b>{d.total_users}</b><span>Total users</span></div>
        <div className="stat"><b>{d.active_users}</b><span>Active users</span></div>
        <div className="stat"><b>{d.total_interviews}</b><span>Total interviews</span></div>
        <div className="stat"><b>{d.total_questions.toLocaleString()}</b><span>Total questions</span></div>
        <div className="stat"><b>{d.total_categories}</b><span>Total categories</span></div>
        <div className="stat"><b>{fmtDuration(d.avg_duration)}</b><span>Average interview duration</span></div>
      </div>
      <div className="two">
        <ChartCard title="Daily interviews (last 30 days)">
          <LineChart data={d.daily}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="date" tickFormatter={(v: string) => v.slice(5)} tick={{ fontSize: 11 }} /><YAxis allowDecimals={false} /><Tooltip />
            <Line type="monotone" dataKey="count" stroke={TEAL} strokeWidth={2} dot={false} /></LineChart>
        </ChartCard>
        <ChartCard title="Monthly interviews"><BarC data={d.monthly} x="month" color={AMBER} /></ChartCard>
        <ChartCard title="Most selected job roles"><BarC data={d.top_roles} horizontal /></ChartCard>
        <ChartCard title="Most selected categories"><BarC data={d.top_categories} horizontal color={AMBER} /></ChartCard>
      </div>
    </>
  )
}

export function Reports() {
  const [d, setD] = useState<any>(null)
  const [users, setUsers] = useState<any[]>([])
  useEffect(() => {
    api('/analytics').then(setD).catch(() => {})
    api('/users?page_size=100').then((r) => setUsers(r.items)).catch(() => {})
  }, [])
  if (!d) return <div className="muted">Loading…</div>
  const ds = d.dataset
  return (
    <>
      <div className="head"><div><h1>Reports</h1><p className="muted">Question distribution, category statistics and user activity.</p></div>
        <button className="btn" onClick={download}>Export report (CSV)</button></div>
      <div className="two">
        <ChartCard title="Questions by difficulty"><BarC data={ds.by_difficulty} /></ChartCard>
        <ChartCard title="Questions by experience level"><BarC data={ds.by_experience} color={AMBER} /></ChartCard>
        <ChartCard title="Questions by category"><BarC data={ds.by_category} horizontal /></ChartCard>
        <ChartCard title="Questions by job role"><BarC data={ds.by_role} horizontal color={AMBER} /></ChartCard>
      </div>
      <div className="card table-wrap">
        <h2>User activity</h2>
        <table><thead><tr><th>Name</th><th>Email</th><th>Interviews</th><th>Last login</th></tr></thead>
          <tbody>{[...users].sort((a, b) => b.interviews - a.interviews).map((u) => (
            <tr key={u.id}><td>{u.name}</td><td>{u.email}</td><td>{u.interviews}</td><td>{u.last_login ? fmtDate(u.last_login) : '—'}</td></tr>
          ))}</tbody></table>
      </div>
    </>
  )
}

/* ---------- Questions ---------- */
const emptyQ = { question: '', category: '', role: '', experience: '', difficulty: 'Easy', source_type: '', ideal_answer: '', keywords: '' }

export function Questions() {
  const [data, setData] = useState<any>({ items: [], total: 0 })
  const [opts, setOpts] = useState<any>({ roles: [], categories: [], experiences: [], difficulties: [] })
  const [f, setF] = useState({ search: '', role: '', category: '', experience: '', difficulty: '', source_type: '' })
  const [page, setPage] = useState(1)
  const [form, setForm] = useState<any>(null)
  const [semantic, setSemantic] = useState(false)
  const [error, setError] = useState('')
  const size = 15

  const bySemantic = semantic && f.search.trim() !== ''
  const load = () => {
    if (bySemantic) {  // search by meaning: Sentence-BERT + FAISS nearest neighbours
      const sp = new URLSearchParams({ q: f.search, limit: '15' })
      if (f.role) sp.set('role', f.role)
      api(`/questions/semantic?${sp}`).then((r) => setData({ items: r.items, total: r.items.length })).catch((e) => setError(e.message))
      return
    }
    const p = new URLSearchParams({ page: String(page), page_size: String(size) })
    Object.entries(f).forEach(([k, v]) => v && p.set(k, v))
    api(`/questions?${p}`).then(setData).catch((e) => setError(e.message))
  }
  useEffect(() => { api('/options').then(setOpts).catch(() => {}) }, [])
  useEffect(() => { const t = setTimeout(load, 250); return () => clearTimeout(t) /* eslint-disable-next-line */ }, [f, page, semantic])

  const setFilter = (k: string) => (e: any) => { setPage(1); setF({ ...f, [k]: e.target.value }) }
  const edit = (q: any) => setForm({ ...q, keywords: q.keywords.join(', ') })

  const save = async (e: FormEvent) => {
    e.preventDefault(); setError('')
    const body = { ...form, keywords: form.keywords.split(',').map((k: string) => k.trim()).filter(Boolean) }
    try {
      if (form.id) await api(`/questions/${form.id}`, { method: 'PUT', body })
      else await api('/questions', { body })
      setForm(null); load(); api('/options').then(setOpts)
    } catch (err: any) { setError(err.message) }
  }
  const remove = async (q: any) => {
    if (!confirm('Delete this question?')) return
    await api(`/questions/${q.id}`, { method: 'DELETE' }); load()
  }
  const pages = Math.max(1, Math.ceil(data.total / size))
  const fld = (k: string, label: string, req = true, area = false) => (
    <label>{label}{area
      ? <textarea required={req} value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })} />
      : <input required={req} value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })} list={`dl-${k}`} />}</label>
  )

  return (
    <>
      <div className="head"><div><h1>Questions</h1><p className="muted">{data.total.toLocaleString()} questions match the current filters.</p></div>
        <button className="btn" onClick={() => setForm({ ...emptyQ })}>Add question</button></div>
      {error && <div className="error">{error}</div>}

      {form && (
        <form className="card" onSubmit={save}>
          <h2>{form.id ? 'Edit question' : 'New question'}</h2>
          {fld('question', 'Question', true, true)}
          <div className="two">
            {fld('category', 'Category')}{fld('role', 'Job role')}{fld('experience', 'Experience level')}
            <label>Difficulty<select value={form.difficulty} onChange={(e) => setForm({ ...form, difficulty: e.target.value })}><option>Easy</option><option>Medium</option><option>Hard</option></select></label>
            {fld('source_type', 'Source type', false)}{fld('keywords', 'Keywords (comma separated)', false)}
          </div>
          {fld('ideal_answer', 'Ideal answer', false, true)}
          <datalist id="dl-category">{opts.categories.map((c: string) => <option key={c} value={c} />)}</datalist>
          <datalist id="dl-role">{opts.roles.map((c: string) => <option key={c} value={c} />)}</datalist>
          <datalist id="dl-experience">{opts.experiences.map((c: string) => <option key={c} value={c} />)}</datalist>
          <div className="row"><button className="btn">Save question</button><button type="button" className="btn ghost" onClick={() => setForm(null)}>Cancel</button></div>
        </form>
      )}

      <div className="card row">
        <input className="grow" placeholder={semantic ? 'Describe what you are looking for' : 'Search question text'} value={f.search} onChange={setFilter('search')} aria-label="Search questions" />
        <label style={{ display: 'flex', alignItems: 'center', gap: '.4rem', margin: 0, fontWeight: 500 }}>
          <input type="checkbox" style={{ width: 'auto' }} checked={semantic} onChange={(e) => { setPage(1); setSemantic(e.target.checked) }} />Search by meaning
        </label>
        <select value={f.role} onChange={setFilter('role')} aria-label="Role"><option value="">All roles</option>{opts.roles.map((r: string) => <option key={r}>{r}</option>)}</select>
        <select value={f.category} onChange={setFilter('category')} aria-label="Category"><option value="">All categories</option>{opts.categories.map((r: string) => <option key={r}>{r}</option>)}</select>
        <select value={f.experience} onChange={setFilter('experience')} aria-label="Experience"><option value="">All levels</option>{opts.experiences.map((r: string) => <option key={r}>{r}</option>)}</select>
        <select value={f.difficulty} onChange={setFilter('difficulty')} aria-label="Difficulty"><option value="">All difficulties</option>{opts.difficulties.map((r: string) => <option key={r}>{r}</option>)}</select>
        <input style={{ width: 150 }} placeholder="Source type" value={f.source_type} onChange={setFilter('source_type')} aria-label="Source type" />
      </div>

      <div className="card table-wrap">
        <table>
          <thead><tr>{bySemantic && <th>Match</th>}<th>Question</th><th>Role</th><th>Level</th><th>Difficulty</th><th>Category</th><th>Type</th><th></th></tr></thead>
          <tbody>{data.items.map((q: any) => (
            <tr key={q.id}>
              {bySemantic && <td>{Number(q.score).toFixed(2)}</td>}<td style={{ minWidth: 260 }}>{q.question}</td><td>{q.role}</td><td>{q.experience}</td><td>{q.difficulty}</td><td>{q.category}</td><td>{q.source_type}</td>
              <td><div className="row"><button className="btn light small" onClick={() => edit(q)}>Edit</button><button className="btn danger small" onClick={() => remove(q)}>Delete</button></div></td>
            </tr>
          ))}</tbody>
        </table>
        {data.items.length === 0 && <p className="muted">No questions found. Import a dataset from the Dataset page.</p>}
        {!bySemantic && (
          <div className="row" style={{ marginTop: '1rem' }}>
            <button className="btn ghost small" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</button>
            <span className="muted">Page {page} of {pages}</span>
            <button className="btn ghost small" disabled={page >= pages} onClick={() => setPage(page + 1)}>Next</button>
          </div>
        )}
      </div>
    </>
  )
}

/* ---------- Users ---------- */
export function Users() {
  const [data, setData] = useState<any>({ items: [], total: 0 })
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [error, setError] = useState('')
  const [edit, setEdit] = useState<any>(null)
  const load = () => api(`/users?search=${encodeURIComponent(search)}&page=${page}&page_size=15`).then(setData).catch((e) => setError(e.message))
  useEffect(() => { const t = setTimeout(load, 250); return () => clearTimeout(t) /* eslint-disable-next-line */ }, [search, page])

  const patch = async (u: any, body: any) => {
    setError('')
    try { await api(`/users/${u.id}`, { method: 'PUT', body }); load() } catch (e: any) { setError(e.message) }
  }
  const remove = async (u: any) => {
    if (!confirm(`Delete ${u.email} and all their interviews?`)) return
    try { await api(`/users/${u.id}`, { method: 'DELETE' }); load() } catch (e: any) { setError(e.message) }
  }
  const saveEdit = async (e: FormEvent) => {
    e.preventDefault()
    await patch(edit, { name: edit.name, email: edit.email, role: edit.role, target_role: edit.target_role, experience: edit.experience })
    setEdit(null)
  }
  const pages = Math.max(1, Math.ceil(data.total / 15))
  return (
    <>
      <div className="head"><div><h1>Users</h1><p className="muted">{data.total} registered accounts</p></div></div>
      {error && <div className="error">{error}</div>}
      {edit && (
        <form className="card" onSubmit={saveEdit}>
          <h2>Edit {edit.email}</h2>
          <div className="two">
            <label>Name<input required value={edit.name} onChange={(e) => setEdit({ ...edit, name: e.target.value })} /></label>
            <label>Email<input type="email" required value={edit.email} onChange={(e) => setEdit({ ...edit, email: e.target.value })} /></label>
            <label>Target role<input value={edit.target_role} onChange={(e) => setEdit({ ...edit, target_role: e.target.value })} /></label>
            <label>Experience<input value={edit.experience} onChange={(e) => setEdit({ ...edit, experience: e.target.value })} /></label>
            <label>Account type<select value={edit.role} onChange={(e) => setEdit({ ...edit, role: e.target.value })}><option value="candidate">Candidate</option><option value="admin">Administrator</option></select></label>
          </div>
          <div className="row"><button className="btn">Save user</button><button type="button" className="btn ghost" onClick={() => setEdit(null)}>Cancel</button></div>
        </form>
      )}
      <div className="card"><input placeholder="Search by name or email" value={search} onChange={(e) => { setPage(1); setSearch(e.target.value) }} aria-label="Search users" /></div>
      <div className="card table-wrap">
        <table>
          <thead><tr><th>Name</th><th>Email</th><th>Type</th><th>Interviews</th><th>Status</th><th></th></tr></thead>
          <tbody>{data.items.map((u: any) => (
            <tr key={u.id}>
              <td>{u.name}</td><td>{u.email}</td><td>{u.role}</td><td>{u.interviews}</td>
              <td><span className={`pill ${u.is_active ? '' : 'bad'}`}>{u.is_active ? 'Active' : 'Disabled'}</span></td>
              <td><div className="row">
                <button className="btn light small" onClick={() => setEdit(u)}>Edit</button>
                <button className="btn ghost small" onClick={() => patch(u, { is_active: !u.is_active })}>{u.is_active ? 'Disable' : 'Activate'}</button>
                <button className="btn danger small" onClick={() => remove(u)}>Delete</button>
              </div></td>
            </tr>
          ))}</tbody>
        </table>
        <div className="row" style={{ marginTop: '1rem' }}>
          <button className="btn ghost small" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</button>
          <span className="muted">Page {page} of {pages}</span>
          <button className="btn ghost small" disabled={page >= pages} onClick={() => setPage(page + 1)}>Next</button>
        </div>
      </div>
    </>
  )
}

/* ---------- Dataset ---------- */
export function DatasetPage() {
  const [info, setInfo] = useState<any>({ datasets: [], total_questions: 0 })
  const [file, setFile] = useState<File | null>(null)
  const [limit, setLimit] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const load = () => api('/dataset/status').then(setInfo).catch((e) => setError(e.message))
  useEffect(() => { load() }, [])
  const running = info.datasets.some((d: any) => d.status === 'pending' || d.status === 'processing')
  useEffect(() => {
    if (!running) return
    const t = setInterval(load, 3000)
    return () => clearInterval(t)
  }, [running])

  const upload = async (e: FormEvent) => {
    e.preventDefault(); if (!file) return
    setBusy(true); setError('')
    const form = new FormData(); form.append('file', file); form.append('limit', limit || '0')
    try { await api('/dataset/upload', { form }); setFile(null); (e.target as HTMLFormElement).reset(); load() } catch (err: any) { setError(err.message) } finally { setBusy(false) }
  }
  const remove = async (d: any) => {
    if (!confirm('Delete this dataset and all questions imported from it?')) return
    try { await api(`/dataset/${d.id}`, { method: 'DELETE' }); load() } catch (err: any) { setError(err.message) }
  }
  return (
    <>
      <div className="head"><div><h1>Dataset</h1><p className="muted">{info.total_questions.toLocaleString()} questions in the database.</p></div></div>
      {error && <div className="error">{error}</div>}
      <form className="card" onSubmit={upload}>
        <h2>Import interview questions</h2>
        <p className="muted">CSV or JSON with columns: question, category, role, experience, difficulty, source_type, ideal_answer, keywords. Duplicate questions are skipped. Each question is embedded with Sentence-BERT and stored in FAISS, which takes a while for large files.</p>
        <div className="row">
          <input className="grow" type="file" accept=".csv,.json" onChange={(e) => setFile(e.target.files?.[0] || null)} aria-label="Dataset file" />
          <input style={{ width: 190 }} type="number" min={0} placeholder="Row limit (optional)" value={limit} onChange={(e) => setLimit(e.target.value)} aria-label="Row limit" />
          <button className="btn" disabled={!file || busy || running}>{busy ? 'Uploading…' : 'Upload and import'}</button>
        </div>
      </form>
      <div className="card table-wrap">
        <h2>Imports</h2>
        {info.datasets.length === 0 ? <p className="muted">Nothing imported yet. Upload your dataset above.</p> : (
          <table>
            <thead><tr><th>File</th><th>Status</th><th>Progress</th><th>Imported</th><th>Duplicates</th><th>Started</th><th></th></tr></thead>
            <tbody>{info.datasets.map((d: any) => (
              <tr key={d.id}>
                <td>{d.filename}</td>
                <td><span className={`pill ${d.status === 'failed' ? 'bad' : d.status === 'completed' ? '' : 'warn'}`}>{d.status}</span>{d.error && <div className="muted">{d.error}</div>}</td>
                <td>{d.total_rows ? `${d.processed}/${d.total_rows}` : '—'}</td><td>{d.imported}</td><td>{d.duplicates}</td><td>{fmtDate(d.created_at)}</td>
                <td><button className="btn danger small" onClick={() => remove(d)} disabled={d.status === 'processing'}>Delete</button></td>
              </tr>
            ))}</tbody>
          </table>
        )}
      </div>
    </>
  )
}

/* ---------- Categories & roles ---------- */
function Manager({ path, title }: { path: 'categories' | 'roles'; title: string }) {
  const [rows, setRows] = useState<any[]>([])
  const [name, setName] = useState('')
  const [error, setError] = useState('')
  const load = () => api(`/${path}`).then(setRows).catch((e) => setError(e.message))
  useEffect(() => { load() }, [])
  const wrap = async (fn: () => Promise<any>) => { setError(''); try { await fn(); load() } catch (e: any) { setError(e.message) } }
  return (
    <div className="card">
      <h2>{title}</h2>
      {error && <div className="error">{error}</div>}
      <form className="row" onSubmit={(e) => { e.preventDefault(); wrap(async () => { await api(`/${path}`, { body: { name } }); setName('') }) }}>
        <input className="grow" required minLength={2} placeholder="Add a new name" value={name} onChange={(e) => setName(e.target.value)} />
        <button className="btn">Add</button>
      </form>
      <table style={{ marginTop: '1rem' }}>
        <thead><tr><th>Name</th><th>Questions</th><th></th></tr></thead>
        <tbody>{rows.map((r) => (
          <tr key={r.id}><td>{r.name}</td><td>{r.questions}</td>
            <td><div className="row">
              <button className="btn light small" onClick={() => { const n = prompt('Rename to', r.name); if (n && n.trim().length > 1) wrap(() => api(`/${path}/${r.id}`, { method: 'PUT', body: { name: n } })) }}>Rename</button>
              <button className="btn danger small" onClick={() => confirm(`Delete "${r.name}"?`) && wrap(() => api(`/${path}/${r.id}`, { method: 'DELETE' }))}>Delete</button>
            </div></td></tr>
        ))}</tbody>
      </table>
    </div>
  )
}

export function Categories() {
  return (
    <>
      <div className="head"><div><h1>Categories & job roles</h1><p className="muted">Renaming updates every question that uses the name. An item can only be deleted when no question uses it.</p></div></div>
      <div className="two"><Manager path="categories" title="Interview categories" /><Manager path="roles" title="Job roles" /></div>
    </>
  )
}
