// In-memory mock that follows spec 7. Extend freely while the backend is not ready.
import { ApiError } from './http'
import type { Api } from './real'
import type { AutoReplySession, Chat, LlmSettings, MeResponse, SessionMessage } from './types'

const delay = (ms = 200) => new Promise((r) => setTimeout(r, ms))

let loggedIn = false
let llm: LlmSettings = { model: 'mock-model', api_key_set: false, api_key_hint: null, verified_at: null }
const me = (): MeResponse => ({ user: { id: 1, display_name: '홍길동' }, llm_configured: llm.api_key_set })

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

const messages: Record<number, SessionMessage[]> = {
  7: [
    { message_id: 555, sender_name: '김철수', text: '안녕', date: '2026-11-14T01:01:00Z', is_outgoing: false, is_auto_reply: false },
    { message_id: 556, sender_name: '김철수', text: '지금 통화 돼?', date: '2026-11-14T01:01:10Z', is_outgoing: false, is_auto_reply: false },
    { message_id: 557, sender_name: '나', text: '지금 회의 중이라 끝나고 연락드릴게요.', date: '2026-11-14T01:01:45Z', is_outgoing: true, is_auto_reply: true },
  ],
}

function requireLogin() {
  if (!loggedIn) throw new ApiError(401, 'UNAUTHORIZED', '로그인이 필요합니다.')
}

function findChat(chatId: number): Chat {
  const chat = chats.find((c) => c.chat_id === chatId)
  if (!chat) throw new ApiError(404, 'NOT_FOUND', '채팅방을 찾을 수 없습니다.')
  return chat
}

export const mockApi: Api = {
  async sendCode() {
    await delay()
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
  async getLlm() {
    requireLogin()
    return llm
  },
  async putLlm(apiKey) {
    await delay(500)
    requireLogin()
    if (!apiKey) throw new ApiError(400, 'LLM_TEST_FAILED', 'API 키 확인에 실패했습니다.')
    llm = { ...llm, api_key_set: true, api_key_hint: `...${apiKey.slice(-4)}`, verified_at: new Date().toISOString() }
    return llm
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
    Object.assign(chat, body)
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
