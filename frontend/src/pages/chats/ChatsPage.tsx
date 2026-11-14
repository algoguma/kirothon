import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router'
import { api, type Chat } from '../../api'
import { errorMessage } from '../../api/errors'
import { MockTag } from '../../components/MockTag'
import { formatKst } from '../../format'
import { AnalysisProgress } from './AnalysisProgress'
import { ChatSettingsModal } from './ChatSettingsModal'
import { HistoryPanel } from './HistoryPanel'

const POLL_MS = 10_000 // spec 8: refresh every 10 seconds
const ANALYSIS_POLL_MS = 3_000 // spec 8: faster while an analysis is running
const SEARCH_DEBOUNCE_MS = 300

// Spec 8 /chats and /chats/:chatId: chat list on the left, the selected chat's history on the right.
export default function ChatsPage() {
  const param = useParams().chatId
  const selectedChatId = param !== undefined && /^-?\d+$/.test(param) ? Number(param) : null
  const [chats, setChats] = useState<Chat[] | null>(null)
  const [query, setQuery] = useState('')
  const [loadError, setLoadError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [toggling, setToggling] = useState<Set<number>>(new Set())
  const [editing, setEditing] = useState<Chat | null>(null)
  // Bumped whenever a write starts or finishes. A list fetched across a write is stale,
  // so it is dropped instead of briefly undoing the user's change.
  const writeSeq = useRef(0)
  const pendingWrites = useRef(0)

  const load = useCallback(async (q: string) => {
    const seq = writeSeq.current
    try {
      const list = await api.chats(q.trim() || undefined)
      if (seq !== writeSeq.current || pendingWrites.current > 0) return
      setChats(list)
      setLoadError(null)
    } catch (e) {
      setLoadError(errorMessage(e))
    }
  }, [])

  const analyzing = chats?.some((c) => c.analysis_status === 'running') ?? false

  // Reload on search change (debounced) and then every POLL_MS (faster while analyzing).
  useEffect(() => {
    const first = setTimeout(() => load(query), SEARCH_DEBOUNCE_MS)
    const timer = setInterval(() => load(query), analyzing ? ANALYSIS_POLL_MS : POLL_MS)
    return () => {
      clearTimeout(first)
      clearInterval(timer)
    }
  }, [query, load, analyzing])

  const replace = useCallback(
    (updated: Chat) =>
      setChats((list) => list?.map((c) => (c.chat_id === updated.chat_id ? updated : c)) ?? list),
    [],
  )

  /** Run a write; polls that overlap it are ignored. */
  const write = useCallback(async <T,>(fn: () => Promise<T>): Promise<T> => {
    writeSeq.current++
    pendingWrites.current++
    try {
      return await fn()
    } finally {
      pendingWrites.current--
      writeSeq.current++
    }
  }, [])

  const toggle = async (chat: Chat) => {
    setActionError(null)
    setToggling((s) => new Set(s).add(chat.chat_id))
    try {
      replace(await write(() => api.updateAutoReply(chat.chat_id, { enabled: !chat.enabled })))
    } catch (e) {
      setActionError(errorMessage(e))
    } finally {
      setToggling((s) => {
        const next = new Set(s)
        next.delete(chat.chat_id)
        return next
      })
    }
  }

  // Stable callbacks: the modal returns focus on cleanup, so these must not change per render.
  const closeEditor = useCallback(() => setEditing(null), [])
  const onSaved = useCallback(
    (saved: Chat) => {
      replace(saved)
      setEditing(null)
    },
    [replace],
  )

  // A chat counts as on only after its analysis is done; until then it is "analyzing".
  const isAnalyzing = (c: Chat) => c.enabled && c.analysis_status === 'running'
  const enabledCount = chats?.filter((c) => c.enabled && !isAnalyzing(c)).length ?? 0
  const analyzingCount = chats?.filter(isAnalyzing).length ?? 0

  const selectedName = chats?.find((c) => c.chat_id === selectedChatId)?.name ?? null

  return (
    <main className={selectedChatId === null ? 'chats-split' : 'chats-split has-selection'}>
      <div className="chats-pane">
      <div className="page-head">
        <h1>
          채팅방 <MockTag group="chats" />
        </h1>
        {chats && (
          <span className="muted">
            자동 답장 켜짐 {enabledCount}개{analyzingCount > 0 && ` · 분석 중 ${analyzingCount}개`}
          </span>
        )}
      </div>

      <input
        className="search"
        type="search"
        placeholder="이름으로 검색"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />

      {actionError && (
        <p className="error" role="alert">
          {actionError}
        </p>
      )}
      {loadError && (
        <p className="error" role="alert">
          목록을 불러오지 못했습니다: {loadError}
        </p>
      )}

      {chats === null && !loadError && <p className="muted">불러오는 중…</p>}
      {chats?.length === 0 && (
        <p className="muted empty">{query ? '검색 결과가 없습니다.' : '1:1 채팅방이 없습니다.'}</p>
      )}

      <ul className="chat-list">
        {chats?.map((chat) => {
          const analyzing = isAnalyzing(chat)
          const on = chat.enabled && !analyzing
          return (
          <li
            key={chat.chat_id}
            className={[
              'chat-row',
              on && 'on',
              analyzing && 'analyzing',
              chat.chat_id === selectedChatId && 'selected',
            ]
              .filter(Boolean)
              .join(' ')}
          >
            <Link
              to={`/chats/${chat.chat_id}`}
              className="chat-main"
              aria-current={chat.chat_id === selectedChatId ? 'page' : undefined}
            >
              <div className="chat-name">{chat.name}</div>
              <div className="muted chat-meta">
                마지막 대화 {formatKst(chat.last_message_at)}
                {on && ` · ${chat.reply_delay_sec}초 뒤 답장`}
                {chat.analysis_status === 'ready' && <span className="chip ready">분신 준비 완료</span>}
                {chat.analysis_status === 'failed' && <span className="chip failed">기본 답장</span>}
              </div>
              {chat.analysis_status === 'running' && (
                <AnalysisProgress startedAt={chat.analysis_started_at} />
              )}
              {/* last_error holds AI failures and AI notes (emergency, "ask the owner"), spec 3.4. */}
              {chat.last_error && <div className="chat-error">⚠ 알림: {chat.last_error}</div>}
            </Link>
            <div className="chat-actions">
              <button type="button" className="secondary small" onClick={() => setEditing(chat)}>
                설정
              </button>
              <label
                className={analyzing ? 'switch pending' : 'switch'}
                title={analyzing ? '분석 중 (누르면 끄기)' : on ? '자동 답장 끄기' : '자동 답장 켜기'}
              >
                <input
                  type="checkbox"
                  role="switch"
                  checked={on}
                  disabled={toggling.has(chat.chat_id)}
                  onChange={() => toggle(chat)}
                  aria-label={`${chat.name} 자동 답장${analyzing ? ' (분석 중)' : ''}`}
                />
                <span className="slider" />
              </label>
            </div>
          </li>
          )
        })}
      </ul>
      </div>

      <div className="history-pane">
        {selectedChatId === null ? (
          <p className="muted history-empty">왼쪽에서 채팅방을 고르면 자동 답장 기록이 여기에 보입니다.</p>
        ) : (
          <HistoryPanel key={selectedChatId} chatId={selectedChatId} chatName={selectedName} />
        )}
      </div>

      {editing && (
        <ChatSettingsModal
          chat={editing}
          save={(body) => write(() => api.updateAutoReply(editing.chat_id, body))}
          onClose={closeEditor}
          onSaved={onSaved}
        />
      )}
    </main>
  )
}
