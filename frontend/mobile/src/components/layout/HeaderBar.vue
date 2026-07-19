<template>
  <div class="header-bar" v-if="isPC">
    <div class="header-left">
      <select class="session-select" v-model="currentSessionId" @change="handleSessionChange">
        <option value="" disabled>选择会话</option>
        <option v-for="s in sessions" :key="s.id" :value="s.id">
          {{ s.title || '未命名会话' }}
        </option>
      </select>
    </div>
    <div class="header-right">
      <span class="conn-status" :class="connClass" :title="connTitle"></span>
      <!-- 子智能体按钮 -->
      <button
        class="header-btn"
        :class="{ active: subAgents.showList.value }"
        @click="handleToggleSubAgents"
        title="子智能体"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
          <circle cx="9" cy="7" r="4"/>
          <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
          <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
        </svg>
      </button>
      <button class="header-btn" @click="toggleNotifications" title="通知">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
          <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
        </svg>
        <span v-if="notificationCount > 0" class="notif-badge">{{ notificationCount }}</span>
      </button>
      <button class="header-btn" @click="cycleTheme" title="切换主题">
        <!-- 月亮 -->
        <svg v-if="theme === 'dark'" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
        </svg>
        <!-- 太阳 -->
        <svg v-else-if="theme === 'light'" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="5"/>
          <line x1="12" y1="1" x2="12" y2="3"/>
          <line x1="12" y1="21" x2="12" y2="23"/>
          <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>
          <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
          <line x1="1" y1="12" x2="3" y2="12"/>
          <line x1="21" y1="12" x2="23" y2="12"/>
          <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>
          <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
        </svg>
        <!-- 雪花 -->
        <svg v-else width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <line x1="12" y1="2" x2="12" y2="22"/>
          <line x1="2" y1="12" x2="22" y2="12"/>
          <line x1="4.93" y1="4.93" x2="19.07" y2="19.07"/>
          <line x1="19.07" y1="4.93" x2="4.93" y2="19.07"/>
        </svg>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useLayout } from '@/composables/useLayout'
import { useChatSingleton } from '@/composables/useChat'
import { useTheme } from '@/composables/useTheme'
import { useRealTimeSingleton } from '@/composables/useRealTime'
import { useSubAgentsSingleton } from '@/composables/useSubAgents'

const { isPC } = useLayout()
const { sessions, currentSessionId, switchSession } = useChatSingleton()
const { theme, setTheme, availableThemes } = useTheme()
const rt = useRealTimeSingleton()
const subAgents = useSubAgentsSingleton()

// 通知计数（暂时硬编码为0，后续可接入实际通知系统）
const notificationCount = ref(0)

// 主题切换
function cycleTheme() {
  const idx = availableThemes.indexOf(theme.value)
  const next = availableThemes[(idx + 1) % availableThemes.length]
  setTheme(next)
}

// 子智能体按钮点击：静默加载后切换弹窗
async function handleToggleSubAgents(): Promise<void> {
  const wasVisible = subAgents.showList.value
  if (!wasVisible) {
    // 静默加载，完成后显示
    await subAgents.loadSubAgents(currentSessionId.value, [])
    subAgents.showList.value = true
  } else {
    subAgents.showList.value = false
  }
}

// 连接状态
const connClass = computed(() => {
  const sse = rt.sseConnected.value
  const ws = rt.wsConnected.value
  if (sse && ws) return 'connected'
  if (sse || ws) return 'partial'
  return 'disconnected'
})

const connTitle = computed(() => {
  const sse = rt.sseConnected.value
  const ws = rt.wsConnected.value
  return `SSE: ${sse ? 'OK' : 'X'} | WS: ${ws ? 'OK' : 'X'}`
})

// 会话切换处理
function handleSessionChange() {
  if (currentSessionId.value) {
    switchSession(currentSessionId.value)
  }
}

// 通知切换（暂时为空实现）
function toggleNotifications() {
  // TODO: 接入通知系统
}
</script>

<style scoped>
.header-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 48px;
  padding: 0 16px;
  background: var(--surface);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-bottom: 0.5px solid var(--border);
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.session-select {
  height: 32px;
  padding: 0 12px;
  background: var(--surface2);
  color: var(--text);
  border: 0.5px solid var(--border);
  border-radius: 8px;
  font-size: 14px;
  font-family: inherit;
  cursor: pointer;
  outline: none;
  min-width: 160px;
  transition: border-color 0.2s;
}

.session-select:focus {
  border-color: var(--primary);
}

.session-select option {
  background: var(--surface);
  color: var(--text);
}

.header-btn {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  border-radius: 50%;
  color: var(--text2);
  cursor: pointer;
  transition: background-color 0.2s, color 0.2s;
  position: relative;
}

.header-btn:hover {
  background: var(--surface3);
  color: var(--text);
}

.header-btn.active {
  background: var(--primary);
  color: #fff;
}

.conn-status {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
  flex-shrink: 0;
}

.conn-status.connected {
  background: var(--accent);
  box-shadow: 0 0 4px var(--accent);
  animation: connPulse 2s ease-in-out infinite;
}

.conn-status.partial {
  background: var(--accent3);
  box-shadow: 0 0 4px var(--accent3);
}

.conn-status.disconnected {
  background: var(--danger);
  box-shadow: 0 0 4px var(--danger);
}

@keyframes connPulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.notif-badge {
  position: absolute;
  top: -2px;
  right: -2px;
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  background: var(--danger);
  color: #fff;
  font-size: 10px;
  font-weight: 600;
  line-height: 16px;
  text-align: center;
  border-radius: 8px;
}
</style>
