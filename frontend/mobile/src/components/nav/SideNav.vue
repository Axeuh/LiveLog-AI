<template>
  <nav class="side-nav" v-if="isPC">
    <div class="nav-items">
      <div
        v-for="item in navItems"
        :key="item.route"
        class="nav-item"
        :class="{ active: route.path === item.route }"
        :title="item.label"
        @click="navigateTo(item.route)"
      >
        <div class="nav-icon">
          <!-- 聊天: 气泡轮廓 -->
          <svg v-if="item.route === '/chat'" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
          </svg>
          <!-- 看板: 3个递增高度的竖条 -->
          <svg v-else-if="item.route === '/dashboard'" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <rect x="3" y="12" width="4" height="9" rx="1"/>
            <rect x="10" y="6" width="4" height="15" rx="1"/>
            <rect x="17" y="3" width="4" height="18" rx="1"/>
          </svg>
          <!-- 文件: 文件夹轮廓 -->
          <svg v-else-if="item.route === '/files'" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
          </svg>
          <!-- 报告: 文档带水平线 -->
          <svg v-else-if="item.route === '/reports'" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
            <line x1="8" y1="13" x2="16" y2="13"/>
            <line x1="8" y1="17" x2="16" y2="17"/>
          </svg>
          <!-- 设置: 齿轮 -->
          <svg v-else-if="item.route === '/settings'" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="3"/>
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>
          </svg>
        </div>
      </div>
    </div>
  </nav>
</template>

<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import { useLayout } from '@/composables/useLayout'

interface NavItem {
  route: string
  label: string
}

const { isPC } = useLayout()
const route = useRoute()
const router = useRouter()

const navItems: NavItem[] = [
  { route: '/chat', label: '聊天' },
  { route: '/dashboard', label: '看板' },
  { route: '/files', label: '文件' },
  { route: '/reports', label: '报告' },
  { route: '/settings', label: '设置' },
]

function navigateTo(path: string) {
  router.push(path)
}
</script>

<style scoped>
.side-nav {
  width: 64px;
  height: 100vh;
  background: var(--bg);
  border-right: 0.5px solid var(--border);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  position: sticky;
  top: 0;
  z-index: 100;
}

.nav-items {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 12px 0;
  gap: 4px;
  flex: 1;
  justify-content: flex-start;
  padding-top: 16px;
}

.nav-item {
  width: 48px;
  padding: 10px 0;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  align-items: center;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
  position: relative;
  user-select: none;
}

.nav-item:hover {
  background: var(--surface2);
}

.nav-item.active {
  background: var(--surface3);
}

.nav-item.active::before {
  content: '';
  position: absolute;
  left: -8px;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 20px;
  background: var(--primary);
  border-radius: 3px;
}

.nav-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  color: var(--text3);
  transition: color 0.15s;
}

.nav-item.active .nav-icon {
  color: var(--primary);
}

.nav-item:hover .nav-icon {
  color: var(--text2);
}
</style>
