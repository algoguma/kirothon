import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api, ApiError, type MeResponse } from '../api'
import { AuthContext, type AuthState } from './context'

// Checks GET /api/me once on app start (spec 8). 401 means "not logged in".
export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ status: 'loading' })

  useEffect(() => {
    let cancelled = false
    api
      .me()
      .then((me) => !cancelled && setState({ status: 'authenticated', me }))
      .catch((e: unknown) => {
        if (cancelled) return
        if (!(e instanceof ApiError && e.status === 401)) console.error(e)
        setState({ status: 'anonymous' })
      })
    return () => {
      cancelled = true
    }
  }, [])

  const setMe = useCallback((me: MeResponse | null) => {
    setState(me ? { status: 'authenticated', me } : { status: 'anonymous' })
  }, [])

  const value = useMemo(() => ({ state, setMe }), [state, setMe])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
