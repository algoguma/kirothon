// Mascot ("분신" ghost). Same shape as public/favicon.svg, without the background.
export function Ghost({ size = 160, animated = false }: { size?: number; animated?: boolean }) {
  return (
    <svg
      className={animated ? 'ghost ghost-animated' : 'ghost'}
      viewBox="0 0 100 120"
      width={size}
      height={(size * 120) / 100}
      aria-hidden="true"
    >
      <path
        fill="#fafafa"
        d="M50 8C78 8 92 30 92 58V92C92 104 84 110 76 106C72 114 62 116 56 108C50 116 38 116 34 106C26 112 16 108 16 98C10 100 4 96 6 90C12 86 14 80 14 72V46C14 24 28 8 50 8Z"
      />
      <g className="ghost-eyes">
        <ellipse cx="52" cy="40" rx="5.5" ry="8" fill="#111" />
        <ellipse cx="70" cy="40" rx="5.5" ry="8" fill="#111" />
      </g>
    </svg>
  )
}
