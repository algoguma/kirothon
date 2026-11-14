// The mascot in webtoon style: ink outline and a slight smile.
const BODY =
  'M50 8C78 8 92 30 92 58V92C92 104 84 110 76 106C72 114 62 116 56 108C50 116 38 116 34 106C26 112 16 108 16 98C10 100 4 96 6 90C12 86 14 80 14 72V46C14 24 28 8 50 8Z'
const INK = '#2a1830'

export function CoverGhost({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 4 100 116" aria-hidden="true">
      <defs>
        <linearGradient id="ghost-shade" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0.55" stopColor="#ffffff" />
          <stop offset="1" stopColor="#e4dcef" />
        </linearGradient>
      </defs>
      <path d={BODY} fill="url(#ghost-shade)" stroke={INK} strokeWidth="2.4" strokeLinejoin="round" />
      <g className="ghost-eyes">
        <ellipse cx="52" cy="40" rx="5.5" ry="8" fill="#111" />
        <ellipse cx="70" cy="40" rx="5.5" ry="8" fill="#111" />
      </g>
      <path d="M55 54Q61 58 67 54" fill="none" stroke={INK} strokeWidth="2" strokeLinecap="round" />
    </svg>
  )
}
