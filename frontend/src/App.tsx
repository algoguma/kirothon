import { BrowserRouter, Navigate, Outlet, Route, Routes, useParams } from 'react-router'
import { AuthProvider } from './auth/AuthProvider'
import { RequireAuth } from './auth/RequireAuth'
import { Header } from './components/Header'
import ChatsPage from './pages/chats/ChatsPage'
import LandingPage from './pages/LandingPage'
import LoginPage from './pages/LoginPage'
import SettingsPage from './pages/SettingsPage'

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
      <Header />
      <div className="container">
        <Outlet />
      </div>
    </>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<LandingPage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route element={<RequireAuth />}>
              <Route path="/chats" element={<ChatsPage />} />
              <Route path="/chats/:chatId/sessions" element={<SessionsPage />} />
              <Route path="/settings" element={<SettingsPage />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
