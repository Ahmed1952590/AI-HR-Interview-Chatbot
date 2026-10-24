const BASE = '/api'

export const getToken = () => localStorage.getItem('token')
export const setToken = (t: string | null) => (t ? localStorage.setItem('token', t) : localStorage.removeItem('token'))

type Opts = { method?: string; body?: any; form?: FormData; blob?: boolean }

export async function api<T = any>(path: string, opts: Opts = {}): Promise<T> {
  const headers: Record<string, string> = {}
  const token = getToken()
  if (token) headers['Authorization'] = `Bearer ${token}`
  let body: any = undefined
  if (opts.form) body = opts.form
  else if (opts.body !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(opts.body)
  }
  const res = await fetch(BASE + path, { method: opts.method || (body ? 'POST' : 'GET'), headers, body })
  if (!res.ok) {
    let msg = `Request failed (${res.status})`
    try {
      const j = await res.json()
      if (typeof j.detail === 'string') msg = j.detail
      else if (Array.isArray(j.detail)) msg = j.detail.map((d: any) => `${(d.loc || []).slice(-1)[0]}: ${d.msg}`).join('; ')
    } catch {}
    if (res.status === 401 && token && !path.startsWith('/login')) {
      setToken(null)
      window.location.href = '/login'
    }
    throw new Error(msg)
  }
  if (opts.blob) return (await res.blob()) as any
  return res.json()
}

export const fmtDuration = (s: number) => {
  const m = Math.floor(s / 60)
  const r = s % 60
  return m ? `${m}m ${r}s` : `${r}s`
}
export const fmtDate = (iso: string) => new Date(iso + (iso.endsWith('Z') ? '' : 'Z')).toLocaleString()
