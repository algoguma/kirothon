// In-memory mock that follows spec 7. Extend freely while the backend is not ready.
import { ApiError, type DownloadedFile } from './http'
import { isMocked } from './mockConfig'
import type { Api } from './real'
import type { AutoReplySession, Chat, ExportFormat, MeResponse, SessionMessage } from './types'
import { kstParts } from '../format'

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
    analysis_status: 'ready',
    analysis_started_at: null,
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
    analysis_status: null,
    analysis_started_at: null,
  },
]

// Sessions newest first (spec 7.4). Counts are computed from `messages`.
const sessions: Record<number, Omit<AutoReplySession, 'message_count' | 'auto_reply_count'>[]> = {
  123456789: [
    { id: 7, started_at: '2026-11-14T01:00:00Z', ended_at: null },
    { id: 5, started_at: '2026-11-13T09:00:00Z', ended_at: '2026-11-13T10:30:00Z' },
  ],
  987654321: [{ id: 3, started_at: '2026-11-13T11:40:00Z', ended_at: '2026-11-13T12:10:00Z' }],
}

let nextSessionId = 8

const m = (
  message_id: number,
  sender_name: string,
  text: string,
  date: string,
  is_outgoing = false,
  is_auto_reply = false,
): SessionMessage => ({ message_id, sender_name, text, date, is_outgoing, is_auto_reply })

const messages: Record<number, SessionMessage[]> = {
  7: [
    m(555, '김철수', '안녕', '2026-11-14T01:01:00Z'),
    m(556, '김철수', '지금 통화 돼?', '2026-11-14T01:01:10Z'),
    m(557, '나', '지금 회의 중이라 끝나고 연락드릴게요.', '2026-11-14T01:01:45Z', true, true),
  ],
  5: [
    m(501, '김철수', '내일 점심 같이 먹을래?', '2026-11-13T09:05:00Z'),
    m(502, '나', '좋아요! 시간은 확인하고 다시 말씀드릴게요.', '2026-11-13T09:05:40Z', true, true),
    m(503, '김철수', '[사진] 여기 어때?', '2026-11-13T09:20:00Z'),
    m(504, '나', '오 좋아 보인다. 12시 반 괜찮아', '2026-11-13T09:22:00Z', true),
    m(505, '김철수', 'ㅇㅋ', '2026-11-13T09:22:30Z'),
  ],
  3: [
    m(301, '이영희', '자료 보냈어요', '2026-11-13T11:50:00Z'),
    m(302, '나', '확인하고 연락드릴게요.', '2026-11-13T11:51:00Z', true, true),
  ],
}

function withCounts(s: (typeof sessions)[number][number]): AutoReplySession {
  const list = messages[s.id] ?? []
  return { ...s, message_count: list.length, auto_reply_count: list.filter((x) => x.is_auto_reply).length }
}

function findSession(sessionId: number) {
  for (const [chatId, list] of Object.entries(sessions)) {
    const session = list.find((s) => s.id === sessionId)
    if (session) return { session, chat: findChat(Number(chatId)) }
  }
  throw new ApiError(404, 'NOT_FOUND', '세션을 찾을 수 없습니다.')
}

// Spec 6.4 export formats. Files use KST.
function buildExport(sessionId: number, format: ExportFormat): DownloadedFile {
  const { session, chat } = findSession(sessionId)
  const list = messages[sessionId] ?? []
  const start = kstParts(session.started_at)
  const end = kstParts(session.ended_at ?? new Date().toISOString())
  const filename = `${chat.name}_${start.date}_${start.time.replace(':', '')}-${end.time.replace(':', '')}.${format}`

  if (format === 'json') {
    const body = {
      chat: { chat_id: chat.chat_id, name: chat.name },
      session: { id: session.id, started_at: start.iso, ended_at: session.ended_at ? end.iso : null },
      messages: list.map((x) => ({ ...x, date: kstParts(x.date).iso })),
    }
    return { filename, blob: new Blob([JSON.stringify(body, null, 2)], { type: 'application/json' }) }
  }
  if (format === 'csv') {
    const cell = (v: string) => `"${v.replace(/"/g, '""')}"`
    const rows = list.map((x) => {
      const p = kstParts(x.date)
      return [`${p.date} ${p.time}`, cell(x.sender_name), cell(x.text), String(x.is_auto_reply)].join(',')
    })
    const csv = ['date,sender_name,text,is_auto_reply', ...rows].join('\r\n')
    return { filename, blob: new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8' }) }
  }
  const lines = list.map((x) => {
    const p = kstParts(x.date)
    const who = x.is_auto_reply ? '나 (AI)' : x.sender_name
    return `[${p.date} ${p.time}] ${who}: ${x.text}`
  })
  return { filename, blob: new Blob([lines.join('\n') + '\n'], { type: 'text/plain;charset=utf-8' }) }
}

// Mock analysis takes this long after turning on (real one: 30s~2min).
const MOCK_ANALYSIS_MS = 20_000

/** Finish mock analyses whose time is up. */
function settleAnalysis(): void {
  for (const chat of chats) {
    if (chat.analysis_status === 'running' && chat.analysis_started_at) {
      if (Date.now() - new Date(chat.analysis_started_at).getTime() >= MOCK_ANALYSIS_MS) {
        chat.analysis_status = 'ready'
        chat.analysis_started_at = null
      }
    }
  }
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
    settleAnalysis()
    return (q ? chats.filter((c) => c.name.includes(q)) : chats).map((c) => ({ ...c }))
  },
  async updateAutoReply(chatId, body) {
    await delay()
    requireLogin()
    const chat = findChat(chatId)
    if (body.reply_delay_sec !== undefined && (body.reply_delay_sec < 5 || body.reply_delay_sec > 120)) {
      throw new ApiError(422, 'VALIDATION_ERROR', '대기 시간은 5~120초입니다.')
    }
    const { enabled, ...rest } = body
    // Spec 6.1 / 6.3: turning on opens a session, turning off closes it.
    if (enabled === true && !chat.enabled) {
      const id = nextSessionId++
      ;(sessions[chatId] ??= []).unshift({
        id,
        started_at: new Date().toISOString(),
        ended_at: null,
      })
      messages[id] = []
      chat.enabled = true
      chat.current_session_id = id
      chat.analysis_status = 'running'
      chat.analysis_started_at = new Date().toISOString()
    } else if (enabled === false && chat.enabled) {
      const open = sessions[chatId]?.find((s) => s.id === chat.current_session_id)
      if (open) open.ended_at = new Date().toISOString()
      chat.enabled = false
      chat.current_session_id = null
      chat.analysis_status = null
      chat.analysis_started_at = null
    }
    Object.assign(chat, rest)
    settleAnalysis()
    return { ...chat }
  },
  async sessions(chatId) {
    await delay()
    requireLogin()
    findChat(chatId)
    return (sessions[chatId] ?? []).map(withCounts)
  },
  async sessionMessages(sessionId) {
    await delay()
    requireLogin()
    findSession(sessionId)
    return messages[sessionId] ?? []
  },
  async exportSession(sessionId, format) {
    await delay()
    requireLogin()
    return buildExport(sessionId, format)
  },
}
