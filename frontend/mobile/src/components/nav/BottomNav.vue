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
        <i :class="tab.icon"></i>
      </span>
      <span>{{ tab.label }}</span>
    </router-link>
  </nav>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router'

const route = useRoute()

interface TabItem {
  route: string
  icon: string
  label: string
}

const tabs: TabItem[] = [
  { route: '/chat', icon: 'fas fa-comment-dots', label: '聊天' },
  { route: '/dashboard', icon: 'fas fa-chart-line', label: '看板' },
  { route: '/files', icon: 'fas fa-folder', label: '文件' },
  { route: '/reports', icon: 'fas fa-file-alt', label: '报告' },
  { route: '/settings', icon: 'fas fa-cog', label: '设置' },
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
  border-top: 1px solid var(--border);
  padding: 8px 0 18px;
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
  font-size: 12px;
  cursor: pointer;
  padding: 6px 0;
  transition: color 0.2s;
  font-weight: 500;
  text-decoration: none;
}

.nav-item .nav-icon {
  font-size: 22px;
  line-height: 1;
}

.nav-item.active {
  color: var(--primary-light);
}

.nav-item.active .nav-icon {
  color: var(--primary-light);
}
</style>
