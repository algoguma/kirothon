// All API calls go through this module. Switch with VITE_USE_MOCK in frontend/.env.local.
import { mockApi } from './mock'
import { realApi } from './real'

export const useMock = import.meta.env.VITE_USE_MOCK !== 'false'
export const api = useMock ? mockApi : realApi

export { ApiError } from './http'
export type * from './types'
