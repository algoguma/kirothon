// Light/dark theme. Default follows the OS; a click stores an explicit choice.
// index.html applies the stored choice before first paint (same key and attribute).
export type Theme = 'light' | 'dark'

const STORAGE_KEY = 'theme'
const media = window.matchMedia('(prefers-color-scheme: dark)')

function stored(): Theme | null {
  try {
    const value = localStorage.getItem(STORAGE_KEY)
    return value === 'light' || value === 'dark' ? value : null
  } catch {
    return null // storage blocked (private mode etc.)
  }
}

/** The theme on screen right now. */
export function currentTheme(): Theme {
  return stored() ?? (media.matches ? 'dark' : 'light')
}

export function setTheme(theme: Theme): void {
  document.documentElement.dataset.theme = theme
  try {
    localStorage.setItem(STORAGE_KEY, theme)
  } catch {
    /* still applied for this page view */
  }
}

/** Notify when the OS theme changes (only matters while no explicit choice is stored). */
export function onSystemThemeChange(callback: () => void): () => void {
  media.addEventListener('change', callback)
  return () => media.removeEventListener('change', callback)
}
