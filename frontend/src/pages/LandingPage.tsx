import { Link, Navigate } from 'react-router'
import { useAuth } from '../auth/context'
import { CoverPoster } from '../components/CoverPoster'

const FEATURES = [
  { title: '채팅방별로 켜고 끄기', body: '자동 답장을 원하는 1:1 채팅방만 골라서 켭니다.' },
  { title: '내 말투로 답장', body: '5초~2분 뒤, 대화 내용을 보고 AI 분신이 대신 답합니다.' },
  { title: '직접 답하면 양보', body: '기다리는 동안 내가 답하면 분신은 답장하지 않습니다.' },
  { title: '기록 내려받기', body: '자동 답장 구간의 대화를 JSON, CSV, TXT로 받습니다.' },
]

// Spec 8 "/": landing page before login.
export default function LandingPage() {
  const { state } = useAuth()
  if (state.status === 'authenticated') return <Navigate to="/chats" replace />

  return (
    <main className="landing">
      <section className="hero-cover">
        <CoverPoster />
        <div className="hero-copy">
          <p className="hero-kicker">바쁜 당신 대신, 분신이 답장합니다</p>
          <h1>
            텔레그램 답장은
            <br />
            <span className="hero-accent">분신</span>에게 맡기세요
          </h1>
          <p className="hero-sub">
            자동 답장을 켠 채팅방에 메시지가 오면, 잠시 기다렸다가 AI 분신이 내 말투로 답합니다.
            내가 직접 답하면 분신은 조용히 물러납니다.
          </p>
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
