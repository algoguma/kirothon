import { BrowserRouter, NavLink, Navigate, Outlet, Route, Routes, useParams } from 'react-router'
import { useMock } from './api'
import { AuthProvider } from './auth/AuthProvider'
import { RequireAuth } from './auth/RequireAuth'
import { Brand } from './brand'
import LoginPage from './pages/LoginPage'
import SetupPage from './pages/SetupPage'

// Routes from spec section 8. Replace each placeholder with a page in src/pages/.
function Placeholder({ title }: { title: string }) {
  return <h1>{title}</h1>
}

function SessionsPage() {
  const { chatId } = useParams()
  return <Placeholder title={`세션 목록 (chat ${chatId})`} />
}

function Layout() {
  return (
    <>
      <nav className="nav">
        <Brand />
        <NavLink to="/chats">채팅방</NavLink>
        <NavLink to="/settings">설정</NavLink>
      </nav>
      <Outlet />
    </>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        {useMock && <div className="mock-badge">MOCK</div>}
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<RequireAuth />}>
            <Route path="/setup" element={<SetupPage />} />
            <Route element={<Layout />}>
              <Route path="/" element={<Navigate to="/chats" replace />} />
              <Route path="/chats" element={<Placeholder title="채팅방 목록" />} />
              <Route path="/chats/:chatId/sessions" element={<SessionsPage />} />
              <Route path="/settings" element={<Placeholder title="설정" />} />
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
