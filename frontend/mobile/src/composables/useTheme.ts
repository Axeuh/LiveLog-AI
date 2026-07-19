import { ref, watch } from 'vue'

export type ThemeName = 'dark' | 'light' | 'glacier'

const STORAGE_KEY = 'theme'

export function useTheme() {
  // Initialize: check localStorage first, then system preference
  function getInitialTheme(): ThemeName {
    const stored = localStorage.getItem(STORAGE_KEY) as ThemeName | null
    if (stored && ['dark', 'light', 'glacier'].includes(stored)) {
      return stored
    }
    if (window.matchMedia?.('(prefers-color-scheme: light)').matches) {
      return 'light'
    }
    return 'dark'
  }

  const theme = ref<ThemeName>(getInitialTheme())
  const availableThemes: ThemeName[] = ['dark', 'light', 'glacier']

  function applyTheme(t: ThemeName) {
    document.documentElement.setAttribute('data-theme', t)
  }

  function setTheme(t: ThemeName) {
    theme.value = t
    localStorage.setItem(STORAGE_KEY, t)
    applyTheme(t)
  }

  // Apply on first load
  applyTheme(theme.value)

  // React to changes
  watch(theme, (t) => {
    applyTheme(t)
  })

  // Listen for system preference changes
  const mediaQuery = window.matchMedia('(prefers-color-scheme: light)')
  mediaQuery.addEventListener('change', (e) => {
    // Only auto-follow if user hasn't manually set a preference
    if (!localStorage.getItem(STORAGE_KEY)) {
      theme.value = e.matches ? 'light' : 'dark'
    }
  })

  return { theme, setTheme, availableThemes }
}
