<template>
  <div class="detail-overlay" :class="{ open: visible }">
    <div class="detail-header">
      <span class="dt-title">通知历史</span>
      <button class="dt-close" @click="$emit('close')">
        <i class="fas fa-times"></i>
      </button>
    </div>
    <div class="detail-body notification-body">
      <!-- Loading state -->
      <div v-if="state === 'loading'" class="notification-center">
        <LoadingSpinner text="加载中..." />
      </div>

      <!-- Error state -->
      <div v-else-if="state === 'error'" class="notification-center">
        <i class="fas fa-exclamation-triangle" style="font-size:36px;opacity:0.3;color:var(--text3)"></i>
        <div class="notification-status-text">加载失败</div>
      </div>

      <!-- Empty state -->
      <div v-else-if="notifications.length === 0" class="notification-center">
        <i class="fas fa-bell-slash" style="font-size:36px;opacity:0.3;color:var(--text3)"></i>
        <div class="notification-status-text">暂无通知</div>
      </div>

      <!-- Notification list -->
      <template v-else>
        <div class="notification-count">共 {{ total }} 条通知</div>
        <div
          v-for="n in notifications"
          :key="n.id"
          class="notification-item"
        >
          <div class="notification-item__content">
            <div class="notification-item__title">{{ n.title }}</div>
            <div class="notification-item__body">{{ n.content }}</div>
            <div class="notification-item__time">{{ formatTime(n.created_at) }}</div>
          </div>
          <button
            class="notification-item__delete"
            @click="handleDelete(n.id)"
            title="删除"
          >
            &times;
          </button>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { watch } from 'vue'
import LoadingSpinner from './LoadingSpinner.vue'

interface NotificationItem {
  id: number
  title: string
  content: string
  created_at: number
}

const props = withDefaults(defineProps<{
  visible: boolean
  notifications?: NotificationItem[]
  total?: number
  state?: 'loading' | 'error' | 'success'
}>(), {
  notifications: () => [],
  total: 0,
  state: 'loading',
})

const emit = defineEmits<{
  close: []
  delete: [id: number]
  reload: []
}>()

function formatTime(ts: number): string {
  if (!ts) return ''
  try {
    const d = new Date(ts * 1000)
    const now = new Date()
    const pad = (n: number) => String(n).padStart(2, '0')
    if (d.toDateString() === now.toDateString()) {
      return `今天 ${pad(d.getHours())}:${pad(d.getMinutes())}`
    }
    const yesterday = new Date(now)
    yesterday.setDate(yesterday.getDate() - 1)
    if (d.toDateString() === yesterday.toDateString()) {
      return `昨天 ${pad(d.getHours())}:${pad(d.getMinutes())}`
    }
    return `${pad(d.getMonth() + 1)}/${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
  } catch {
    return ''
  }
}

function handleDelete(id: number) {
  emit('delete', id)
}

watch(() => props.visible, (val) => {
  if (val) {
    emit('reload')
  }
})
</script>

<style scoped>
.detail-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.88);
  backdrop-filter: blur(14px);
  display: none;
  flex-direction: column;
  z-index: 700;
}

.detail-overlay.open {
  display: flex;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 20px;
  flex-shrink: 0;
  background: var(--surface);
}

.dt-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--text);
}

.dt-close {
  background: transparent;
  border: none;
  color: var(--text3);
  font-size: 20px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 6px;
}

.dt-close:hover {
  background: var(--surface2);
}

.detail-body {
  flex: 1;
  overflow-y: auto;
  padding: 14px 20px 90px;
}

.notification-center {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  gap: 12px;
  min-height: 30vh;
}

.notification-status-text {
  font-size: 14px;
  color: var(--text2);
}

.notification-count {
  font-size: 11px;
  color: var(--text3);
  margin-bottom: 10px;
}

.notification-item {
  background: var(--surface2);
  border-radius: 10px;
  padding: 12px 14px;
  margin-bottom: 8px;
  border: 1px solid var(--border);
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 8px;
}

.notification-item__content {
  flex: 1;
  min-width: 0;
}

.notification-item__title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
  margin-bottom: 4px;
}

.notification-item__body {
  font-size: 12px;
  color: var(--text2);
  line-height: 1.5;
  word-break: break-word;
  white-space: pre-wrap;
}

.notification-item__time {
  font-size: 10px;
  color: var(--text3);
  margin-top: 6px;
}

.notification-item__delete {
  flex-shrink: 0;
  background: transparent;
  border: none;
  color: var(--text3);
  font-size: 18px;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
  line-height: 1;
}

.notification-item__delete:hover {
  color: #ff6b6b;
  background: var(--surface3);
}
</style>
