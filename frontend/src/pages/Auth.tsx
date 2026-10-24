import { FormEvent, ReactNode, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'

function AuthCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="auth">
      <div className="card">
        <p className="muted" style={{ margin: 0, fontWeight: 700 }}>HR Interview Coach</p>
        <h1>{title}</h1>
        {children}
      </div>
    </div>
  )
}

export function Login() {
  const { login } = useAuth()
  const nav = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setError('')
    try { const u = await login(email, password); nav(u.role === 'admin' ? '/admin' : '/') } catch (err: any) { setError(err.message) }
  }
  return (
    <AuthCard title="Log in">
      {error && <div className="error">{error}</div>}
      <form onSubmit={submit}>
        <label>Email<input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></label>
        <label>Password<input type="password" required value={password} onChange={(e) => setPassword(e.target.value)} /></label>
        <button className="btn" style={{ width: '100%' }}>Log in</button>
      </form>
      <p style={{ marginTop: '1rem' }}><Link to="/forgot-password">Forgot password?</Link> · <Link to="/register">Create an account</Link></p>
    </AuthCard>
  )
}

export function Register() {
  const { register } = useAuth()
  const nav = useNavigate()
  const [f, setF] = useState({ name: '', email: '', password: '', confirm: '' })
  const [error, setError] = useState('')
  const set = (k: string) => (e: any) => setF({ ...f, [k]: e.target.value })
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setError('')
    if (f.password !== f.confirm) return setError('Passwords do not match')
    try { await register(f.name, f.email, f.password); nav('/profile') } catch (err: any) { setError(err.message) }
  }
  return (
    <AuthCard title="Create your account">
      {error && <div className="error">{error}</div>}
      <form onSubmit={submit}>
        <label>Full name<input required minLength={2} value={f.name} onChange={set('name')} /></label>
        <label>Email<input type="email" required value={f.email} onChange={set('email')} /></label>
        <label>Password (6+ characters)<input type="password" required minLength={6} value={f.password} onChange={set('password')} /></label>
        <label>Confirm password<input type="password" required value={f.confirm} onChange={set('confirm')} /></label>
        <button className="btn" style={{ width: '100%' }}>Create account</button>
      </form>
      <p style={{ marginTop: '1rem' }}>Already registered? <Link to="/login">Log in</Link></p>
    </AuthCard>
  )
}

export function Forgot() {
  const [email, setEmail] = useState('')
  const [res, setRes] = useState<any>(null)
  const [error, setError] = useState('')
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setError('')
    try { setRes(await api('/forgot-password', { body: { email } })) } catch (err: any) { setError(err.message) }
  }
  return (
    <AuthCard title="Reset your password">
      {error && <div className="error">{error}</div>}
      {res ? (
        <>
          <div className="ok">{res.message}</div>
          {res.reset_token && (
            <p>Demo mode (no mail server): <Link to={`/reset-password?token=${encodeURIComponent(res.reset_token)}`}>choose a new password</Link>.</p>
          )}
        </>
      ) : (
        <form onSubmit={submit}>
          <label>Your account email<input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></label>
          <button className="btn" style={{ width: '100%' }}>Get reset link</button>
        </form>
      )}
      <p style={{ marginTop: '1rem' }}><Link to="/login">Back to log in</Link></p>
    </AuthCard>
  )
}

export function Reset() {
  const [params] = useSearchParams()
  const [token, setToken] = useState(params.get('token') || '')
  const [pw, setPw] = useState('')
  const [msg, setMsg] = useState('')
  const [error, setError] = useState('')
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setError('')
    try { const r = await api('/reset-password', { body: { token, new_password: pw } }); setMsg(r.message) } catch (err: any) { setError(err.message) }
  }
  return (
    <AuthCard title="Choose a new password">
      {error && <div className="error">{error}</div>}
      {msg ? <div className="ok">{msg} <Link to="/login">Log in</Link></div> : (
        <form onSubmit={submit}>
          <label>Reset token<input required value={token} onChange={(e) => setToken(e.target.value)} /></label>
          <label>New password<input type="password" required minLength={6} value={pw} onChange={(e) => setPw(e.target.value)} /></label>
          <button className="btn" style={{ width: '100%' }}>Save new password</button>
        </form>
      )}
    </AuthCard>
  )
}
