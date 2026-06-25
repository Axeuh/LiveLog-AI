<template>
  <!-- 遮罩层 -->
  <Transition name="backdrop">
    <div
      v-if="visible"
      class="drawer-backdrop"
      @click="handleClose"
    />
  </Transition>

  <!-- 抽屉面板 -->
  <Transition name="drawer">
    <div
      v-if="visible"
      class="session-drawer"
    >
      <!-- 头部 -->
      <div class="drawer-header">
        <span class="drawer-title">会话列表</span>
        <button
          class="drawer-close"
          @click="handleClose"
        >
          <i class="fas fa-times" />
        </button>
      </div>

      <!-- 会话列表 -->
      <div class="drawer-body">
        <div
          v-if="sessions.length === 0"
          class="drawer-empty"
        >
          暂无会话
        </div>
        <div
          v-for="session in sessions"
          :key="session.id"
          class="session-item"
          :class="{ active: session.id === currentSessionId }"
        >
          <div class="si-top">
            <!-- 编辑模式 -->
            <template v-if="editingSessionId === session.id">
              <input
                ref="renameInputRef"
                v-model="editTitle"
                class="si-rename-input"
                type="text"
                maxlength="50"
                @keydown.enter="handleRenameSubmit(session.id)"
                @keydown.escape="handleRenameCancel"
                @blur="handleRenameSubmit(session.id)"
                @click.stop
              />
            </template>
            <!-- 显示模式 -->
            <template v-else>
              <span
                class="si-title"
                @click="handleSelectSession(session.id)"
              >{{ session.title || '未命名会话' }}</span>
              <button
                class="si-rename-btn"
                title="重命名"
                @click.stop="handleStartRename(session)"
              >
                <i class="fas fa-pen" />
              </button>
            </template>
            <span class="si-date">{{ session.date || '' }}</span>
          </div>
          <div
            v-if="session.preview"
            class="si-preview"
            @click="handleSelectSession(session.id)"
          >
            {{ session.preview }}
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { ref, nextTick } from 'vue'
import { useChatSingleton } from '@/composables/useChat'
import type { SessionInfo } from '@/types'

defineProps<{
  /** 是否显示抽屉 */
  visible: boolean
}>()

const emit = defineEmits<{
  /** 关闭抽屉 */
  (e: 'close'): void
  /** 选择会话 */
  (e: 'select-session', sessionId: string): void
}>()

const { sessions, currentSessionId, switchSession, renameSession } = useChatSingleton()

// ==================== 重命名状态 ====================

const editingSessionId = ref<string>('')
const editTitle = ref('')
const renameInputRef = ref<HTMLInputElement | null>(null)

/** 开始重命名 */
function handleStartRename(session: SessionInfo): void {
  editingSessionId.value = session.id
  editTitle.value = session.title || ''
  nextTick(() => {
    renameInputRef.value?.focus()
    renameInputRef.value?.select()
  })
}

/** 提交重命名 */
async function handleRenameSubmit(sessionId: string): Promise<void> {
  const newTitle = editTitle.value.trim()
  if (!newTitle || !sessionId) {
    handleRenameCancel()
    return
  }
  editingSessionId.value = ''
  await renameSession(sessionId, newTitle)
}

/** 取消重命名 */
function handleRenameCancel(): void {
  editingSessionId.value = ''
  editTitle.value = ''
}

/** 关闭抽屉 */
function handleClose(): void {
  handleRenameCancel()
  emit('close')
}

/** 选择会话 */
async function handleSelectSession(sessionId: string): Promise<void> {
  if (sessionId === currentSessionId.value) {
    handleClose()
    return
  }
  // 由父组件 (ChatView) 处理 switchSession, 避免重复调用
  emit('select-session', sessionId)
  handleClose()
}
</script>

<style scoped>
/* 遮罩层 */
.drawer-backdrop {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 700;
}

/* 抽屉面板 */
.session-drawer {
  position: fixed;
  top: 0;
  left: 0;
  width: 75vw;
  max-width: 320px;
  bottom: 0;
  background: var(--surface);
  z-index: 800;
  display: flex;
  flex-direction: column;
  box-shadow: 2px 0 20px rgba(0, 0, 0, 0.3);
}

/* 头部 */
.drawer-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 16px 12px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.drawer-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--text);
}

.drawer-close {
  background: transparent;
  border: none;
  color: var(--text3);
  font-size: 18px;
  cursor: pointer;
  padding: 4px;
  transition: color 0.15s;
}

.drawer-close:active {
  color: var(--text);
}

/* 列表区域 */
.drawer-body {
  flex: 1;
  overflow-y: auto;
  padding: 8px 12px;
  -webkit-overflow-scrolling: touch;
}

.drawer-empty {
  text-align: center;
  padding: 30px;
  color: var(--text3);
  font-size: 13px;
}

/* 会话条目 */
.session-item {
  display: flex;
  flex-direction: column;
  padding: 12px 14px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background 0.15s;
}

.session-item:active {
  background: var(--surface2);
}

.session-item.active {
  background: var(--surface3);
}

.session-item .si-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2px;
  gap: 6px;
}

.session-item .si-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-item .si-rename-btn {
  width: 24px;
  height: 24px;
  border: none;
  background: transparent;
  color: var(--text3);
  font-size: 11px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  flex-shrink: 0;
  opacity: 0;
  transition: opacity 0.15s, background 0.15s;
}

.session-item:hover .si-rename-btn {
  opacity: 1;
}

.session-item .si-rename-btn:active {
  background: var(--surface3);
  color: var(--primary);
}

.si-rename-input {
  flex: 1;
  background: var(--surface2);
  border: 1px solid var(--primary);
  border-radius: 6px;
  padding: 4px 8px;
  color: var(--text);
  font-family: inherit;
  font-size: 13px;
  font-weight: 600;
  outline: none;
  min-width: 0;
}

.session-item .si-date {
  font-size: 10px;
  color: var(--text3);
  flex-shrink: 0;
}

.session-item .si-preview {
  font-size: 12px;
  color: var(--text2);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 遮罩层动画 */
.backdrop-enter-active,
.backdrop-leave-active {
  transition: opacity 0.25s ease;
}

.backdrop-enter-from,
.backdrop-leave-to {
  opacity: 0;
}

/* 抽屉滑入动画 */
.drawer-enter-active,
.drawer-leave-active {
  transition: transform 0.25s ease;
}

.drawer-enter-from,
.drawer-leave-to {
  transform: translateX(-100%);
}
</style>
