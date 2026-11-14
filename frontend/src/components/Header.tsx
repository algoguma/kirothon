import { Link, NavLink, useLocation } from 'react-router'
import { mockLabel, useMock } from '../api'
import { useAuth } from '../auth/context'
import { SERVICE_NAME } from '../brand'

// Fixed top bar shown on every screen (spec 8).
export function Header() {
  const { state } = useAuth()
  const { pathname } = useLocation()
  const loggedIn = state.status === 'authenticated'

  return (
    <header className="topbar">
      <div className="topbar-inner">
        <Link to="/" className="brand">
          <img src="/favicon.svg" alt="" width={28} height={28} />
          {SERVICE_NAME}
        </Link>
        {useMock && <span className="mock-badge">{mockLabel}</span>}
        <nav className="topbar-nav">
          {loggedIn && (
            <>
              <NavLink to="/chats">채팅방</NavLink>
              <NavLink to="/settings">설정</NavLink>
            </>
          )}
          {state.status === 'anonymous' && pathname !== '/login' && (
            <Link to="/login" className="button small">
              로그인
            </Link>
          )}
        </nav>
      </div>
    </header>
  )
}
