// API types from docs/auto-reply-spec.md section 7. Update the spec first, then this file.
// All timestamps are ISO 8601 UTC strings (e.g. "2026-11-14T01:23:45Z").

export type IsoDate = string

export type ErrorCode =
  | 'UNAUTHORIZED'
  | 'INVALID_API_CREDENTIALS'
  | 'INVALID_CODE'
  | 'PASSWORD_REQUIRED'
  | 'INVALID_PASSWORD'
  | 'FLOOD_WAIT'
  | 'VALIDATION_ERROR'
  | 'NOT_FOUND'

export interface ErrorBody {
  error: { code: ErrorCode; message: string; retry_after_sec?: number }
}

// 7.1 Auth
export interface SendCodeRequest {
  api_id: number
  api_hash: string
  phone: string
}
export interface SendCodeResponse {
  login_id: string
}
export interface SignInRequest {
  login_id: string
  code: string
}
export interface PasswordRequest {
  login_id: string
  password: string
}
export interface User {
  id: number
  display_name: string
}
// 7.1 sign-in / password response and 7.2 GET /api/me
export interface MeResponse {
  user: User
}

// 7.3 Chats
export interface Chat {
  chat_id: number
  name: string
  last_message_at: IsoDate | null
  enabled: boolean
  reply_delay_sec: number // 5..120
  ai_instructions: string
  fallback_text: string | null
  current_session_id: number | null
  last_error: string | null
}
export type AutoReplyUpdate = Partial<
  Pick<Chat, 'enabled' | 'reply_delay_sec' | 'ai_instructions' | 'fallback_text'>
>

// 7.4 Sessions
export interface AutoReplySession {
  id: number
  started_at: IsoDate
  ended_at: IsoDate | null
  message_count: number
  auto_reply_count: number
}
export interface SessionMessage {
  message_id: number
  sender_name: string
  text: string
  date: IsoDate
  is_outgoing: boolean
  is_auto_reply: boolean
}
export type ExportFormat = 'json' | 'csv' | 'txt'
