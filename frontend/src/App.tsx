import { BrowserRouter, Navigate, Outlet, Route, Routes, useParams } from 'react-router'
import { AuthProvider } from './auth/AuthProvider'
import { RequireAuth } from './auth/RequireAuth'
import { Header } from './components/Header'
import ChatsPage from './pages/chats/ChatsPage'
import LandingPage from './pages/LandingPage'
import LoginPage from './pages/LoginPage'
import SettingsPage from './pages/SettingsPage'

/** The history used to be its own page (spec 8). */
function OldSessionsRedirect() {
  const { chatId } = useParams()
  return <Navigate to={`/chats/${chatId}`} replace />
}

// Routes from spec section 8.
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
              <Route path="/chats/:chatId?" element={<ChatsPage />} />
              <Route path="/chats/:chatId/sessions" element={<OldSessionsRedirect />} />
              <Route path="/settings" element={<SettingsPage />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
