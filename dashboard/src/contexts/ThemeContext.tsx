'use client'

import { createContext, useContext, useEffect, useState } from 'react'

type Theme = 'dark' | 'light'

interface ThemeContextValue {
  theme: Theme
  toggleTheme: () => void
}

// The app opens in the soft light theme that matches the marketing site. The
// key was renamed when that became the default: browsers that had stored
// "dark" under the old one start on the new look, and a visitor's own choice
// from here on still persists.
const STORAGE_KEY = 'tw-theme-v2'

const ThemeContext = createContext<ThemeContextValue>({
  theme: 'light',
  toggleTheme: () => {},
})

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setTheme] = useState<Theme>('light')

  // On mount, read persisted preference (default: light)
  useEffect(() => {
    let stored: Theme | null = null
    try {
      stored = localStorage.getItem(STORAGE_KEY) as Theme | null
    } catch {
      // Storage blocked: fall back to the default.
    }
    const preferred = stored === 'dark' ? 'dark' : 'light'
    setTheme(preferred)
    applyTheme(preferred)
  }, [])

  function applyTheme(t: Theme) {
    const root = document.documentElement
    if (t === 'dark') {
      root.classList.add('dark')
    } else {
      root.classList.remove('dark')
    }
  }

  function toggleTheme() {
    setTheme(prev => {
      const next: Theme = prev === 'dark' ? 'light' : 'dark'
      try {
        localStorage.setItem(STORAGE_KEY, next)
      } catch {
        // Storage blocked: the choice lasts for this page only.
      }
      applyTheme(next)
      return next
    })
  }

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme() {
  return useContext(ThemeContext)
}
