import { createContext, type ReactNode, useEffect, useMemo, useState } from 'react'

export type Theme = 'light' | 'dark' | 'system'

interface ThemeContextValue {
  theme: Theme
  resolvedTheme: 'light' | 'dark'
  setTheme: (t: Theme) => void
}

// eslint-disable-next-line react-refresh/only-export-components
export const ThemeContext = createContext<ThemeContextValue | null>(null)

const STORAGE_KEY = 'halite-theme'

function readStored(): Theme {
  if (typeof localStorage === 'undefined') return 'system'
  const v = localStorage.getItem(STORAGE_KEY)
  if (v === 'light' || v === 'dark' || v === 'system') return v
  return 'system'
}

function systemPrefersDark(): boolean {
  if (typeof window === 'undefined' || !window.matchMedia) return false
  return window.matchMedia('(prefers-color-scheme: dark)').matches
}

function resolve(theme: Theme, sysDark: boolean): 'light' | 'dark' {
  if (theme === 'system') return sysDark ? 'dark' : 'light'
  return theme
}

function applyToDocument(resolved: 'light' | 'dark') {
  if (typeof document === 'undefined') return
  const root = document.documentElement
  if (resolved === 'dark') root.classList.add('dark')
  else root.classList.remove('dark')
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(() => readStored())
  // Track system preference separately so we can update it from the media query listener
  const [sysDark, setSysDark] = useState<boolean>(() => systemPrefersDark())

  const resolved = useMemo(() => resolve(theme, sysDark), [theme, sysDark])

  // Persist to localStorage and apply to document whenever resolved changes
  useEffect(() => {
    applyToDocument(resolved)
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(STORAGE_KEY, theme)
    }
  }, [resolved, theme])

  // Listen for system theme changes when in 'system' mode
  useEffect(() => {
    if (theme !== 'system' || typeof window === 'undefined' || !window.matchMedia) return
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const handler = () => setSysDark(mq.matches)
    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [theme])

  return (
    <ThemeContext.Provider value={{ theme, resolvedTheme: resolved, setTheme: setThemeState }}>
      {children}
    </ThemeContext.Provider>
  )
}
