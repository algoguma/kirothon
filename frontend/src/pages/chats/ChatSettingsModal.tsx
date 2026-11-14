import { useEffect, useState, type FormEvent } from 'react'
import { type AutoReplyUpdate, type Chat } from '../../api'
import { errorMessage } from '../../api/errors'

const MIN_DELAY = 5
const MAX_DELAY = 120

interface Props {
  chat: Chat
  /** Sends the update; the page wraps it so overlapping list refreshes are ignored. */
  save: (body: AutoReplyUpdate) => Promise<Chat>
  onClose: () => void
  onSaved: (chat: Chat) => void
}

// Per-chat settings (spec 8 /chats): reply delay, AI instructions, fallback text.
export function ChatSettingsModal({ chat, save, onClose, onSaved }: Props) {
  const [delay, setDelay] = useState(chat.reply_delay_sec)
  const [instructions, setInstructions] = useState(chat.ai_instructions)
  const [fallback, setFallback] = useState(chat.fallback_text ?? '')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  // Remember the opener during the first render, before autoFocus moves focus into the modal.
  const [opener] = useState(() => document.activeElement as HTMLElement | null)

  // Close on Esc wherever focus is; return focus to the opener when the modal goes away.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])
  useEffect(() => () => opener?.focus(), [opener])
  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const saved = await save({
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
      >
        <h2 id="chat-settings-title">{chat.name} 자동 답장 설정</h2>
        <form onSubmit={submit}>
          <label>
            <span>
              답장 대기 시간: <strong>{delay}초</strong>
            </span>
            <input
              type="range"
              autoFocus
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
