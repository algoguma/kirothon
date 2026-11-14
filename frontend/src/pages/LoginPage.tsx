import { useState, type FormEvent } from 'react'
import { Navigate } from 'react-router'
import { api, ApiError, isMocked, type MeResponse } from '../api'
import { errorMessage } from '../api/errors'
import { useAuth } from '../auth/context'

type Step = 'phone' | 'code' | 'password'

/** "010-1234-5678" -> "+821012345678". Keeps numbers that already start with "+". */
function normalizePhone(input: string): string {
  const trimmed = input.trim()
  const digits = trimmed.replace(/\D/g, '')
  if (trimmed.startsWith('+')) return `+${digits}`
  if (digits.startsWith('0')) return `+82${digits.slice(1)}`
  return `+${digits}`
}

// Spec 8 /login: phone -> code -> (optional) 2FA password on one page.
export default function LoginPage() {
  const { state, setMe } = useAuth()

  const [step, setStep] = useState<Step>('phone')
  const [apiId, setApiId] = useState('')
  const [apiHash, setApiHash] = useState('')
  const [phone, setPhone] = useState('')
  const [loginId, setLoginId] = useState('')
  const [code, setCode] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  // Also handles the redirect right after a successful login (setMe re-renders this page).
  if (state.status === 'authenticated') {
    return <Navigate to="/chats" replace />
  }

  const done = (me: MeResponse) => setMe(me)

  const run = async (action: () => Promise<void>) => {
    setBusy(true)
    setError(null)
    try {
      await action()
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  const submitPhone = (e: FormEvent) => {
    e.preventDefault()
    void run(async () => {
      const res = await api.sendCode({
        api_id: Number(apiId.trim()),
        api_hash: apiHash.trim(),
        phone: normalizePhone(phone),
      })
      setLoginId(res.login_id)
      setCode('')
      setStep('code')
    })
  }

  const submitCode = (e: FormEvent) => {
    e.preventDefault()
    void run(async () => {
      try {
        done(await api.signIn(loginId, code.trim()))
      } catch (err) {
        if (err instanceof ApiError && err.code === 'PASSWORD_REQUIRED') {
          setStep('password')
          return
        }
        throw err
      }
    })
  }

  const submitPassword = (e: FormEvent) => {
    e.preventDefault()
    void run(async () => done(await api.password(loginId, password)))
  }

  const restart = () => {
    setStep('phone')
    setPassword('')
    setError(null)
  }

  return (
    <main className="card">
      <img className="card-logo" src="/favicon.svg" alt="" width={64} height={64} />
      <h1>텔레그램 로그인</h1>

      {step === 'phone' && (
        <form onSubmit={submitPhone}>
          <p className="muted small">
            <a href="https://my.telegram.org/apps" target="_blank" rel="noreferrer">
              my.telegram.org
            </a>
            {' '}→ API development tools에서 앱을 만들고 api_id와 api_hash를 받아 오세요. 로그인할
            때마다 입력합니다.
          </p>
          <label>
            api_id
            <input
              inputMode="numeric"
              autoFocus
              required
              pattern="[0-9]+"
              placeholder="1234567"
              value={apiId}
              onChange={(e) => setApiId(e.target.value)}
            />
          </label>
          <label>
            api_hash
            <input
              type="password"
              autoComplete="off"
              required
              pattern="[0-9a-fA-F]{32}"
              title="32자리 16진수"
              value={apiHash}
              onChange={(e) => setApiHash(e.target.value)}
            />
          </label>
          <label>
            전화번호
            <input
              type="tel"
              required
              placeholder="010-1234-5678"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
            />
          </label>
          <button disabled={busy || !apiId.trim() || !apiHash.trim() || !phone.trim()}>
            인증 코드 받기
          </button>
        </form>
      )}

      {step === 'code' && (
        <form onSubmit={submitCode}>
          <p className="muted">텔레그램 앱으로 받은 코드를 입력하세요. ({normalizePhone(phone)})</p>
          <label>
            인증 코드
            <input
              inputMode="numeric"
              autoComplete="one-time-code"
              autoFocus
              required
              value={code}
              onChange={(e) => setCode(e.target.value)}
            />
          </label>
          <button disabled={busy || !code.trim()}>로그인</button>
          <button type="button" className="link" onClick={restart} disabled={busy}>
            전화번호 다시 입력
          </button>
        </form>
      )}

      {step === 'password' && (
        <form onSubmit={submitPassword}>
          <p className="muted">2단계 인증이 켜져 있습니다. 비밀번호를 입력하세요.</p>
          <label>
            2단계 인증 비밀번호
            <input
              type="password"
              autoComplete="current-password"
              autoFocus
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          <button disabled={busy || !password}>확인</button>
          <button type="button" className="link" onClick={restart} disabled={busy}>
            처음부터 다시
          </button>
        </form>
      )}

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {isMocked('auth') && (
        <p className="muted small">
          MOCK: api_hash는 32자리 16진수면 통과, 코드는 아무거나 통과, 00000이면 2단계 인증 화면
        </p>
      )}
    </main>
  )
}
