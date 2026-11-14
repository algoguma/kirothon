import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { api, type LlmSettings } from '../api'
import { errorMessage } from '../api/errors'
import { useAuth } from '../auth/context'
import { LlmKeyForm } from '../components/LlmKeyForm'
import { MockTag } from '../components/MockTag'

// Spec 8 /setup: one API key field. The backend verifies the key before saving.
export default function SetupPage() {
  const { state, setMe } = useAuth()
  const navigate = useNavigate()
  const [llm, setLlm] = useState<LlmSettings | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.getLlm().then(setLlm, (e: unknown) => setError(errorMessage(e)))
  }, [])

  return (
    <main className="card">
      <img className="card-logo" src="/favicon.svg" alt="" width={64} height={64} />
      <h1>
        LLM 연결 설정 <MockTag group="llm" />
      </h1>
      <p className="muted">GPU 서버 담당자에게 받은 API 키를 입력하세요. 저장할 때 연결을 확인합니다.</p>
      {llm && (
        <p className="muted small">
          모델: {llm.model}
          {llm.api_key_set && ` · 저장된 키 ${llm.api_key_hint ?? ''}`}
        </p>
      )}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <LlmKeyForm
        submitLabel="저장"
        autoFocus
        onSaved={() => {
          if (state.status === 'authenticated') setMe({ ...state.me, llm_configured: true })
          navigate('/chats', { replace: true })
        }}
      />
    </main>
  )
}
