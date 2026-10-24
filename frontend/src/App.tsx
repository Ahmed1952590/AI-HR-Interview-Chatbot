import { ReactNode } from 'react'
import { Navigate, NavLink, Route, Routes, Outlet } from 'react-router-dom'
import { useAuth } from './auth'
import { Login, Register, Forgot, Reset } from './pages/Auth'
import { Dashboard, Profile } from './pages/Candidate'
import { Configure, Chat, InterviewDetail, History } from './pages/Interview'
import { AdminDashboard, Reports, Questions, Users, DatasetPage, Categories } from './pages/Admin'

function Guard({ role, children }: { role?: 'admin' | 'candidate'; children: ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="center muted">Loading…</div>
  if (!user) return <Navigate to="/login" replace />
  if (role && user.role !== role) return <Navigate to={user.role === 'admin' ? '/admin' : '/'} replace />
  return <>{children}</>
}

function Shell() {
  const { user, logout } = useAuth()
  const admin = user?.role === 'admin'
  const links = admin
    ? [['/admin', 'Overview'], ['/admin/questions', 'Questions'], ['/admin/dataset', 'Dataset'], ['/admin/categories', 'Categories & roles'], ['/admin/users', 'Users'], ['/admin/reports', 'Reports']]
    : [['/', 'Dashboard'], ['/interview/new', 'New interview'], ['/history', 'History'], ['/profile', 'Profile & settings']]
  return (
    <div className="shell">
      <aside className="side">
        <div className="brand">HR Interview<br />Coach</div>
        <nav>
          {links.map(([to, label]) => (
            <NavLink key={to} to={to} end={to === '/' || to === '/admin'}>{label}</NavLink>
          ))}
        </nav>
        <div className="side-foot">
          <div className="who">{user?.name}<small>{admin ? 'Administrator' : 'Candidate'}</small></div>
          <button className="btn ghost" onClick={logout}>Log out</button>
        </div>
      </aside>
      <main className="main"><Outlet /></main>
    </div>
  )
}

export default function App() {
  const { user } = useAuth()
  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to={user.role === 'admin' ? '/admin' : '/'} /> : <Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/forgot-password" element={<Forgot />} />
      <Route path="/reset-password" element={<Reset />} />
      <Route element={<Guard role="candidate"><Shell /></Guard>}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/interview/new" element={<Configure />} />
        <Route path="/interview/:id" element={<Chat />} />
        <Route path="/interview/:id/summary" element={<InterviewDetail summary />} />
        <Route path="/history" element={<History />} />
        <Route path="/history/:id" element={<InterviewDetail />} />
        <Route path="/profile" element={<Profile />} />
      </Route>
      <Route element={<Guard role="admin"><Shell /></Guard>}>
        <Route path="/admin" element={<AdminDashboard />} />
        <Route path="/admin/questions" element={<Questions />} />
        <Route path="/admin/dataset" element={<DatasetPage />} />
        <Route path="/admin/categories" element={<Categories />} />
        <Route path="/admin/users" element={<Users />} />
        <Route path="/admin/reports" element={<Reports />} />
      </Route>
      <Route path="*" element={<Navigate to="/" />} />
    </Routes>
  )
}
