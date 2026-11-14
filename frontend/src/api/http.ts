import type { ErrorBody, ErrorCode } from './types'

export class ApiError extends Error {
  readonly status: number
  readonly code: ErrorCode | 'UNKNOWN'
  readonly retryAfterSec?: number

  constructor(status: number, code: ErrorCode | 'UNKNOWN', message: string, retryAfterSec?: number) {
    super(message)
    this.status = status
    this.code = code
    this.retryAfterSec = retryAfterSec
  }
}

export async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`/api${path}`, {
    method,
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (res.status === 204) return undefined as T
  const data: unknown = await res.json().catch(() => null)
  if (!res.ok) {
    const err = (data as ErrorBody | null)?.error
    throw new ApiError(res.status, err?.code ?? 'UNKNOWN', err?.message ?? res.statusText, err?.retry_after_sec)
  }
  return data as T
}

export interface DownloadedFile {
  blob: Blob
  filename: string
}

/** GET a file. The filename comes from Content-Disposition (RFC 6266 `filename*` first). */
export async function download(path: string, fallbackName: string): Promise<DownloadedFile> {
  const res = await fetch(`/api${path}`)
  if (!res.ok) {
    const data = (await res.json().catch(() => null)) as ErrorBody | null
    const err = data?.error
    throw new ApiError(res.status, err?.code ?? 'UNKNOWN', err?.message ?? res.statusText, err?.retry_after_sec)
  }
  return { blob: await res.blob(), filename: filenameFrom(res.headers.get('Content-Disposition')) ?? fallbackName }
}

function filenameFrom(header: string | null): string | null {
  if (!header) return null
  const star = /filename\*\s*=\s*(?:UTF-8|utf-8)''([^;]+)/.exec(header)
  if (star) {
    try {
      return decodeURIComponent(star[1].trim())
    } catch {
      /* fall through to plain filename */
    }
  }
  const plain = /filename\s*=\s*"([^"]+)"|filename\s*=\s*([^;]+)/.exec(header)
  return plain ? (plain[1] ?? plain[2]).trim() : null
}

/** Save a downloaded file through a temporary <a download>. */
export function saveFile({ blob, filename }: DownloadedFile): void {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
