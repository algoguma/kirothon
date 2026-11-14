import type { ReactNode } from 'react'
import { Link, Navigate } from 'react-router'
import { useAuth } from '../auth/context'
import { CoverPoster } from '../components/CoverPoster'

// 24x24 stroke icons (currentColor).
const ICONS: Record<string, ReactNode> = {
  toggle: (
    <>
      <rect x="2" y="7" width="20" height="10" rx="5" />
      <circle cx="16" cy="12" r="3" fill="currentColor" />
    </>
  ),
  chat: (
    <>
      <path d="M4 5h16v10H9l-5 4z" />
      <path d="M8 9h8M8 12h5" />
    </>
  ),
  hand: (
    <>
      <path d="M8 13V5.5a1.5 1.5 0 0 1 3 0V11" />
      <path d="M11 10.5V4.5a1.5 1.5 0 0 1 3 0V11" />
      <path d="M14 10.5V6a1.5 1.5 0 0 1 3 0v7c0 4-2.5 7-6.5 7S5 17.5 4.5 15l-1-3.5a1.4 1.4 0 0 1 2.4-1.3L8 13" />
    </>
  ),
  download: (
    <>
      <path d="M12 4v11M7 10l5 5 5-5" />
      <path d="M5 20h14" />
    </>
  ),
}

const FEATURES = [
  { icon: 'toggle', title: '채팅방별로 켜고 끄기', body: '자동 답장을 원하는 1:1 채팅방만 골라서 켭니다.' },
  { icon: 'chat', title: '내 말투로 답장', body: '5초~2분 뒤, 대화 내용을 보고 AI 분신이 대신 답합니다.' },
  { icon: 'hand', title: '직접 답하면 양보', body: '기다리는 동안 내가 답하면 분신은 답장하지 않습니다.' },
  { icon: 'download', title: '기록 내려받기', body: '자동 답장 구간의 대화를 JSON, CSV, TXT로 받습니다.' },
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
            <svg
              className="feature-icon"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              {ICONS[f.icon]}
            </svg>
            <h2>{f.title}</h2>
            <p>{f.body}</p>
          </article>
        ))}
      </section>
    </main>
  )
}
