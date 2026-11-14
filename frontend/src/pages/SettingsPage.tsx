import { useEffect, useState } from 'react'
import { api, type LlmSettings } from '../api'
import { errorMessage } from '../api/errors'
import { useAuth } from '../auth/context'
import { LlmKeyForm } from '../components/LlmKeyForm'
import { MockTag } from '../components/MockTag'
import { formatKst } from '../format'

// Spec 8 /settings: change the LLM key, log out.
export default function SettingsPage() {
  const { state, setMe } = useAuth()

  const [llm, setLlm] = useState<LlmSettings | null>(null)
  const [llmError, setLlmError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)
  const [logoutError, setLogoutError] = useState<string | null>(null)
  const [loggingOut, setLoggingOut] = useState(false)

  useEffect(() => {
    api.getLlm().then(setLlm, (e: unknown) => setLlmError(errorMessage(e)))
  }, [])

  const logout = async () => {
    const ok = window.confirm(
      '로그아웃하면 텔레그램 세션이 끊기고 자동 답장도 멈춥니다.\n다음 로그인 때 api_id와 api_hash를 다시 입력해야 합니다.\n\n로그아웃할까요?',
    )
    if (!ok) return
    setLoggingOut(true)
    setLogoutError(null)
    try {
      await api.logout()
      setMe(null) // RequireAuth sends a logged-out user to the landing page
    } catch (e) {
      setLogoutError(errorMessage(e))
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
        <h2>
          LLM 연결 <MockTag group="llm" />
        </h2>
        {llmError && (
          <p className="error" role="alert">
            {llmError}
          </p>
        )}
        {llm && (
          <dl className="kv">
            <dt>모델</dt>
            <dd>{llm.model}</dd>
            <dt>저장된 키</dt>
            <dd>{llm.api_key_set ? llm.api_key_hint : '없음'}</dd>
            <dt>마지막 확인</dt>
            <dd>{formatKst(llm.verified_at)}</dd>
          </dl>
        )}
        <p className="muted small">새 키를 저장하면 연결을 먼저 확인합니다. 실패하면 기존 키를 유지합니다.</p>
        <LlmKeyForm
          submitLabel={llm?.api_key_set ? '키 변경' : '키 저장'}
          onSaved={(next) => {
            setLlm(next)
            setSaved(true)
            if (state.status === 'authenticated' && !state.me.llm_configured) {
              setMe({ ...state.me, llm_configured: true })
            }
          }}
        />
        {saved && <p className="success">키를 저장했습니다.</p>}
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
        {logoutError && (
          <p className="error" role="alert">
            {logoutError}
          </p>
        )}
      </section>
    </main>
  )
}
