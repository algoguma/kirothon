import { useState, type FormEvent } from 'react'
import { api, type Chat } from '../../api'
import { errorMessage } from '../../api/errors'

const MIN_DELAY = 30
const MAX_DELAY = 120

interface Props {
  chat: Chat
  onClose: () => void
  onSaved: (chat: Chat) => void
}

// Per-chat settings (spec 8 /chats): reply delay, AI instructions, fallback text.
export function ChatSettingsModal({ chat, onClose, onSaved }: Props) {
  const [delay, setDelay] = useState(chat.reply_delay_sec)
  const [instructions, setInstructions] = useState(chat.ai_instructions)
  const [fallback, setFallback] = useState(chat.fallback_text ?? '')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const saved = await api.updateAutoReply(chat.chat_id, {
        reply_delay_sec: delay,
        ai_instructions: instructions.trim(),
        fallback_text: fallback.trim() || null,
      })
      onSaved(saved)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="chat-settings-title"
        onClick={(e) => e.stopPropagation()}
        onKeyDown={(e) => e.key === 'Escape' && onClose()}
      >
        <h2 id="chat-settings-title">{chat.name} 자동 답장 설정</h2>
        <form onSubmit={submit}>
          <label>
            <span>
              답장 대기 시간: <strong>{delay}초</strong>
            </span>
            <input
              type="range"
              min={MIN_DELAY}
              max={MAX_DELAY}
              step={5}
              value={delay}
              onChange={(e) => setDelay(Number(e.target.value))}
            />
            <span className="muted small-inline">
              상대의 마지막 메시지 뒤로 이 시간 동안 새 메시지가 없으면 답장합니다.
            </span>
          </label>
          <label>
            AI 지침
            <textarea
              rows={3}
              placeholder="예: 지금 회의 중이라고 정중하게 안내해 줘"
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
            />
          </label>
          <label>
            대체 문구 (AI 실패 시)
            <input
              placeholder="비워 두면 AI가 실패했을 때 답장하지 않습니다"
              value={fallback}
              onChange={(e) => setFallback(e.target.value)}
            />
          </label>
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
          <div className="modal-actions">
            <button type="button" className="secondary" onClick={onClose} disabled={busy}>
              취소
            </button>
            <button disabled={busy}>{busy ? '저장 중…' : '저장'}</button>
          </div>
        </form>
      </div>
    </div>
  )
}
