import { CoverGhost } from './CoverGhost'

// Webtoon-cover style title art, an homage to "분신으로 자동사냥". Drawn with SVG/CSS only.
export function CoverPoster() {
  return (
    <figure className="poster" role="img" aria-label="분신으로 자동답장">
      <CoverGhost className="poster-ghost" />

      <div className="poster-title" aria-hidden="true">
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
    </figure>
  )
}
