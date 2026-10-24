import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, fmtDate, fmtDuration } from '../api'
import { useAuth } from '../auth'

/* ---------- Interview configuration ---------- */
export function Configure() {
  const { user } = useAuth()
  const nav = useNavigate()
  const [opts, setOpts] = useState<any>({ roles: [], categories: [], experiences: [], difficulties: [] })
  const [cfg, setCfg] = useState<any>({ role: user?.target_role || '', experience: user?.experience || '', difficulty: '', categories: [] as string[], num_questions: 5 })
  const [review, setReview] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    api('/options').then((o) => {
      setLoaded(true)
      setOpts(o)
      setCfg((c: any) => ({
        ...c,
        role: o.roles.includes(c.role) ? c.role : o.roles[0] || '',
        experience: o.experiences.includes(c.experience) ? c.experience : o.experiences[0] || '',
        difficulty: o.difficulties.includes(c.difficulty) ? c.difficulty : o.difficulties[0] || '',
      }))
    }).catch((e) => setError(e.message))
  }, [])

  const toggle = (cat: string) =>
    setCfg({ ...cfg, categories: cfg.categories.includes(cat) ? cfg.categories.filter((c: string) => c !== cat) : [...cfg.categories, cat] })

  const start = async () => {
    setBusy(true); setError('')
    try {
      const r = await api('/interview/start', { body: { ...cfg, num_questions: Number(cfg.num_questions) } })
      nav(`/interview/${r.interview.id}`)
    } catch (e: any) { setError(e.message); setReview(false) } finally { setBusy(false) }
  }

  if (loaded && opts.roles.length === 0 && !error) {
    return <div className="card"><h1>No questions available yet</h1><p className="muted">An administrator needs to import the interview dataset before interviews can start.</p></div>
  }

  return (
    <>
      <div className="head"><div><h1>Set up your interview</h1><p className="muted">Questions are picked by semantic similarity to what you choose here.</p></div></div>
      {error && <div className="error">{error}</div>}
      {!review ? (
        <form className="card" onSubmit={(e) => { e.preventDefault(); setReview(true) }}>
          <div className="two">
            <label>Target job role
              <select value={cfg.role} onChange={(e) => setCfg({ ...cfg, role: e.target.value })}>{opts.roles.map((r: string) => <option key={r}>{r}</option>)}</select>
            </label>
            <label>Experience level
              <select value={cfg.experience} onChange={(e) => setCfg({ ...cfg, experience: e.target.value })}>{opts.experiences.map((r: string) => <option key={r}>{r}</option>)}</select>
            </label>
            <label>Difficulty
              <select value={cfg.difficulty} onChange={(e) => setCfg({ ...cfg, difficulty: e.target.value })}>{opts.difficulties.map((r: string) => <option key={r}>{r}</option>)}</select>
            </label>
            <label>Number of questions
              <input type="number" min={1} max={50} value={cfg.num_questions} onChange={(e) => setCfg({ ...cfg, num_questions: e.target.value })} />
            </label>
          </div>
          <p style={{ fontWeight: 600, marginBottom: '.4rem' }}>Interview categories <small>(leave empty to include all)</small></p>
          <div className="checks">
            {opts.categories.map((c: string) => (
              <label key={c} className={cfg.categories.includes(c) ? 'on' : ''}>
                <input type="checkbox" checked={cfg.categories.includes(c)} onChange={() => toggle(c)} />{c}
              </label>
            ))}
          </div>
          <button className="btn">Review setup</button>
        </form>
      ) : (
        <div className="card">
          <h2>Your interview</h2>
          <table><tbody>
            <tr><th>Job role</th><td>{cfg.role}</td></tr>
            <tr><th>Experience level</th><td>{cfg.experience}</td></tr>
            <tr><th>Difficulty</th><td>{cfg.difficulty}</td></tr>
            <tr><th>Categories</th><td>{cfg.categories.length ? cfg.categories.join(', ') : 'All categories'}</td></tr>
            <tr><th>Number of questions</th><td>{cfg.num_questions}</td></tr>
          </tbody></table>
          <div className="row" style={{ marginTop: '1rem' }}>
            <button className="btn" disabled={busy} onClick={start}>{busy ? 'Starting…' : 'Start interview'}</button>
            <button className="btn ghost" onClick={() => setReview(false)}>Change setup</button>
          </div>
        </div>
      )}
    </>
  )
}

/* ---------- Chat interview ---------- */
type Msg = { who: 'bot' | 'me' | 'sys' | 'q'; text: string; meta?: string }

export function Chat() {
  const { id } = useParams()
  const nav = useNavigate()
  const [iv, setIv] = useState<any>(null)
  const [q, setQ] = useState<any>(null)
  const [msgs, setMsgs] = useState<Msg[]>([])
  const [text, setText] = useState('')
  const [state, setState] = useState<'idle' | 'answered' | 'skipped'>('idle')
  const [ideal, setIdeal] = useState<any>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const [doneCount, setDoneCount] = useState(0)
  const bottom = useRef<HTMLDivElement>(null)
  const started = useRef(0)

  const push = (m: Msg) => setMsgs((x) => [...x, m])

  const finish = async () => {
    await api('/interview/finish', { body: { interview_id: Number(id) } })
    nav(`/interview/${id}/summary`, { replace: true })
  }

  const loadNext = async () => {
    setBusy(true); setError('')
    try {
      const r = await api(`/interview/question?interview_id=${id}`)
      if (r.done) { await finish(); return }
      setQ(r); setState('idle'); setIdeal(null); setText('')
      setDoneCount(r.index - 1)
      push({ who: 'q', text: r.question, meta: [r.category, r.source_type].filter(Boolean).join(' · ') })
    } catch (e: any) { setError(e.message) } finally { setBusy(false) }
  }

  const init = useRef(false)
  useEffect(() => {
    if (init.current) return // React StrictMode runs effects twice in development
    init.current = true
    api(`/interview/${id}`).then((d) => {
      if (d.finished) return nav(`/interview/${id}/summary`, { replace: true })
      setIv(d)
      started.current = Date.parse(d.started_at + 'Z')
      push({ who: 'bot', text: `Hello! I'm your HR interview coach. This is a ${d.difficulty.toLowerCase()} ${d.role} interview with ${d.num_questions} questions.` })
      push({ who: 'sys', text: 'Rules: answer in your own words and press Send Answer. You may skip a question. After answering you can open the ideal answer. Press Next Question to continue.' })
      loadNext()
    }).catch((e) => setError(e.message))
    // eslint-disable-next-line
  }, [id])

  useEffect(() => {
    const t = setInterval(() => started.current && setElapsed(Math.max(0, Math.floor((Date.now() - started.current) / 1000))), 1000)
    return () => clearInterval(t)
  }, [])

  useEffect(() => { bottom.current?.scrollIntoView({ behavior: 'smooth' }) }, [msgs, ideal])

  const send = async () => {
    if (!text.trim() || !q) return
    setBusy(true); setError('')
    try {
      await api('/interview/answer', { body: { interview_id: Number(id), interview_question_id: q.interview_question_id, answer: text } })
      push({ who: 'me', text: text.trim() }); setState('answered'); setDoneCount(q.index)
    } catch (e: any) { setError(e.message) } finally { setBusy(false) }
  }
  const skip = async () => {
    setBusy(true); setError('')
    try {
      await api('/interview/skip', { body: { interview_id: Number(id), interview_question_id: q.interview_question_id } })
      push({ who: 'sys', text: 'Question skipped.' }); setState('skipped'); setDoneCount(q.index)
    } catch (e: any) { setError(e.message) } finally { setBusy(false) }
  }
  const showIdeal = async () => {
    try { setIdeal(await api(`/interview/ideal/${q.interview_question_id}`)) } catch (e: any) { setError(e.message) }
  }

  const total = iv?.num_questions || 0
  const last = q && q.index >= total
  const answeredOrSkipped = state !== 'idle'

  return (
    <>
      <div className="head">
        <div><h1>{iv?.role || 'Interview'}</h1><p className="muted">{iv ? `${iv.experience} · ${iv.difficulty}` : ''}</p></div>
        <div className="row">
          <span className="pill">Remaining: {Math.max(0, total - doneCount)}</span>
          <span className="timer">⏱ {fmtDuration(elapsed)}</span>
        </div>
      </div>
      <div className="progress" aria-label="Interview progress"><div style={{ width: `${total ? (doneCount / total) * 100 : 0}%` }} /></div>
      <p className="muted" style={{ margin: '.4rem 0 0' }}>{q ? `Question ${q.index} of ${total}` : ''}</p>

      {error && <div className="error" style={{ marginTop: '1rem' }}>{error}</div>}

      <div className="chat">
        {msgs.map((m, i) => (
          <div key={i} className={`bubble ${m.who === 'me' ? 'me' : m.who === 'sys' ? 'sys' : 'bot'} ${m.who === 'q' ? 'q' : ''}`}>
            {m.who === 'q' && m.meta && <div><small>{m.meta}</small></div>}
            {m.text}
          </div>
        ))}
        {ideal && (
          <div className="ideal">
            <div className="row" style={{ marginBottom: '.5rem' }}>
              <span className="pill">{ideal.category}</span><span className="pill warn">{ideal.difficulty}</span>
            </div>
            <h2>Ideal answer</h2>
            <p>{ideal.ideal_answer || 'No ideal answer is stored for this question.'}</p>
            {ideal.keywords.length > 0 && <p><b>Keywords: </b>{ideal.keywords.map((k: string) => <span className="kw" key={k}>✓ {k}</span>)}</p>}
            <b>Interview tips</b>
            <ul>{ideal.tips.map((t: string, i: number) => <li key={i}>{t}</li>)}</ul>
          </div>
        )}
        <div ref={bottom} />
      </div>

      {q && (
        <div className="card">
          <textarea value={text} onChange={(e) => setText(e.target.value)} disabled={answeredOrSkipped || busy} placeholder="Type your answer here…" aria-label="Your answer" />
          <div className="row" style={{ marginTop: '.75rem' }}>
            <button className="btn" onClick={send} disabled={busy || answeredOrSkipped || !text.trim()}>Send answer</button>
            <button className="btn ghost" onClick={skip} disabled={busy || answeredOrSkipped}>Skip question</button>
            <button className="btn light" onClick={showIdeal} disabled={state !== 'answered' || !!ideal}>Show ideal answer</button>
            <span className="grow" />
            <button className="btn" onClick={last ? finish : loadNext} disabled={busy || !answeredOrSkipped}>{last ? 'Finish interview' : 'Next question'}</button>
          </div>
        </div>
      )}
    </>
  )
}

/* ---------- Summary / review of one interview ---------- */
export function InterviewDetail({ summary }: { summary?: boolean }) {
  const { id } = useParams()
  const [d, setD] = useState<any>(null)
  const [error, setError] = useState('')
  useEffect(() => { api(`/interview/${id}`).then(setD).catch((e) => setError(e.message)) }, [id])
  if (error) return <div className="error">{error}</div>
  if (!d) return <div className="muted">Loading…</div>
  return (
    <>
      <div className="head">
        <div><h1>{summary ? 'Interview complete' : 'Interview review'}</h1><p className="muted">Started {fmtDate(d.date)}{d.finished_at ? ` · Completed ${fmtDate(d.finished_at)}` : ''}</p></div>
        <div className="row"><Link className="btn" to="/interview/new">New interview</Link><Link className="btn ghost" to="/history">History</Link></div>
      </div>
      <div className="grid">
        <div className="stat"><b>{fmtDuration(d.duration)}</b><span>Duration</span></div>
        <div className="stat"><b>{d.num_questions}</b><span>Number of questions</span></div>
        <div className="stat"><b>{d.answered}</b><span>Answered</span></div>
        <div className="stat"><b>{d.skipped}</b><span>Skipped</span></div>
        <div className="stat"><b>{d.viewed_ideal}</b><span>Ideal answers viewed</span></div>
      </div>
      <div className="card"><b>{d.role}</b> · {d.experience} · {d.difficulty} · {d.categories.length ? d.categories.join(', ') : 'All categories'}</div>
      {d.items.map((it: any, i: number) => (
        <div className="card" key={it.id}>
          <small>Question {i + 1}{it.category ? ` · ${it.category}` : ''}</small>
          <h2>{it.question}</h2>
          {it.skipped ? <span className="pill bad">Skipped</span> : <p style={{ whiteSpace: 'pre-wrap' }}><b>Your answer: </b>{it.answer}</p>}
          {it.ideal_answer && (
            <details>
              <summary>Ideal answer {it.viewed_ideal ? '(you viewed this)' : ''}</summary>
              <div className="ideal" style={{ marginTop: '.5rem' }}>
                <p>{it.ideal_answer}</p>
                {it.keywords.map((k: string) => <span className="kw" key={k}>✓ {k}</span>)}
              </div>
            </details>
          )}
        </div>
      ))}
    </>
  )
}

/* ---------- History ---------- */
export function History() {
  const [rows, setRows] = useState<any[]>([])
  const [opts, setOpts] = useState<any>({ roles: [] })
  const [f, setF] = useState({ search: '', role: '', date_from: '', date_to: '' })
  const [error, setError] = useState('')
  useEffect(() => { api('/options').then(setOpts).catch(() => {}) }, [])
  useEffect(() => {
    const p = new URLSearchParams()
    Object.entries(f).forEach(([k, v]) => v && p.set(k, v))
    const t = setTimeout(() => api(`/interview/history?${p}`).then(setRows).catch((e) => setError(e.message)), 250)
    return () => clearTimeout(t)
  }, [f])
  return (
    <>
      <div className="head"><div><h1>Interview history</h1><p className="muted">Review earlier answers and ideal answers.</p></div></div>
      {error && <div className="error">{error}</div>}
      <div className="card row">
        <input className="grow" placeholder="Search role, question or answer" value={f.search} onChange={(e) => setF({ ...f, search: e.target.value })} aria-label="Search" />
        <select value={f.role} onChange={(e) => setF({ ...f, role: e.target.value })} aria-label="Filter by role"><option value="">All roles</option>{opts.roles.map((r: string) => <option key={r}>{r}</option>)}</select>
        <input type="date" value={f.date_from} onChange={(e) => setF({ ...f, date_from: e.target.value })} aria-label="From date" />
        <input type="date" value={f.date_to} onChange={(e) => setF({ ...f, date_to: e.target.value })} aria-label="To date" />
      </div>
      <div className="card table-wrap">
        {rows.length === 0 ? <p className="muted">No interviews match. Start one from “New interview”.</p> : (
          <table>
            <thead><tr><th>Date</th><th>Role</th><th>Level</th><th>Difficulty</th><th>Answered</th><th>Skipped</th><th>Duration</th><th></th></tr></thead>
            <tbody>{rows.map((r) => (
              <tr key={r.id}>
                <td>{fmtDate(r.date)}</td><td>{r.role}</td><td>{r.experience}</td><td>{r.difficulty}</td>
                <td>{r.answered}/{r.num_questions}</td><td>{r.skipped}</td><td>{fmtDuration(r.duration)}</td>
                <td><Link to={r.finished ? `/history/${r.id}` : `/interview/${r.id}`}>{r.finished ? 'Review' : 'Resume'}</Link></td>
              </tr>
            ))}</tbody>
          </table>
        )}
      </div>
    </>
  )
}
