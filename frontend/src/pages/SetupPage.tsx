import { useEffect, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router'
import { api, type LlmSettings } from '../api'
import { errorMessage } from '../api/errors'
import { useAuth } from '../auth/context'

// Spec 8 /setup: one API key field. The backend verifies the key before saving.
export default function SetupPage() {
  const { state, setMe } = useAuth()
  const navigate = useNavigate()

  const [llm, setLlm] = useState<LlmSettings | null>(null)
  const [apiKey, setApiKey] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api.getLlm().then(setLlm, (e: unknown) => setError(errorMessage(e)))
  }, [])

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await api.putLlm(apiKey.trim())
      if (state.status === 'authenticated') setMe({ ...state.me, llm_configured: true })
      navigate('/chats', { replace: true })
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="card">
      <h1>LLM 연결 설정</h1>
      <p className="muted">GPU 서버 담당자에게 받은 API 키를 입력하세요. 저장할 때 연결을 확인합니다.</p>
      {llm && (
        <p className="muted small">
          모델: {llm.model}
          {llm.api_key_set && ` · 저장된 키 ${llm.api_key_hint ?? ''}`}
        </p>
      )}
      <form onSubmit={submit}>
        <label>
          API 키
          <input
            type="password"
            autoComplete="off"
            autoFocus
            required
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
          />
        </label>
        <button disabled={busy || !apiKey.trim()}>{busy ? '연결 확인 중…' : '저장'}</button>
      </form>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
    </main>
  )
}
