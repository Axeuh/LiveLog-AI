<template>
  <div id="page-chat" class="page active">
    <!-- 会话顶栏 -->
    <div class="session-bar" @click="handleSessionBarClick">
      <span class="session-current">
        <span>{{ currentSessionTitle || '新对话' }}</span>
        <i class="fas fa-chevron-down session-arrow"></i>
      </span>
      <button class="new-session-btn" title="新建会话" @click.stop="handleNewSession">
        <i class="fas fa-plus"></i>
      </button>
    </div>

    <!-- 加载/空状态 -->
    <PageState
      v-if="pageState"
      :state="pageState.state"
      :message="pageState.message"
      :description="pageState.description"
      @retry="handleRetry"
    />

    <!-- 消息列表 (含流式消息) -->
    <div
      v-show="!pageState"
      ref="chatMessagesRef"
      class="chat-msgs"
    >
      <template v-for="(group, gIdx) in messageGroups" :key="gIdx">
        <!-- 日期分隔 -->
        <div class="chat-date">{{ group.dateLabel }}</div>

        <MessageBubble v-for="(msg, mIdx) in group.messages" :key="mIdx" :message="msg" :role="getMessageRole(msg)" />
      </template>

      <!-- 流式消息直接在消息列表中渲染, 跟在历史消息后面 -->
      <MessageBubble
        v-if="isStreaming"
        :message="streamingChatMessage"
        role="ai"
      />
    </div>

    <!-- 会话抽屉 -->
    <SessionDrawer
      :visible="showDrawer"
      @close="showDrawer = false"
      @select-session="handleSelectSession"
    />

    <ChatInput @send="handleSend" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import PageState from '@/components/common/PageState.vue'
import ChatInput from '@/components/chat/ChatInput.vue'
import MessageBubble from '@/components/chat/MessageBubble.vue'
import SessionDrawer from '@/components/chat/SessionDrawer.vue'
import { useChatSingleton } from '@/composables/useChat'
import { useStreamingMessageSingleton } from '@/composables/useStreamingMessage'
import type { ChatMessage } from '@/types'

// ==================== Composables ====================

const chat = useChatSingleton()
const streaming = useStreamingMessageSingleton()

// ==================== 状态 ====================

const chatMessagesRef = ref<HTMLDivElement | null>(null)

/** 是否正在流式输出 */
const isStreaming = computed(() => streaming.isStreaming.value)

/** 会话抽屉显示状态 */
const showDrawer = ref(false)

/** 当前会话标题 */
const currentSessionTitle = computed(() => chat.currentSessionTitle.value)

/** 消息列表 */
const messages = computed(() => chat.messages.value)

/** 是否正在加载 */
const loadingMessages = computed(() => chat.loadingMessages.value)

// ==================== 页面状态 ====================

interface PageStateInfo {
  state: 'loading' | 'empty' | 'error'
  message: string
  description?: string
}

/** 计算页面状态 (loading / empty / null=正常显示消息) */
const pageState = computed<PageStateInfo | null>(() => {
  if (loadingMessages.value) {
    return { state: 'loading', message: '加载中...', description: '正在加载聊天记录' }
  }
  if (!chat.currentSessionId.value) {
    return { state: 'empty', message: '暂无会话', description: '点击右上角创建新会话' }
  }
  if (messages.value.length === 0 && !isStreaming.value) {
    return { state: 'empty', message: '暂无消息', description: '发送一条消息开始对话' }
  }
  return null
})

// ==================== 日期分组 ====================

interface MessageGroup {
  dateLabel: string
  messages: ChatMessage[]
}

/**
 * 将消息按日期分组
 * 同一天的消息归为一组, 每组前显示日期分隔
 */
const messageGroups = computed<MessageGroup[]>(() => {
  const msgs = messages.value
  if (msgs.length === 0) return []

  const groups: MessageGroup[] = []
  let currentDate = ''
  let currentGroup: ChatMessage[] = []

  for (const msg of msgs) {
    const dateStr = getMessageDate(msg)
    if (dateStr !== currentDate) {
      // 保存前一组
      if (currentGroup.length > 0) {
        groups.push({ dateLabel: currentDate, messages: currentGroup })
      }
      currentDate = dateStr
      currentGroup = [msg]
    } else {
      currentGroup.push(msg)
    }
  }

  // 保存最后一组
  if (currentGroup.length > 0) {
    groups.push({ dateLabel: currentDate, messages: currentGroup })
  }

  return groups
})

// ==================== 消息工具函数 ====================

/** 获取消息角色 */
function getMessageRole(msg: ChatMessage): 'ai' | 'user' {
  const role = msg.info?.role || msg.role
  return role === 'assistant' ? 'ai' : 'user'
}

/** 发送消息 */
async function handleSend(text: string, files: File[]): Promise<void> {
  await chat.sendMessage(text, files)
}

/** 将 streamParts (StreamPartsMap) 转为 MessagePart[] 供 StreamingText 渲染 */
const streamPartsArray = computed(() => {
  return Object.values(streaming.streamParts).map((sp) => ({
    type: sp.type,
    text: sp.text,
    tool: sp.toolName,
    state: sp.toolStatus
      ? { status: sp.toolStatus, input: sp.toolInput, output: sp.toolOutput }
      : undefined,
  }))
})

/** 将流式内容构建为 ChatMessage, 直接在消息列表中渲染 */
const streamingChatMessage = computed<ChatMessage>(() => ({
  parts: streamPartsArray.value,
}))

/** 获取消息日期字符串 (用于分组) */
function getMessageDate(msg: ChatMessage): string {
  const ts = msg.timestamp || msg.created_at
  if (!ts) return '未知日期'

  try {
    const date = new Date(ts)
    if (isNaN(date.getTime())) return '未知日期'

    const now = new Date()
    const isToday =
      date.getFullYear() === now.getFullYear() &&
      date.getMonth() === now.getMonth() &&
      date.getDate() === now.getDate()

    if (isToday) return '今天'

    const yesterday = new Date(now)
    yesterday.setDate(yesterday.getDate() - 1)
    const isYesterday =
      date.getFullYear() === yesterday.getFullYear() &&
      date.getMonth() === yesterday.getMonth() &&
      date.getDate() === yesterday.getDate()

    if (isYesterday) return '昨天'

    // 格式: 2026年6月11日 星期三
    const weekdays = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六']
    const year = date.getFullYear()
    const month = date.getMonth() + 1
    const day = date.getDate()
    const weekday = weekdays[date.getDay()]
    return `${year}年${month}月${day}日 ${weekday}`
  } catch {
    return '未知日期'
  }
}

// ==================== 滚动控制 ====================

let _userScrolledUp = false

/** 检查用户是否在底部附近 (20px 阈值) */
function isNearBottom(): boolean {
  const el = chatMessagesRef.value
  if (!el) return true
  return el.scrollHeight - el.scrollTop - el.clientHeight < 20
}

/** 滚动到底部 (仅在用户未主动上滑时执行) */
function scrollToBottom(smooth = true): void {
  if (_userScrolledUp) return
  nextTick(() => {
    const el = chatMessagesRef.value
    if (el) {
      el.scrollTo({
        top: el.scrollHeight,
        behavior: smooth ? 'smooth' : 'instant',
      })
    }
  })
}

/** 重置用户上滑标记 (新消息/流式内容到来时如果已在底部就滚动) */
function resetScrollLock(): void {
  if (isNearBottom()) {
    _userScrolledUp = false
  }
}

/** 监听消息变化, 自动滚动到底部 */
watch(
  () => messages.value.length,
  () => {
    scrollToBottom()
  },
)

/** 监听流式状态变化, 滚动到底部 */
watch(isStreaming, (val) => {
  if (val) {
    scrollToBottom(false)
  }
})

/** 流式渲染过程中自动滚动到底部 (内容变化时) */
watch(
  () => streamPartsArray.value.length,
  () => {
    if (isStreaming.value) {
      scrollToBottom(false)
    }
  },
)

// ==================== 事件处理 ====================

/** 点击会话栏 (打开会话抽屉) */
function handleSessionBarClick(): void {
  showDrawer.value = !showDrawer.value
}

/** 选择会话 (带防重复守卫) */
async function handleSelectSession(sessionId: string): Promise<void> {
  if (!sessionId) return
  showDrawer.value = false
  // 如果已经是当前会话，不再切换
  if (sessionId === chat.currentSessionId.value) return
  await chat.switchSession(sessionId)
}

/** 新建会话 */
async function handleNewSession(): Promise<void> {
  await chat.createNewSession()
  scrollToBottom(false)
}

/** 重试加载 */
async function handleRetry(): Promise<void> {
  await chat.loadSessions()
  if (chat.currentSessionId.value) {
    await chat.loadChatHistory(chat.currentSessionId.value)
  }
}

// ==================== 生命周期 ====================

onMounted(async () => {
  await chat.loadSessions()
  if (chat.currentSessionId.value) {
    await chat.loadChatHistory(chat.currentSessionId.value)
  }
  scrollToBottom(false)

  // 监听滚动事件，判断用户是否主动上滑
  const el = chatMessagesRef.value
  if (el) {
    el.addEventListener('scroll', onChatScroll)
  }
})

onUnmounted(() => {
  const el = chatMessagesRef.value
  if (el) {
    el.removeEventListener('scroll', onChatScroll)
  }
})

function onChatScroll(): void {
  if (isNearBottom()) {
    _userScrolledUp = false
  } else {
    _userScrolledUp = true
  }
}
</script>

<style scoped>
/* 页面容器 - flex column 布局 */
#page-chat {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  height: 100%;
  padding: 12px 12px 0;
}

/* 会话顶栏 */
.session-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  margin: 0 0 10px;
  cursor: pointer;
  border-bottom: 1px solid var(--border);
}

.session-bar:active {
  opacity: 0.7;
}

.session-current {
  font-size: 15px;
  font-weight: 700;
  color: var(--text);
  flex: 1;
}

.session-arrow {
  font-size: 11px;
  color: var(--text3);
  transition: transform 0.2s;
  margin-left: 4px;
}

.new-session-btn {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  border: none;
  background: var(--surface2);
  color: var(--text2);
  font-size: 13px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
  flex-shrink: 0;
}

.new-session-btn:active {
  background: var(--primary);
  color: #fff;
}

/* 消息列表 */
.chat-msgs {
  flex: 1;
  overflow-y: auto;
  padding: 8px 12px 0;
  -webkit-overflow-scrolling: touch;
}

/* 日期分隔 */
.chat-date {
  font-size: 11px;
  color: var(--text3);
  text-align: center;
  margin: 10px 0 8px;
  font-weight: 500;
}
</style>
