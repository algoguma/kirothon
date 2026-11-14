import { useEffect, useState } from 'react'

function elapsed(fromIso: string | null, now: number): string {
  if (!fromIso) return ''
  const sec = Math.max(0, Math.floor((now - new Date(fromIso).getTime()) / 1000))
  return `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, '0')}`
}

// Shown while analysis_status is "running". Length is unknown, so the bar is indeterminate.
export function AnalysisProgress({ startedAt }: { startedAt: string | null }) {
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(timer)
  }, [])

  const time = elapsed(startedAt, now)
  return (
    <div className="analysis" role="status">
      <div className="analysis-bar" aria-hidden="true">
        <span />
      </div>
      <span className="analysis-text">
        분신이 대화를 읽고 말투·기억을 분석하는 중 (보통 30초~2분){time && ` · ${time}`}
      </span>
      <span className="analysis-hint">분석이 끝날 때까지 들어온 메시지는 답장을 기다립니다.</span>
    </div>
  )
}
