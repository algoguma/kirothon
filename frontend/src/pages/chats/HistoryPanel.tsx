import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import {
  api,
  saveFile,
  type AutoReplySession,
  type ExportFormat,
  type SessionMessage,
} from '../../api'
import { errorMessage } from '../../api/errors'
import { MockTag } from '../../components/MockTag'
import { formatKst, formatKstTime } from '../../format'

const POLL_MS = 10_000 // same cadence as the chat list

const FORMATS: { format: ExportFormat; label: string }[] = [
  { format: 'json', label: 'JSON' },
  { format: 'csv', label: 'CSV' },
  { format: 'txt', label: 'TXT' },
]

interface Props {
  chatId: number
  /** From the chat list; null while it is loading or if the chat is not in it. */
  chatName: string | null
}

// Right pane of /chats/:chatId (spec 8): session list, conversation preview, export downloads.
// The parent renders it with key={chatId}, so every chat starts from a clean state.
export function HistoryPanel({ chatId, chatName }: Props) {
  const [sessions, setSessions] = useState<AutoReplySession[] | null>(null)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  // Preview result for one session; ignored while it belongs to another selection.
  const [preview, setPreview] = useState<{
    id: number
    messages?: SessionMessage[]
    error?: string
  } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [downloadError, setDownloadError] = useState<string | null>(null)
  const [downloading, setDownloading] = useState<ExportFormat | null>(null)

  // Load now, then every POLL_MS so counts, new sessions and session ends show up.
  useEffect(() => {
    let cancelled = false
    const load = (first: boolean) =>
      api.sessions(chatId).then(
        (list) => {
          if (cancelled) return
          setSessions(list)
          setError(null)
          // Pick the newest session; also when one appears later (auto reply turned on).
          setSelectedId((id) => id ?? list[0]?.id ?? null)
        },
        (e: unknown) => {
          // Keep the last good list on a failed refresh; the next tick retries.
          if (!cancelled && first) setError(errorMessage(e))
        },
      )
    load(true)
    const timer = setInterval(() => load(false), POLL_MS)
    return () => {
      cancelled = true
      clearInterval(timer)
    }
  }, [chatId])

  const selected = sessions?.find((s) => s.id === selectedId) ?? null
  const selectedLive = selected !== null && selected.ended_at === null

  useEffect(() => {
    if (selectedId === null) return
    let cancelled = false
    const fetchMessages = () =>
      api.sessionMessages(selectedId).then(
        (list) => !cancelled && setPreview({ id: selectedId, messages: list }),
        (e: unknown) => !cancelled && setPreview({ id: selectedId, error: errorMessage(e) }),
      )
    fetchMessages()
    // A live session keeps receiving messages (auto replies included); refresh the preview.
    const timer = selectedLive ? setInterval(fetchMessages, POLL_MS) : undefined
    return () => {
      cancelled = true
      clearInterval(timer)
    }
  }, [selectedId, selectedLive])

  const current = preview?.id === selectedId ? preview : null
  const messages = current?.messages ?? null
  const previewError = current?.error ?? downloadError

  const select = (id: number) => {
    setDownloadError(null)
    setSelectedId(id)
  }

  const exportAs = async (format: ExportFormat) => {
    if (selectedId === null) return
    setDownloading(format)
    setDownloadError(null)
    try {
      saveFile(await api.exportSession(selectedId, format))
    } catch (e) {
      setDownloadError(`다운로드 실패: ${errorMessage(e)}`)
    } finally {
      setDownloading(null)
    }
  }

  return (
    <section className="history" aria-label="자동 답장 기록">
      <Link to="/chats" className="back-link history-back">
        ← 채팅방 목록
      </Link>
      <h2 className="history-title">
        {chatName ?? `채팅방 ${chatId}`} 자동 답장 기록 <MockTag group="sessions" />
      </h2>

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {sessions === null && !error && <p className="muted">불러오는 중…</p>}
      {sessions?.length === 0 && (
        <p className="muted empty">아직 기록이 없습니다. 자동 답장을 켜면 그때부터 기록됩니다.</p>
      )}

      {sessions && sessions.length > 0 && (
        <>
          <ul className="session-tabs" aria-label="세션">
            {sessions.map((s) => (
              <li key={s.id}>
                <button
                  type="button"
                  className={s.id === selectedId ? 'session-item selected' : 'session-item'}
                  onClick={() => select(s.id)}
                  aria-pressed={s.id === selectedId}
                >
                  <span className="session-range">
                    {formatKst(s.started_at)} ~ {s.ended_at ? formatKst(s.ended_at) : '지금'}
                    {!s.ended_at && <span className="live-badge">진행 중</span>}
                  </span>
                  <span className="session-counts">
                    메시지 {s.message_count} · AI 답장 {s.auto_reply_count}
                  </span>
                </button>
              </li>
            ))}
          </ul>

          <div className="preview">
            {selected && (
              <div className="preview-head">
                <span className="muted small-inline">
                  {selected.ended_at ? '이 구간의 대화' : '진행 중인 세션은 현재 시각까지 내려받습니다'}
                </span>
                <div className="export-buttons">
                  {FORMATS.map(({ format, label }) => (
                    <button
                      key={format}
                      type="button"
                      className="secondary small"
                      disabled={downloading !== null}
                      onClick={() => exportAs(format)}
                    >
                      {downloading === format ? '받는 중…' : `${label} 받기`}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {previewError && (
              <p className="error" role="alert">
                {previewError}
              </p>
            )}
            {messages === null && !previewError && <p className="muted">불러오는 중…</p>}
            {messages?.length === 0 && <p className="muted empty">이 세션에는 아직 메시지가 없습니다.</p>}
            <ol className="bubbles">
              {messages?.map((msg) => (
                <li key={msg.message_id} className={msg.is_outgoing ? 'bubble-row out' : 'bubble-row in'}>
                  <div className={msg.is_auto_reply ? 'bubble ai' : 'bubble'}>
                    {msg.is_auto_reply && <span className="ai-badge">AI 분신</span>}
                    {!msg.is_outgoing && <span className="bubble-sender">{msg.sender_name}</span>}
                    <span className="bubble-text">{msg.text}</span>
                  </div>
                  <time className="bubble-time" dateTime={msg.date}>
                    {formatKstTime(msg.date)}
                  </time>
                </li>
              ))}
            </ol>
          </div>
        </>
      )}
    </section>
  )
}
