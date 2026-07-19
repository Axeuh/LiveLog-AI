<template>
  <nav class="bottom-nav">
    <router-link
      v-for="tab in tabs"
      :key="tab.route"
      :to="tab.route"
      class="nav-item"
      :class="{ active: isActive(tab.route) }"
    >
      <span class="nav-icon">
        <!-- 聊天: 气泡轮廓 -->
        <svg v-if="tab.route === '/chat'" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
        </svg>
        <!-- 看板: 3个递增高度的竖条 -->
        <svg v-else-if="tab.route === '/dashboard'" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <rect x="3" y="12" width="4" height="9" rx="1"/>
          <rect x="10" y="6" width="4" height="15" rx="1"/>
          <rect x="17" y="3" width="4" height="18" rx="1"/>
        </svg>
        <!-- 文件: 文件夹轮廓 -->
        <svg v-else-if="tab.route === '/files'" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
        </svg>
        <!-- 报告: 文档带水平线 -->
        <svg v-else-if="tab.route === '/reports'" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
          <polyline points="14 2 14 8 20 8"/>
          <line x1="8" y1="13" x2="16" y2="13"/>
          <line x1="8" y1="17" x2="16" y2="17"/>
        </svg>
        <!-- 设置: 齿轮 -->
        <svg v-else-if="tab.route === '/settings'" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="3"/>
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>
        </svg>
      </span>
      <span class="nav-label">{{ tab.label }}</span>
    </router-link>
  </nav>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router'

const route = useRoute()

interface TabItem {
  route: string
  label: string
}

const tabs: TabItem[] = [
  { route: '/chat', label: '聊天' },
  { route: '/dashboard', label: '看板' },
  { route: '/files', label: '文件' },
  { route: '/reports', label: '报告' },
  { route: '/settings', label: '设置' },
]

function isActive(path: string): boolean {
  return route.path === path
}
</script>

<style scoped>
.bottom-nav {
  flex-shrink: 0;
  display: flex;
  background: var(--surface);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-top: 0.5px solid var(--border);
  padding: 8px 0;
  padding-bottom: env(safe-area-inset-bottom, 8px);
  position: relative;
  z-index: 600;
}

.nav-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  background: transparent;
  border: none;
  color: var(--text3);
  font-family: inherit;
  font-size: 10px;
  cursor: pointer;
  padding: 6px 0;
  transition: color 0.2s;
  font-weight: 500;
  text-decoration: none;
}

.nav-item .nav-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  line-height: 1;
}

.nav-item.active {
  color: var(--primary);
}

.nav-item.active .nav-icon {
  color: var(--primary);
}
</style>
