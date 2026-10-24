import { createContext, useContext, useEffect, useState, ReactNode } from 'react'
import { api, getToken, setToken } from './api'

export type User = {
  id: number; name: string; email: string; role: 'candidate' | 'admin'; is_active: boolean
  target_role: string; experience: string; industry: string; language: string
}
type Ctx = {
  user: User | null; loading: boolean
  login: (email: string, password: string) => Promise<User>
  register: (name: string, email: string, password: string) => Promise<User>
  logout: () => Promise<void>
  setUser: (u: User) => void
}
const AuthCtx = createContext<Ctx>(null as any)
export const useAuth = () => useContext(AuthCtx)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(!!getToken())

  useEffect(() => {
    if (!getToken()) return
    api<User>('/profile').then(setUser).catch(() => setToken(null)).finally(() => setLoading(false))
  }, [])

  const finish = (r: any) => { setToken(r.access_token); setUser(r.user); return r.user as User }
  const login = async (email: string, password: string) => finish(await api('/login', { body: { email, password } }))
  const register = async (name: string, email: string, password: string) => finish(await api('/register', { body: { name, email, password } }))
  const logout = async () => {
    try { await api('/logout', { method: 'POST' }) } catch {}
    setToken(null); setUser(null)
  }
  return <AuthCtx.Provider value={{ user, loading, login, register, logout, setUser }}>{children}</AuthCtx.Provider>
}
