import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router'
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

const POLL_MS = 10_000 // same cadence as /chats

const FORMATS: { format: ExportFormat; label: string }[] = [
  { format: 'json', label: 'JSON' },
  { format: 'csv', label: 'CSV' },
  { format: 'txt', label: 'TXT' },
]

// Spec 8 /chats/:chatId/sessions: session list, conversation preview, export downloads.
export default function SessionsPage() {
  const chatId = Number(useParams().chatId)
  const [chatName, setChatName] = useState<string | null>(null)
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

  useEffect(() => {
    // There is no single-chat API; take the name from the list.
    api.chats().then(
      (list) => setChatName(list.find((c) => c.chat_id === chatId)?.name ?? `채팅방 ${chatId}`),
      () => setChatName(`채팅방 ${chatId}`),
    )
    api.sessions(chatId).then(
      (list) => {
        setSessions(list)
        setSelectedId(list[0]?.id ?? null)
      },
      (e: unknown) => setError(errorMessage(e)),
    )
  }, [chatId])

  // Refresh the list every POLL_MS so counts, new sessions and session ends show up.
  useEffect(() => {
    const timer = setInterval(() => {
      api.sessions(chatId).then(
        (list) => {
          setSessions(list)
          setError(null)
          // A session appeared while nothing was selected (e.g. auto reply just turned on).
          setSelectedId((id) => id ?? list[0]?.id ?? null)
        },
        () => {}, // keep showing the last good list; the next tick retries
      )
    }, POLL_MS)
    return () => clearInterval(timer)
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
    <main>
      <Link to="/chats" className="back-link">
        ← 채팅방 목록
      </Link>
      <h1>
        {chatName ?? '…'} 자동 답장 기록 <MockTag group="sessions" />
      </h1>

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
        <div className="sessions-layout">
          <ul className="session-list">
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

          <section className="preview">
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
          </section>
        </div>
      )}
    </main>
  )
}
