// API timestamps are UTC; screens show KST (spec 7 common rules).
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
