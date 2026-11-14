import { HoodieGhost } from './HoodieGhost'

// Sparkle positions (% of the poster), mostly in the top-right like light dust.
const SPARKLES = [
  [72, 6, 1.0], [80, 12, 0.6], [88, 8, 0.8], [76, 20, 0.5], [92, 22, 0.7], [84, 30, 0.4],
  [68, 14, 0.4], [90, 38, 0.5], [60, 8, 0.5], [95, 14, 0.4], [70, 28, 0.3], [86, 46, 0.35],
  [12, 30, 0.35], [8, 48, 0.3], [18, 18, 0.25],
] as const

// Webtoon-cover style hero, an homage to "분신으로 자동사냥". Drawn with SVG/CSS only.
export function CoverPoster() {
  return (
    <figure className="poster" aria-label="분신으로 자동답장 표지">
      <div className="poster-rays" />
      <span className="poster-label">Kirothon / 텔레그램 AI 자동답장</span>
      {SPARKLES.map(([x, y, s], i) => (
        <span
          key={i}
          className="sparkle"
          style={{ left: `${x}%`, top: `${y}%`, scale: String(s), animationDelay: `${(i % 5) * 0.6}s` }}
        />
      ))}

      <HoodieGhost className="poster-ghost" />

      <div className="poster-title">
        <svg className="bolt bolt-left" viewBox="0 0 60 40" aria-hidden="true">
          <path d="M58 6L30 14L38 20L4 34L26 18L18 14Z" />
        </svg>
        <svg className="bolt bolt-right" viewBox="0 0 60 40" aria-hidden="true">
          <path d="M2 30L28 22L22 16L56 4L34 20L42 24Z" />
        </svg>
        <span className="title-line title-ice">분신으로</span>
        <span className="title-line title-gold">
          자동답장
          <svg className="title-plane" viewBox="0 0 24 24" aria-hidden="true">
            <path d="M2 11L22 2L15 22L11 13Z M11 13L22 2" />
          </svg>
        </span>
      </div>

      <figcaption className="poster-credits">
        <span>
          오마주 <b>분신으로 자동사냥</b>
        </span>
        <span>
          기획 <b>Kirothon 팀</b> 작화 <b>Kiro</b>
        </span>
      </figcaption>
      <span className="poster-emblem">AI</span>
    </figure>
  )
}
