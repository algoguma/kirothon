import { createContext, useContext } from 'react'
import type { MeResponse } from '../api'

export type AuthState =
  | { status: 'loading' }
  | { status: 'anonymous' }
  | { status: 'authenticated'; me: MeResponse }

export interface AuthContextValue {
  state: AuthState
  /** Set after sign-in / setup, or null after logout. */
  setMe: (me: MeResponse | null) => void
}

export const AuthContext = createContext<AuthContextValue | null>(null)

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
