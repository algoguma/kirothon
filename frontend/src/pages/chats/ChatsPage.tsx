import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router'
import { api, type Chat } from '../../api'
import { errorMessage } from '../../api/errors'
import { MockTag } from '../../components/MockTag'
import { formatKst } from '../../format'
import { ChatSettingsModal } from './ChatSettingsModal'

const POLL_MS = 10_000 // spec 8: refresh every 10 seconds
const SEARCH_DEBOUNCE_MS = 300

// Spec 8 /chats: 1:1 chat list with auto-reply toggle and settings.
export default function ChatsPage() {
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

  // Reload on search change (debounced) and then every POLL_MS.
  useEffect(() => {
    const first = setTimeout(() => load(query), SEARCH_DEBOUNCE_MS)
    const timer = setInterval(() => load(query), POLL_MS)
    return () => {
      clearTimeout(first)
      clearInterval(timer)
    }
  }, [query, load])

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

  const enabledCount = chats?.filter((c) => c.enabled).length ?? 0

  return (
    <main>
      <div className="page-head">
        <h1>
          채팅방 <MockTag group="chats" />
        </h1>
        {chats && <span className="muted">자동 답장 켜짐 {enabledCount}개</span>}
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
        {chats?.map((chat) => (
          <li key={chat.chat_id} className={chat.enabled ? 'chat-row on' : 'chat-row'}>
            <div className="chat-main">
              <div className="chat-name">{chat.name}</div>
              <div className="muted chat-meta">
                마지막 대화 {formatKst(chat.last_message_at)}
                {chat.enabled && ` · ${chat.reply_delay_sec}초 뒤 답장`}
              </div>
              {chat.last_error && <div className="chat-error">⚠ 마지막 오류: {chat.last_error}</div>}
            </div>
            <div className="chat-actions">
              <Link to={`/chats/${chat.chat_id}/sessions`} className="button secondary small">
                기록
              </Link>
              <button type="button" className="secondary small" onClick={() => setEditing(chat)}>
                설정
              </button>
              <label className="switch" title={chat.enabled ? '자동 답장 끄기' : '자동 답장 켜기'}>
                <input
                  type="checkbox"
                  role="switch"
                  checked={chat.enabled}
                  disabled={toggling.has(chat.chat_id)}
                  onChange={() => toggle(chat)}
                  aria-label={`${chat.name} 자동 답장`}
                />
                <span className="slider" />
              </label>
            </div>
          </li>
        ))}
      </ul>

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
