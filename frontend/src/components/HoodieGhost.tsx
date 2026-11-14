// The mascot dressed as a webtoon hero: red hoodie, ink outline, slight smile.
const BODY =
  'M50 8C78 8 92 30 92 58V92C92 104 84 110 76 106C72 114 62 116 56 108C50 116 38 116 34 106C26 112 16 108 16 98C10 100 4 96 6 90C12 86 14 80 14 72V46C14 24 28 8 50 8Z'
const INK = '#2a1830'

export function HoodieGhost({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="-4 -6 108 128" aria-hidden="true">
      <defs>
        <clipPath id="hoodie-clip">
          <rect x="-10" y="70" width="130" height="60" />
        </clipPath>
        <linearGradient id="hoodie-red" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#ef6a4c" />
          <stop offset="1" stopColor="#b8402c" />
        </linearGradient>
        <linearGradient id="ghost-shade" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0.55" stopColor="#ffffff" />
          <stop offset="1" stopColor="#e4dcef" />
        </linearGradient>
      </defs>

      {/* hood behind the head */}
      <path
        d="M2 74C-2 30 20 -2 52 -2C84 -2 104 28 100 74L90 70C92 36 76 8 50 8C26 8 10 34 12 70Z"
        fill="url(#hoodie-red)"
        stroke={INK}
        strokeWidth="2.2"
        strokeLinejoin="round"
      />
      {/* ghost body */}
      <path d={BODY} fill="url(#ghost-shade)" stroke={INK} strokeWidth="2.4" strokeLinejoin="round" />
      {/* hoodie front: same silhouette as the body, clipped below the neckline */}
      <path d={BODY} fill="url(#hoodie-red)" clipPath="url(#hoodie-clip)" />
      <path d={BODY} fill="none" stroke={INK} strokeWidth="2.4" strokeLinejoin="round" />
      <path d="M13 70C30 80 74 80 92 70" fill="none" stroke={INK} strokeWidth="2.2" strokeLinecap="round" />
      {/* drawstrings */}
      <path d="M42 77L40 95M62 77L64 95" stroke="#f6efe4" strokeWidth="2.2" strokeLinecap="round" />
      <circle cx="40" cy="96" r="2.2" fill="#f6efe4" stroke={INK} strokeWidth="1" />
      <circle cx="64" cy="96" r="2.2" fill="#f6efe4" stroke={INK} strokeWidth="1" />
      {/* face */}
      <g className="ghost-eyes">
        <ellipse cx="52" cy="40" rx="5.5" ry="8" fill="#111" />
        <ellipse cx="70" cy="40" rx="5.5" ry="8" fill="#111" />
        <circle cx="53.8" cy="36.5" r="1.7" fill="#fff" />
        <circle cx="71.8" cy="36.5" r="1.7" fill="#fff" />
      </g>
      <path d="M55 54Q61 58 67 54" fill="none" stroke={INK} strokeWidth="2" strokeLinecap="round" />
    </svg>
  )
}
