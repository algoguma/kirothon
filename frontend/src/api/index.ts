// All API calls go through this module. Switch with VITE_USE_MOCK in frontend/.env.local
// (see mockConfig.ts): "true", "false", or a list of groups such as "chats,sessions".
import { mockApi } from './mock'
import { isMocked, MOCK_GROUPS, mockedGroups, type MockGroup } from './mockConfig'
import { realApi, type Api } from './real'

const groupOf: Record<keyof Api, MockGroup> = {
  sendCode: 'auth',
  signIn: 'auth',
  password: 'auth',
  logout: 'auth',
  me: 'auth',
  chats: 'chats',
  updateAutoReply: 'chats',
  sessions: 'sessions',
  sessionMessages: 'sessions',
  exportUrl: 'sessions',
}

export const api = Object.fromEntries(
  (Object.keys(groupOf) as (keyof Api)[]).map((key) => [
    key,
    (isMocked(groupOf[key]) ? mockApi : realApi)[key],
  ]),
) as Api

/** True if any group is mocked (shows the MOCK badge). */
export const useMock = mockedGroups.size > 0
/** Badge text, e.g. "MOCK" or "MOCK: chats, sessions". */
export const mockLabel =
  mockedGroups.size === MOCK_GROUPS.length ? 'MOCK' : `MOCK: ${[...mockedGroups].join(', ')}`

export { isMocked } from './mockConfig'
export { ApiError } from './http'
export type * from './types'
