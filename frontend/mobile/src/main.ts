import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import './styles/main.css'

// Initialize theme immediately (before any render) to prevent flash of wrong colors
const initialTheme = localStorage.getItem('theme') as 'dark' | 'light' | 'glacier' | null
if (initialTheme && ['dark', 'light', 'glacier'].includes(initialTheme)) {
  document.documentElement.setAttribute('data-theme', initialTheme)
} else if (window.matchMedia?.('(prefers-color-scheme: light)').matches) {
  document.documentElement.setAttribute('data-theme', 'light')
} else {
  document.documentElement.setAttribute('data-theme', 'dark')
}

const app = createApp(App)
app.use(router)
app.mount('#app')
