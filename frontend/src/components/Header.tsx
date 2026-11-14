import { Link, NavLink, useLocation } from 'react-router'
import { mockLabel, useMock } from '../api'
import { useAuth } from '../auth/context'
import { SERVICE_NAME } from '../brand'
import { ThemeToggle } from './ThemeToggle'

const ChatIcon = () => (
  <svg
    viewBox="0 0 24 24"
    width={20}
    height={20}
    fill="none"
    stroke="currentColor"
    strokeWidth={1.8}
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    <path d="M4 5h16v11H9l-5 4z" />
    <path d="M8 9.5h8M8 12.5h5" />
  </svg>
)

const GearIcon = () => (
  <svg
    viewBox="0 0 24 24"
    width={20}
    height={20}
    fill="none"
    stroke="currentColor"
    strokeWidth={1.8}
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" />
  </svg>
)

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
            <NavLink to="/chats" className="icon-button" aria-label="채팅방" title="채팅방">
              <ChatIcon />
            </NavLink>
          )}
          <ThemeToggle />
          {loggedIn && (
            <NavLink to="/settings" className="icon-button" aria-label="설정" title="설정">
              <GearIcon />
            </NavLink>
          )}
          {/* The landing page has its own login button; the login page needs none. */}
          {state.status === 'anonymous' && pathname !== '/' && pathname !== '/login' && (
            <Link to="/login" className="button small">
              로그인
            </Link>
          )}
        </nav>
      </div>
    </header>
  )
}
