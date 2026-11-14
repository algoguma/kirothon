// API timestamps are UTC; screens and export files show KST (spec 7 common rules).
const kst = new Intl.DateTimeFormat('ko-KR', {
  timeZone: 'Asia/Seoul',
  month: 'numeric',
  day: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
})

export function formatKst(iso: string | null): string {
  return iso ? kst.format(new Date(iso)) : '-'
}

const kstTime = new Intl.DateTimeFormat('ko-KR', {
  timeZone: 'Asia/Seoul',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
})

/** "10:23" in KST. */
export function formatKstTime(iso: string): string {
  return kstTime.format(new Date(iso))
}

const KST_OFFSET_MS = 9 * 60 * 60 * 1000

/** KST pieces for export files: { date: "2026-11-14", time: "10:23", iso: "2026-11-14T10:23:45+09:00" }. */
export function kstParts(iso: string): { date: string; time: string; iso: string } {
  const shifted = new Date(new Date(iso).getTime() + KST_OFFSET_MS).toISOString() // "...Z" but KST clock
  const date = shifted.slice(0, 10)
  const time = shifted.slice(11, 16)
  return { date, time, iso: `${shifted.slice(0, 19)}+09:00` }
}
