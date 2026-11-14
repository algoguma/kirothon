import { ApiError } from './http'

/** User-facing Korean message for any thrown error. */
export function errorMessage(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.code === 'FLOOD_WAIT' && e.retryAfterSec) {
      return `요청이 너무 많습니다. ${e.retryAfterSec}초 뒤에 다시 시도해 주세요.`
    }
    return e.message
  }
  return '알 수 없는 오류가 발생했습니다. 잠시 뒤 다시 시도해 주세요.'
}
