<template>
  <div class="app">
    <div class="app-content">
      <router-view />
    </div>
    <!-- 登录覆盖层隐藏时才显示底部导航 -->
    <BottomNav v-show="!showLogin" />

    <!-- 浮动按钮 - 仅登录后显示 -->
    <template v-if="!showLogin">
      <!-- WS 日志按钮 -->
      <div
        class="floating-btn floating-btn--ws"
        @click="toggleWsLog"
        title="WS 日志"
      >
        <i class="fas fa-plug"></i>
      </div>

      <!-- 通知按钮 -->
      <div
        class="floating-btn floating-btn--notif"
        @click="openNotifications"
        title="通知历史"
      >
        <i class="fas fa-bell"></i>
      </div>
    </template>

    <!-- WS 日志面板 -->
    <Transition name="ws-panel">
      <div v-if="showWsLog" class="ws-log-panel">
        <div class="ws-log-panel__header">
          <span class="ws-log-panel__title">WS 日志</span>
          <button class="ws-log-panel__close" @click="showWsLog = false">
            <i class="fas fa-times"></i>
          </button>
        </div>
        <div class="ws-log-panel__body" ref="wsLogBody">
          <div v-if="wsLogs.length === 0" class="ws-log-empty">
            暂无日志
          </div>
          <div
            v-for="(log, idx) in wsLogs"
            :key="idx"
            class="ws-log-item"
          >
            <span class="ws-log-item__time">{{ log.time }}</span>
            <span class="ws-log-item__msg">{{ log.message }}</span>
          </div>
        </div>
      </div>
    </Transition>

    <!-- 通知列表 -->
    <NotificationList
      :visible="showNotifications"
      :notifications="notifications"
      :total="notificationTotal"
      :state="notificationState"
      @close="showNotifications = false"
      @delete="handleDeleteNotification"
      @reload="loadNotifications"
    />

    <!-- Token 登录覆盖层 (401 时自动弹出) -->
    <LoginOverlay
      :visible="showLogin"
      @close="showLogin = false"
      @login-success="handleLoginSuccess"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import BottomNav from '@/components/nav/BottomNav.vue'
import LoginOverlay from '@/components/common/LoginOverlay.vue'
import NotificationList from '@/components/common/NotificationList.vue'
import { useApi } from '@/composables/useApi'
import { useChatIntegration } from '@/composables/useChatIntegration'
import { useRealTimeSingleton } from '@/composables/useRealTime'
import { apiGet, apiPost } from '@/api/client'
import type { WSMessageHandler } from '@/api/ws'

// ==================== 状态 ====================

/** 登录覆盖层显示状态 */
const showLogin = ref(false)

/** WS 日志面板显示状态 */
const showWsLog = ref(false)

/** 通知面板显示状态 */
const showNotifications = ref(false)

/** WS 日志列表 */
interface WsLogEntry {
  time: string
  message: string
}

const wsLogs = ref<WsLogEntry[]>([])
const wsLogBody = ref<HTMLElement | null>(null)

/** 通知数据 */
interface NotificationItem {
  id: number
  title: string
  content: string
  created_at: number
}

const notifications = ref<NotificationItem[]>([])
const notificationTotal = ref(0)
const notificationState = ref<'loading' | 'error' | 'success'>('loading')

// ==================== 初始化 ====================

const { onAuthFail, offAuthFail, isLoggedIn } = useApi()
const rt = useRealTimeSingleton()

/**
 * Auth fail 回调
 * 当 API 请求返回 401 时, 由 client.ts 触发
 */
function handleAuthFail(): void {
  showLogin.value = true
}

/**
 * 登录成功回调
 * LoginOverlay emit login-success(token) 后, 关闭覆盖层并重连实时连接
 */
function handleLoginSuccess(_token: string): void {
  showLogin.value = false
  // token 已由 LoginOverlay 内部的 useApi().login() 保存
  // 重连实时连接 (SSE + WS), 使用新 token
  rt.reconnectSSE()
  rt.reconnectWS()
}

// ==================== WS 日志 ====================

/** WS 消息处理器（跳过 TTS 音频块避免刷屏） */
const wsLogHandler: WSMessageHandler = (data: unknown) => {
  // 跳过 TTS 音频块，仅记录开始/结束
  if (data && typeof data === 'object') {
    const msg = data as Record<string, unknown>
    if (msg.type === 'tts_audio_chunk') return
    if (msg.type === 'tts_audio') return
    if (msg.type === 'tts_start' || msg.type === 'tts_end') {
      // 只记录类型，不记录 base64 数据
      wsLogs.value.push({
        time: now(),
        message: JSON.stringify({ type: msg.type, text: (msg.text || '')?.toString()?.substring(0, 50) }),
      })
      trimLog()
      return
    }
  }

  const now = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  const time = `${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`

  let message: string
  if (typeof data === 'string') {
    message = data
  } else {
    try {
      message = JSON.stringify(data)
    } catch {
      message = String(data)
    }
  }

  wsLogs.value.push({ time, message })
  trimLog()
}

/** 限制日志数量 */
function trimLog(): void {
  if (wsLogs.value.length > 200) {
    wsLogs.value = wsLogs.value.slice(-100)
  }
}

/** 切换 WS 日志面板 */
function toggleWsLog(): void {
  showWsLog.value = !showWsLog.value
}

// ==================== 通知 ====================

/** 打开通知面板 */
function openNotifications(): void {
  showNotifications.value = true
}

/** 通知 API 响应类型 */
interface NotificationResponse {
  notifications: NotificationItem[]
  total: number
}

/** 加载通知列表 */
async function loadNotifications(): Promise<void> {
  notificationState.value = 'loading'
  try {
    const data = await apiGet<NotificationResponse>('/api/notification/history')
    if (data && data.notifications) {
      notifications.value = data.notifications
      notificationTotal.value = data.total || data.notifications.length
      notificationState.value = 'success'
    } else {
      notifications.value = []
      notificationTotal.value = 0
      notificationState.value = 'success'
    }
  } catch (e) {
    console.error('[App] 加载通知失败:', e)
    notificationState.value = 'error'
  }
}

/** 删除通知 */
async function handleDeleteNotification(id: number): Promise<void> {
  try {
    await apiPost(`/api/notification/history/${id}`, {})
    // 从列表中移除
    notifications.value = notifications.value.filter(n => n.id !== id)
    notificationTotal.value = Math.max(0, notificationTotal.value - 1)
  } catch (e) {
    console.error('[App] 删除通知失败:', e)
  }
}

// ==================== 生命周期 ====================

onMounted(() => {
  // 1. 注册 auth fail 监听
  onAuthFail(handleAuthFail)

  // 2. 检查初始登录状态, 未登录则显示登录覆盖层
  if (!isLoggedIn.value) {
    showLogin.value = true
  }

  // 3. 初始化聊天集成 (SSE 事件路由 + 实时连接)
  //    如果未登录, connect() 会失败但不影响后续登录后重连
  useChatIntegration()

  // 4. 注册 WS 消息监听 (用于日志面板)
  rt.onWSMessage(wsLogHandler)
})

onUnmounted(() => {
  // 清理: 移除 auth fail 监听, 断开实时连接, 移除 WS 日志监听
  offAuthFail(handleAuthFail)
  rt.offWSMessage(wsLogHandler)
  rt.disconnect()
})
</script>

<style scoped>
.app {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.app-content {
  flex: 1;
  overflow: hidden;
  min-height: 0;
  position: relative;
}

/* ==================== 浮动按钮 ==================== */

.floating-btn {
  position: fixed;
  right: 12px;
  z-index: 9999;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  cursor: pointer;
  border: 1px solid;
  transition: all 0.15s;
}

.floating-btn:active {
  transform: scale(0.95);
}

.floating-btn--ws {
  bottom: 228px;
  background: rgba(108, 92, 231, 0.3);
  border-color: rgba(108, 92, 231, 0.2);
  color: var(--primary-light);
}

.floating-btn--ws:active {
  background: rgba(108, 92, 231, 0.5);
}

.floating-btn--notif {
  bottom: 180px;
  background: rgba(253, 121, 168, 0.3);
  border-color: rgba(253, 121, 168, 0.2);
  color: var(--accent2);
}

.floating-btn--notif:active {
  background: rgba(253, 121, 168, 0.5);
}

/* ==================== WS 日志面板 ==================== */

.ws-log-panel {
  position: fixed;
  bottom: 268px;
  right: 12px;
  width: 300px;
  max-height: 300px;
  background: rgba(22, 22, 31, 0.95);
  backdrop-filter: blur(12px);
  border: 1px solid var(--border);
  border-radius: 12px;
  z-index: 9998;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.ws-log-panel__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.ws-log-panel__title {
  font-size: 11px;
  font-weight: 600;
  color: var(--text2);
}

.ws-log-panel__close {
  background: transparent;
  border: none;
  color: var(--text3);
  font-size: 12px;
  cursor: pointer;
  padding: 2px 4px;
}

.ws-log-panel__body {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
  max-height: 260px;
  font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', monospace;
  font-size: 11px;
}

.ws-log-empty {
  text-align: center;
  color: var(--text3);
  padding: 20px 0;
  font-family: inherit;
}

.ws-log-item {
  padding: 3px 0;
  border-bottom: 1px solid var(--border);
  display: flex;
  gap: 8px;
  word-break: break-all;
}

.ws-log-item__time {
  color: var(--text3);
  flex-shrink: 0;
}

.ws-log-item__msg {
  color: var(--text2);
}

/* WS 面板动画 */
.ws-panel-enter-active,
.ws-panel-leave-active {
  transition: opacity 0.15s ease;
}

.ws-panel-enter-from,
.ws-panel-leave-to {
  opacity: 0;
}
</style>
