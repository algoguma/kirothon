// In-memory mock that follows spec 7. Extend freely while the backend is not ready.
import { ApiError } from './http'
import { isMocked } from './mockConfig'
import type { Api } from './real'
import type { AutoReplySession, Chat, MeResponse, SessionMessage } from './types'

const delay = (ms = 200) => new Promise((r) => setTimeout(r, ms))

let loggedIn = false
const me = (): MeResponse => ({ user: { id: 1, display_name: '홍길동' } })

const chats: Chat[] = [
  {
    chat_id: 123456789,
    name: '김철수',
    last_message_at: '2026-11-14T01:20:00Z',
    enabled: true,
    reply_delay_sec: 30,
    ai_instructions: '회의 중이라고 안내',
    fallback_text: '나중에 연락드릴게요.',
    current_session_id: 7,
    last_error: null,
  },
  {
    chat_id: 987654321,
    name: '이영희',
    last_message_at: '2026-11-13T12:00:00Z',
    enabled: false,
    reply_delay_sec: 60,
    ai_instructions: '',
    fallback_text: null,
    current_session_id: null,
    last_error: 'LLM 호출 시간 초과',
  },
]

const sessions: Record<number, AutoReplySession[]> = {
  123456789: [
    { id: 7, started_at: '2026-11-14T01:00:00Z', ended_at: null, message_count: 3, auto_reply_count: 1 },
  ],
}

let nextSessionId = 8

const messages: Record<number, SessionMessage[]> = {
  7: [
    { message_id: 555, sender_name: '김철수', text: '안녕', date: '2026-11-14T01:01:00Z', is_outgoing: false, is_auto_reply: false },
    { message_id: 556, sender_name: '김철수', text: '지금 통화 돼?', date: '2026-11-14T01:01:10Z', is_outgoing: false, is_auto_reply: false },
    { message_id: 557, sender_name: '나', text: '지금 회의 중이라 끝나고 연락드릴게요.', date: '2026-11-14T01:01:45Z', is_outgoing: true, is_auto_reply: true },
  ],
}

function requireLogin() {
  // When auth goes to the real backend, the backend cookie decides; mock data is shared.
  if (isMocked('auth') && !loggedIn) throw new ApiError(401, 'UNAUTHORIZED', '로그인이 필요합니다.')
}

function findChat(chatId: number): Chat {
  const chat = chats.find((c) => c.chat_id === chatId)
  if (!chat) throw new ApiError(404, 'NOT_FOUND', '채팅방을 찾을 수 없습니다.')
  return chat
}

export const mockApi: Api = {
  async sendCode({ api_hash }) {
    await delay()
    if (!/^[0-9a-f]{32}$/i.test(api_hash)) {
      throw new ApiError(400, 'INVALID_API_CREDENTIALS', 'api_id 또는 api_hash가 올바르지 않습니다.')
    }
    return { login_id: 'mock-login' }
  },
  async signIn(_loginId, code) {
    await delay()
    if (code === '00000') throw new ApiError(401, 'PASSWORD_REQUIRED', '2단계 인증 비밀번호가 필요합니다.')
    loggedIn = true
    return me()
  },
  async password() {
    await delay()
    loggedIn = true
    return me()
  },
  async logout() {
    loggedIn = false
  },
  async me() {
    await delay()
    requireLogin()
    return me()
  },
  async chats(q) {
    await delay()
    requireLogin()
    return q ? chats.filter((c) => c.name.includes(q)) : [...chats]
  },
  async updateAutoReply(chatId, body) {
    await delay()
    requireLogin()
    const chat = findChat(chatId)
    if (body.reply_delay_sec !== undefined && (body.reply_delay_sec < 30 || body.reply_delay_sec > 120)) {
      throw new ApiError(422, 'VALIDATION_ERROR', '대기 시간은 30~120초입니다.')
    }
    const { enabled, ...rest } = body
    // Spec 6.1 / 6.3: turning on opens a session, turning off closes it.
    if (enabled === true && !chat.enabled) {
      const id = nextSessionId++
      ;(sessions[chatId] ??= []).unshift({
        id,
        started_at: new Date().toISOString(),
        ended_at: null,
        message_count: 0,
        auto_reply_count: 0,
      })
      messages[id] = []
      chat.enabled = true
      chat.current_session_id = id
    } else if (enabled === false && chat.enabled) {
      const open = sessions[chatId]?.find((s) => s.id === chat.current_session_id)
      if (open) open.ended_at = new Date().toISOString()
      chat.enabled = false
      chat.current_session_id = null
    }
    Object.assign(chat, rest)
    return { ...chat }
  },
  async sessions(chatId) {
    await delay()
    requireLogin()
    findChat(chatId)
    return sessions[chatId] ?? []
  },
  async sessionMessages(sessionId) {
    await delay()
    requireLogin()
    const list = messages[sessionId]
    if (!list) throw new ApiError(404, 'NOT_FOUND', '세션을 찾을 수 없습니다.')
    return list
  },
  exportUrl: (sessionId, format) => `/api/sessions/${sessionId}/export?format=${format}`,
}
