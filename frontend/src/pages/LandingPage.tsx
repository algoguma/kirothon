import { Link, Navigate } from 'react-router'
import { useAuth } from '../auth/context'
import { SERVICE_NAME } from '../brand'
import { Ghost } from '../components/Ghost'

const FEATURES = [
  { title: '채팅방별로 켜고 끄기', body: '자동 답장을 원하는 1:1 채팅방만 골라서 켭니다.' },
  { title: '내 말투로 답장', body: '30초~2분 뒤, 대화 내용을 보고 AI 분신이 대신 답합니다.' },
  { title: '직접 답하면 양보', body: '기다리는 동안 내가 답하면 분신은 답장하지 않습니다.' },
  { title: '기록 내려받기', body: '자동 답장 구간의 대화를 JSON, CSV, TXT로 받습니다.' },
]

// Spec 8 "/": landing page before login.
export default function LandingPage() {
  const { state } = useAuth()
  if (state.status === 'authenticated') return <Navigate to="/chats" replace />

  return (
    <main className="landing">
      <section className="hero">
        <Ghost size={180} animated />
        <div className="hero-text">
          <h1>{SERVICE_NAME}</h1>
          <p className="hero-sub">바쁠 땐 분신이 텔레그램 답장을 대신해 드려요.</p>
          <Link to="/login" className="button large">
            텔레그램으로 로그인
          </Link>
        </div>
      </section>

      <section className="features">
        {FEATURES.map((f) => (
          <article key={f.title} className="feature">
            <h2>{f.title}</h2>
            <p>{f.body}</p>
          </article>
        ))}
      </section>
    </main>
  )
}
