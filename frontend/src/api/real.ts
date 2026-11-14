import { request } from './http'
import type {
  AutoReplySession,
  AutoReplyUpdate,
  Chat,
  ExportFormat,
  LlmSettings,
  MeResponse,
  SendCodeRequest,
  SendCodeResponse,
  SessionMessage,
} from './types'

export const realApi = {
  sendCode: (body: SendCodeRequest) => request<SendCodeResponse>('POST', '/auth/send-code', body),
  signIn: (login_id: string, code: string) =>
    request<MeResponse>('POST', '/auth/sign-in', { login_id, code }),
  password: (login_id: string, password: string) =>
    request<MeResponse>('POST', '/auth/password', { login_id, password }),
  logout: () => request<void>('POST', '/auth/logout'),

  me: () => request<MeResponse>('GET', '/me'),
  getLlm: () => request<LlmSettings>('GET', '/me/llm'),
  putLlm: (api_key: string) => request<LlmSettings>('PUT', '/me/llm', { api_key }),

  chats: (q?: string) =>
    request<Chat[]>('GET', `/chats${q ? `?q=${encodeURIComponent(q)}` : ''}`),
  updateAutoReply: (chatId: number, body: AutoReplyUpdate) =>
    request<Chat>('PUT', `/chats/${chatId}/auto-reply`, body),

  sessions: (chatId: number) => request<AutoReplySession[]>('GET', `/chats/${chatId}/sessions`),
  sessionMessages: (sessionId: number) =>
    request<SessionMessage[]>('GET', `/sessions/${sessionId}/messages`),
  exportUrl: (sessionId: number, format: ExportFormat) =>
    `/api/sessions/${sessionId}/export?format=${format}`,
}

export type Api = typeof realApi
