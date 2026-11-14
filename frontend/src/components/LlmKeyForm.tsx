import { useState, type FormEvent } from 'react'
import { api, type LlmSettings } from '../api'
import { errorMessage } from '../api/errors'

interface Props {
  submitLabel: string
  autoFocus?: boolean
  onSaved: (llm: LlmSettings) => void
}

// API key input shared by /setup and /settings. PUT /api/me/llm verifies the key before saving.
export function LlmKeyForm({ submitLabel, autoFocus = false, onSaved }: Props) {
  const [apiKey, setApiKey] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const saved = await api.putLlm(apiKey.trim())
      setApiKey('')
      onSaved(saved)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit}>
      <label>
        API 키
        <input
          type="password"
          autoComplete="off"
          autoFocus={autoFocus}
          required
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
        />
      </label>
      <button disabled={busy || !apiKey.trim()}>{busy ? '연결 확인 중…' : submitLabel}</button>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
    </form>
  )
}
