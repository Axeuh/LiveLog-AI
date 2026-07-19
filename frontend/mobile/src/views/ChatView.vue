<template>
  <div id="page-chat" class="page active">
    <!-- 子智能体模式: 返回按钮 + 子智能体按钮 -->
    <div v-if="isSubAgentMode" class="session-bar subagent-mode">
      <button class="back-btn" @click="handleBackToParent">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="15 18 9 12 15 6"/>
        </svg>
        <span>返回 {{ subAgents.parentSessionTitle }} 会话</span>
      </button>
      <div class="session-bar-actions">
        <button
          class="new-session-btn subagent-btn"
          title="查看子智能体"
          @click.stop="handleShowSubAgents"
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
            <circle cx="9" cy="7" r="4"/>
            <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
            <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
          </svg>
        </button>
      </div>
    </div>

    <!-- 会话顶栏 (PC 隐藏, 由 HeaderBar 切换) -->
    <div v-else v-show="!isPC" class="session-bar" @click="handleSessionBarClick">
      <span class="session-current">
        <span>{{ currentSessionTitle || '新对话' }}</span>
        <span class="session-arrow"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><polyline points="6 9 12 15 18 9"/></svg></span>
      </span>
      <div class="session-bar-actions">
        <!-- Token 用量 (移动端) -->
        <span
          v-if="currentTokens && currentTokens.total > 0"
          class="session-token-usage"
          :title="`Token 用量: 输入 ${currentTokens.input}, 输出 ${currentTokens.output}`"
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="9"></circle>
            <line x1="12" y1="8" x2="12" y2="16"></line>
            <line x1="9" y1="10" x2="15" y2="10"></line>
          </svg>
          <span>{{ formatTokenDisplay(currentTokens.total) }}</span>
        </span>
        <!-- 子智能体按钮 -->
        <button
          class="new-session-btn subagent-btn"
          title="查看子智能体"
          @click.stop="handleShowSubAgents"
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
            <circle cx="9" cy="7" r="4"/>
            <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
            <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
          </svg>
        </button>
      </div>
    </div>

    <!-- 消息/骨架共用容器 (始终在 DOM 中，避免输入框偏移) -->
    <div
      ref="chatMessagesRef"
      class="chat-msgs"
      :class="{ 'has-skeleton': loadingMessages && !USE_MOCK_DATA }"
      v-show="(!pageState || !!loadingMessages)"
    >
      <!-- 骨架屏 (容器内部覆盖，不影响 flex 布局) -->
      <SkeletonMessages v-if="loadingMessages && !USE_MOCK_DATA" />

      <!-- 真实消息 (仅非加载时显示) -->
      <template v-if="!loadingMessages">
        <template v-for="(group, gIdx) in displayMessageGroups" :key="gIdx">
          <!-- 日期分隔 -->
          <div class="chat-date">{{ group.dateLabel }}</div>

          <MessageBubble v-for="(msg, mIdx) in group.messages" :key="mIdx" :message="msg" :role="getDisplayMessageRole(msg)" />
        </template>
      </template>
    </div>

    <!-- 空/错误状态 (非 loading 时显示) -->
    <PageState
      v-if="pageState && pageState.state && pageState.state !== 'loading'"
      :state="pageState.state"
      :message="pageState.message"
      :description="pageState.description"
      @retry="handleRetry"
    />

    <!-- 会话状态指示器 (繁忙/空闲) -->
    <div v-if="currentSessionStatus === 'busy'" class="session-status-indicator">
      <span class="status-dot busy"></span>
      <span>正在处理...</span>
    </div>

    <!-- 会话标题栏 (仅 PC，移动端见上方 session-bar) -->
    <div v-if="isPC && currentSessionId" class="pc-session-bar">
      <span class="pc-session-title">
        {{ currentSessionTitle || '新对话' }}
        <span v-if="currentSessionStatus === 'busy'" class="status-dot busy"></span>
      </span>
      <div class="pc-session-actions">
        <!-- Token 用量 -->
        <span
          v-if="currentTokens && currentTokens.total > 0"
          class="session-token-usage"
          :title="`本会话 Token 用量: 输入 ${currentTokens.input}, 输出 ${currentTokens.output}`"
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="9"></circle>
            <line x1="12" y1="8" x2="12" y2="16"></line>
            <line x1="9" y1="10" x2="15" y2="10"></line>
          </svg>
          <span>{{ formatTokenDisplay(currentTokens.total) }}</span>
        </span>
        <!-- 会话 ID 复制 -->
        <button
          class="session-id-copy"
          :title="'复制会话 ID: ' + currentSessionId"
          @click="copySessionId"
        >
          <code>{{ truncateSessionId(currentSessionId) }}</code>
          <svg v-if="!copiedSessionId" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
          </svg>
          <span v-else class="copied-check">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#34c759" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="20 6 9 17 4 12"></polyline>
            </svg>
          </span>
        </button>
      </div>
    </div>

    <!-- 会话抽屉 -->
    <SessionDrawer
      :visible="showDrawer"
      :mode="isPC ? 'inline' : 'drawer'"
      @close="showDrawer = false"
      @select-session="handleSelectSession"
    />

    <ChatInput @send="handleSend" />

    <!-- 子智能体列表弹窗 -->
    <SubAgentList
      :visible="showSubAgentsList"
      :agents="subAgentsList"
      @close="showSubAgentsList = false"
      @select="handleSelectSubAgent"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import PageState from '@/components/common/PageState.vue'
import ChatInput from '@/components/chat/ChatInput.vue'
import MessageBubble from '@/components/chat/MessageBubble.vue'
import SessionDrawer from '@/components/chat/SessionDrawer.vue'
import SubAgentList from '@/components/chat/SubAgentList.vue'
import SkeletonMessages from '@/components/chat/SkeletonMessages.vue'
import { useChatSingleton } from '@/composables/useChat'
import { useStreamingMessageSingleton } from '@/composables/useStreamingMessage'
import { useLayout } from '@/composables/useLayout'
import { useSubAgentsSingleton } from '@/composables/useSubAgents'
import { USE_MOCK_DATA } from '@/composables/useMockData'
import type { ChatMessage } from '@/types'

const MOCK_MESSAGES: ChatMessage[] = [
  {
    role: 'user',
    content: '简述我今天的健康状况',
    timestamp: new Date(Date.now() - 7200000).toISOString(),
  },
  {
    role: 'assistant',
    parts: [
      {
        type: 'text',
        text: '好的，让我为您总结今天的健康数据：\n\n## 今日概览\n\n| 指标 | 数值 | 状态 |\n|------|------|------|\n| 心率 | 69 bpm | 正常范围 |\n| 步数 | 8,421 步 | 已完成 84% |\n| 血氧 | 97% | 优秀 |\n| 睡眠 | 7h 32m | 充足 |\n\n> 整体来看，您的各项指标均在健康范围内，继续保持！',
      },
    ],
    timestamp: new Date(Date.now() - 7100000).toISOString(),
  },
  {
    role: 'user',
    content: '帮我分析一下近一周的运动趋势',
    timestamp: new Date(Date.now() - 5400000).toISOString(),
  },
  {
    role: 'assistant',
    parts: [
      {
        type: 'reasoning',
        text: '分析步数数据发现明显的上升趋势，从周初5200步逐步增长至周五突破万步，说明用户活动量有所提升。',
      },
      {
        type: 'text',
        text: '### 近7日运动趋势分析\n\n过去一周您的活动量呈现上升趋势：\n\n- **周一**: 5,200 步（偏低）\n- **周二**: 6,800 步（正常）\n- **周三**: 7,100 步（正常）\n- **周四**: 9,300 步（活跃）\n- **周五**: 10,200 步（活跃）\n- **周六**: 8,400 步（正常）\n- **今日**: 8,421 步（进行中）\n\n> 建议：周三后开始明显增加，继续保持！',
      },
    ],
    timestamp: new Date(Date.now() - 5300000).toISOString(),
  },
  {
    role: 'user',
    content: '昨晚睡眠质量如何？',
    timestamp: new Date(Date.now() - 3600000).toISOString(),
  },
  {
    role: 'assistant',
    parts: [
      {
        type: 'text',
        text: '## 昨晚睡眠报告\n\n**总时长**: 7小时32分\n\n| 阶段 | 时长 | 占比 |\n|------|------|------|\n| 深睡 | 2h 10m | 29% |\n| REM | 1h 45m | 23% |\n| 浅睡 | 3h 05m | 41% |\n| 清醒 | 32m | 7% |\n\n深睡占比 29%（高于建议值 20%），恢复效果良好。',
      },
      {
        type: 'tool_call',
        tool: 'query_sleep_data',
        state: {
          status: 'completed',
        },
      },
    ],
    timestamp: new Date(Date.now() - 3500000).toISOString(),
  },
]

// ==================== Composables ====================

const chat = useChatSingleton()
const streaming = useStreamingMessageSingleton()
const { isPC } = useLayout()
const subAgents = useSubAgentsSingleton()

// ==================== 状态 ====================

const chatMessagesRef = ref<HTMLDivElement | null>(null)

/** 当前会话 ID (简化引用) */
const currentSessionId = computed(() => chat.currentSessionId.value)

/** 当前会话 Token 用量 (SSE 实时更新 + API 加载) */
const currentTokens = computed(() => streaming.currentTokens.value)

/** 复制会话 ID 后的临时状态 */
const copiedSessionId = ref(false)

/** 是否正在流式输出 */
const isStreaming = computed(() => streaming.isStreaming.value)

/** 会话抽屉显示状态 */
const showDrawer = ref(false)

/** 子智能体列表弹窗 (共享状态) */
const showSubAgentsList = computed({
  get: () => subAgents.showList.value,
  set: (v) => { subAgents.showList.value = v },
})

/** 子智能体列表 (共享状态) */
const subAgentsList = computed(() => subAgents.subAgents.value)

/** 是否在子智能体模式下 (查看子会话) */
const isSubAgentMode = computed(() => subAgents.isChildMode.value)

/** 当前会话标题 */
const currentSessionTitle = computed(() => chat.currentSessionTitle.value)

/** 当前会话状态 (null=无/空闲, 'busy'=正在处理) */
const currentSessionStatus = computed(() => {
  const sid = chat.currentSessionId.value
  if (!sid) return null
  return streaming.sessionStatus.value[sid] || null
})

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
  if (USE_MOCK_DATA) return null // mock 模式跳过状态检查
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

  return groupMessagesByDate(msgs)
})

/** Mock 消息分组 */
const mockMessageGroups = computed<MessageGroup[]>(() => {
  if (!USE_MOCK_DATA) return []
  return groupMessagesByDate(MOCK_MESSAGES)
})

/** 实际显示的消息分组 (mock 或真实) */
const displayMessageGroups = computed<MessageGroup[]>(() => {
  return USE_MOCK_DATA ? mockMessageGroups.value : messageGroups.value
})

/** 将消息数组按日期分组 */
function groupMessagesByDate(msgs: ChatMessage[]): MessageGroup[] {
  const groups: MessageGroup[] = []
  let currentDate = ''
  let currentGroup: ChatMessage[] = []

  for (const msg of msgs) {
    const dateStr = getMessageDate(msg)
    if (dateStr !== currentDate) {
      if (currentGroup.length > 0) {
        groups.push({ dateLabel: currentDate, messages: currentGroup })
      }
      currentDate = dateStr
      currentGroup = [msg]
    } else {
      currentGroup.push(msg)
    }
  }

  if (currentGroup.length > 0) {
    groups.push({ dateLabel: currentDate, messages: currentGroup })
  }

  return groups
}

// ==================== Token 和会话工具函数 ====================

/** 格式化 Token 数量显示 (>=10000 显示为 "X万") */
function formatTokenDisplay(n: number): string {
  if (!n || n < 10000) return String(n || 0)
  return Math.round(n / 10000) + '万'
}

/** 截断会话 ID 为前12位 + ... */
function truncateSessionId(id: string): string {
  if (id.length <= 14) return id
  return id.slice(0, 12) + '...'
}

/** 复制会话 ID 到剪贴板 */
async function copySessionId(): Promise<void> {
  try {
    await navigator.clipboard.writeText(chat.currentSessionId.value)
    copiedSessionId.value = true
    setTimeout(() => {
      copiedSessionId.value = false
    }, 2000)
  } catch {
    // 静默失败
  }
}

// ==================== 消息工具函数 ====================

/** 获取消息角色 (真实数据) */
function getMessageRole(msg: ChatMessage): 'ai' | 'user' {
  // 优先用显式 role 字段
  const role = msg.info?.role || msg.role
  if (role === 'assistant') return 'ai'
  if (role === 'user') return 'user'

  // 兜底：有 parts 无 content = assistant；有 content 无 parts = user
  if (msg.parts && msg.parts.length > 0 && !msg.content && !msg.text) return 'ai'
  if ((msg.content || msg.text) && (!msg.parts || msg.parts.length === 0)) return 'user'

  // 最后一层：如果有工具 parts（tool/tool_call），必然是 assistant
  if (msg.parts?.some(p => p.type === 'tool' || p.type === 'tool_call')) return 'ai'

  return 'ai'
}

/** 获取显示消息角色 (兼容 mock 和真实数据) */
function getDisplayMessageRole(msg: ChatMessage): 'ai' | 'user' {
  if (USE_MOCK_DATA) {
    const role = msg.info?.role || msg.role
    return role === 'assistant' ? 'ai' : 'user'
  }
  return getMessageRole(msg)
}

/** 发送消息 */
async function handleSend(text: string, files: File[]): Promise<void> {
  if (USE_MOCK_DATA) return // mock 模式不发送
  await chat.sendMessage(text, files)
}

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

/** 监听消息变化, 自动滚动到底部 */
let _lastScrollSessionId = ''
watch(
  () => messages.value.length,
  (newLen, oldLen) => {
    const sid = chat.currentSessionId.value
    const isSessionSwitch = sid !== _lastScrollSessionId
    if (isSessionSwitch) {
      _lastScrollSessionId = sid
      scrollToBottom(false) // 会话切换用 instant
    } else if (oldLen === 0 && newLen > 0) {
      scrollToBottom(false) // 初始加载用 instant
    } else if (newLen > 0) {
      scrollToBottom()      // 后续追加用 smooth
    }
  },
)

/** 监听流式状态变化, 滚动到底部 */
watch(isStreaming, (val) => {
  if (val) {
    scrollToBottom(false)
  }
})

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

/** 重试加载 */
async function handleRetry(): Promise<void> {
  await chat.loadSessions()
  if (chat.currentSessionId.value) {
    await chat.loadChatHistory(chat.currentSessionId.value)
  }
}

/** 加载子智能体列表 */
async function loadSubAgents(): Promise<void> {
  await subAgents.loadSubAgents(chat.currentSessionId.value, chat.messages.value)
}

/** 点击子智能体按钮：先静默加载，完成后直接显示列表 */
async function handleShowSubAgents(): Promise<void> {
  await loadSubAgents()
  showSubAgentsList.value = true
}

/** 返回父会话 */
async function handleBackToParent(): Promise<void> {
  await subAgents.returnToParent()
}

/** 选择子智能体，进入子会话 */
async function handleSelectSubAgent(childSessionId: string): Promise<void> {
  showSubAgentsList.value = false
  await subAgents.enterSubAgent(childSessionId)
}

// ==================== 生命周期 ====================

onMounted(async () => {
  // 初始化流式消息系统 (注入 messages/activeSessionId refs)
  chat.initStreaming()

  if (USE_MOCK_DATA) {
    scrollToBottom(false)
    return
  }
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
}

/* 会话顶栏 */
.session-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 16px;
  cursor: pointer;
  border-bottom: 0.5px solid var(--border);
  flex-shrink: 0;
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

/* 子智能体模式顶栏 */
.subagent-mode {
  justify-content: space-between;
}

.back-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  background: none;
  border: none;
  color: var(--primary);
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  padding: 4px 0;
}

.back-btn:active {
  opacity: 0.7;
}

/* 顶栏按钮行 */
.session-bar-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.subagent-btn {
  color: var(--primary);
  background: rgba(10, 132, 255, 0.1);
}

.subagent-btn:active {
  background: var(--primary) !important;
  color: #fff !important;
}

/* 会话状态指示器 */
.session-status-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 16px;
  font-size: 12px;
  color: var(--text3);
  background: var(--surface);
  flex-shrink: 0;
}
.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  display: inline-block;
}
.status-dot.busy {
  background: var(--accent3);
  animation: statusPulse 1.5s infinite;
}

/* PC 会话标题栏 */
.pc-session-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 6px 16px;
  font-size: 12px;
  color: var(--text2);
  background: var(--surface);
  flex-shrink: 0;
  border-bottom: 1px solid var(--border);
}
.pc-session-title {
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 6px;
}
.pc-session-title .status-dot {
  display: inline-block;
}
.pc-session-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}
.session-token-usage {
  display: flex;
  align-items: center;
  gap: 4px;
  color: var(--text3);
}
.session-id-copy {
  display: flex;
  align-items: center;
  gap: 4px;
  background: none;
  border: none;
  cursor: pointer;
  color: var(--text4);
  padding: 2px 6px;
  border-radius: 4px;
  transition: color 0.15s, background 0.15s;
}
.session-id-copy:hover {
  color: var(--text2);
  background: var(--surface2);
}
.session-id-copy code {
  font-family: 'SF Mono', 'Cascadia Code', 'Consolas', monospace;
  font-size: 10px;
  background: transparent;
  padding: 0;
}
.copied-check {
  display: flex;
  align-items: center;
}
@keyframes statusPulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

/* 消息列表 */
.chat-msgs {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  -webkit-overflow-scrolling: touch;
}

/* 日期分隔 - 轻量居中标签 */
.chat-date {
  font-size: 12px;
  color: var(--text3);
  text-align: center;
  margin: 16px 0 12px;
  font-weight: 500;
}

/* ==================== PC 样式覆盖 ==================== */
  @media (min-width: 768px) {
    #page-chat {
      padding: 0;  /* PC 上无内边距 - 由 pc-main 处理 */
    }
    .chat-msgs {
      width: 100%;
      max-width: 1200px;
      margin: 0 auto;
      padding: 16px 24px;
    }
  .chat-date {
    margin: 20px 0 16px;
    font-size: 13px;
  }
}
</style>
