import { BrowserRouter, Link, Navigate, Route, Routes, useParams } from 'react-router'
import { useMock } from './api'

// Routes from spec section 8. Replace each placeholder with a page in src/pages/.
function Placeholder({ title }: { title: string }) {
  return <h1>{title}</h1>
}

function SessionsPage() {
  const { chatId } = useParams()
  return <Placeholder title={`세션 목록 (chat ${chatId})`} />
}

export default function App() {
  return (
    <BrowserRouter>
      <nav style={{ display: 'flex', gap: 12 }}>
        <Link to="/login">로그인</Link>
        <Link to="/setup">LLM 설정</Link>
        <Link to="/chats">채팅방</Link>
        <Link to="/settings">설정</Link>
        {useMock && <strong>MOCK</strong>}
      </nav>
      <Routes>
        <Route path="/" element={<Navigate to="/chats" replace />} />
        <Route path="/login" element={<Placeholder title="로그인" />} />
        <Route path="/setup" element={<Placeholder title="LLM 설정" />} />
        <Route path="/chats" element={<Placeholder title="채팅방 목록" />} />
        <Route path="/chats/:chatId/sessions" element={<SessionsPage />} />
        <Route path="/settings" element={<Placeholder title="설정" />} />
      </Routes>
    </BrowserRouter>
  )
}
