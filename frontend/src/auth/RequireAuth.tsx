import { Navigate, Outlet, useLocation } from 'react-router'
import { useAuth } from './context'

export function RequireAuth() {
  const { state } = useAuth()
  const location = useLocation()

  if (state.status === 'loading') return <p className="muted">불러오는 중…</p>
  if (state.status === 'anonymous') return <Navigate to="/login" replace state={{ from: location }} />
  return <Outlet />
}
