import { useState } from 'react'
import { api } from '../api'
import { errorMessage } from '../api/errors'
import { useAuth } from '../auth/context'
import { MockTag } from '../components/MockTag'

// Spec 8 /settings: log out. The LLM connection is shared and configured by the backend.
export default function SettingsPage() {
  const { state, setMe } = useAuth()
  const [error, setError] = useState<string | null>(null)
  const [loggingOut, setLoggingOut] = useState(false)

  const logout = async () => {
    const ok = window.confirm(
      '로그아웃하면 텔레그램 세션이 끊기고 자동 답장도 멈춥니다.\n다음 로그인 때 api_id와 api_hash를 다시 입력해야 합니다.\n\n로그아웃할까요?',
    )
    if (!ok) return
    setLoggingOut(true)
    setError(null)
    try {
      await api.logout()
      setMe(null) // RequireAuth sends a logged-out user to the landing page
    } catch (e) {
      setError(errorMessage(e))
      setLoggingOut(false)
    }
  }

  return (
    <main className="settings">
      <h1>설정</h1>

      <section className="panel">
        <h2>
          내 계정 <MockTag group="auth" />
        </h2>
        <dl className="kv">
          <dt>텔레그램 이름</dt>
          <dd>{state.status === 'authenticated' ? state.me.user.display_name : '-'}</dd>
        </dl>
      </section>

      <section className="panel">
        <h2>로그아웃</h2>
        <p className="muted small">
          텔레그램 세션을 끊고 이 기기에서 로그아웃합니다. 다음 로그인 때 api_id와 api_hash를 다시
          입력해야 합니다.
        </p>
        <button type="button" className="danger" onClick={logout} disabled={loggingOut}>
          {loggingOut ? '로그아웃 중…' : '로그아웃'}
        </button>
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
      </section>
    </main>
  )
}
