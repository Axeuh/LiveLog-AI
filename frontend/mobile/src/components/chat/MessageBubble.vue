<template>
  <div class="message" :class="role">
    <!-- 气泡 -->
    <div class="bubble">
      <!-- AI 消息: 遍历 parts 渲染 -->
      <template v-if="role === 'ai'">
        <template v-for="(part, pIdx) in messageParts" :key="pIdx">
          <MarkdownContent v-if="part.type === 'text'" :content="part.text || ''" />
          <ReasoningBlock
            v-else-if="part.type === 'reasoning' || part.type === 'thought'"
            :content="part.text || ''"
            label="思考过程"
            :collapsed="true"
          />
          <ToolCardMini
            v-else-if="part.type === 'tool_call' || part.type === 'tool' || part.type === 'tool_result'"
            :tool="{
              id: part.tool || 'tool',
              name: part.tool || 'tool',
              args: part.state?.input || {},
              status: part.state?.status || 'completed',
              output: part.state?.output || part.text,
            }"
            :status="mapStreamStatus(part)"
          />
        </template>
      </template>
      <!-- 用户消息: 纯文本, 不渲染 markdown, 过长自动折叠 -->
      <template v-else>
        <div
          class="user-text"
          :class="{ collapsed: isLong && !userExpanded }"
          @click="userExpanded = !userExpanded"
        >
          {{ messageText }}
        </div>
        <button
          v-if="isLong"
          class="user-expand-btn"
          @click="userExpanded = !userExpanded"
        >
          {{ userExpanded ? '收起' : '展开全部' }}
        </button>
      </template>

      <!-- 时间戳 - 轻量标签 -->
      <div v-if="formattedTime" class="msg-time">{{ formattedTime }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import MarkdownContent from './MarkdownContent.vue'
import ReasoningBlock from './ReasoningBlock.vue'
import ToolCardMini from './ToolCardMini.vue'
import type { ChatMessage } from '@/types'

const USER_COLLAPSE_LIMIT = 200

const props = defineProps<{
  message: ChatMessage
  role: 'ai' | 'user'
}>()

const userExpanded = ref(false)

/** 获取消息的全部 parts (用于 AI 消息) */
const messageParts = computed(() => {
  return props.message.parts || []
})

/** 获取消息文本内容 (仅纯文本, 工具调用由各组件渲染) */
const messageText = computed<string>(() => {
  const msg = props.message
  if (msg.parts && msg.parts.length > 0) {
    const textParts = msg.parts.filter((p) => p.type === 'text' && p.text)
    if (textParts.length > 0) {
      return textParts.map((p) => p.text).join('')
    }
  }
  return msg.content || msg.text || ''
})

/** 用户消息是否过长需要折叠 */
const isLong = computed(() => messageText.value.length > USER_COLLAPSE_LIMIT)

/** 将 part 的工具状态映射为 ToolCardMini 的三态 */
function mapStreamStatus(part: { state?: { status?: string } }): 'running' | 'completed' | 'error' {
  const s = part.state?.status
  if (s === 'completed' || s === 'done' || s === 'success') return 'completed'
  if (s === 'error' || s === 'failed') return 'error'
  if (s === 'running' || s === 'working' || s === 'pending') return 'running'
  return 'completed'
}

/** 格式化消息时间 (HH:MM) */
const formattedTime = computed<string>(() => {
  const ts = props.message.timestamp || props.message.created_at
  if (!ts) return ''
  try {
    const date = new Date(ts)
    if (isNaN(date.getTime())) return ''
    const h = date.getHours().toString().padStart(2, '0')
    const m = date.getMinutes().toString().padStart(2, '0')
    return h + ':' + m
  } catch {
    return ''
  }
})
</script>

<style scoped>
.message {
  display: flex;
  margin-bottom: 4px;
}

/* 手机: AI 消息满宽, 不留右边界 */
.message.ai {
  justify-content: flex-start;
  padding: 0 0 0 4px;
}

/* 手机: 用户消息右对齐, 减少左留白 */
.message.user {
  justify-content: flex-end;
  padding: 0 4px 0 4px;
}

/* PC 上增加气泡边距 */
@media (min-width: 768px) {
  .message {
    padding: 0 24px !important;
  }
}

/* 气泡 - iMessage 风格 */
.bubble {
  padding: 12px 16px;
  font-size: 15px;
  line-height: 1.45;
  word-break: break-word;
  position: relative;
}

/* 手机: AI 气泡满宽 */
.message.ai .bubble {
  max-width: 100%;
  background: var(--surface2);
  color: var(--text);
  border-radius: 18px 18px 18px 4px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
}

/* 手机: 用户气泡 85% 宽度, 略微留白 */
.message.user .bubble {
  max-width: 85%;
  background: var(--primary);
  color: #fff;
  border-radius: 18px 18px 4px 18px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
}

/* 用户长文本折叠 */
.user-text.collapsed {
  max-height: 4.2em;
  overflow: hidden;
  position: relative;
}
.user-text.collapsed::after {
  content: '';
  position: absolute;
  bottom: 0;
  right: 0;
  width: 60%;
  height: 1.4em;
  background: linear-gradient(to right, transparent, var(--primary));
  pointer-events: none;
}
.user-text:not(.collapsed) {
  max-height: none;
}

.user-expand-btn {
  display: block;
  background: none;
  border: none;
  color: rgba(255, 255, 255, 0.7);
  font-size: 12px;
  padding: 2px 0 0;
  margin-top: 2px;
  cursor: pointer;
  text-align: right;
  width: 100%;
}
.user-expand-btn:active {
  color: #fff;
}

/* PC 上气泡宽度限制恢复 70% */
@media (min-width: 768px) {
  .message.ai .bubble {
    max-width: 70% !important;
  }
  .message.user .bubble {
    max-width: 70% !important;
  }
}

/* 时间标签 - 轻量显示在气泡底部 */
.msg-time {
  font-size: 11px;
  color: var(--text3);
  margin-top: 4px;
  text-align: right;
  opacity: 0.6;
}

.message.user .msg-time {
  color: rgba(255, 255, 255, 0.5);
}

/* 连续消息间距优化: 同角色连续消息减少间距 */
.message + .message {
  margin-top: 2px;
}

.message + .message.ai,
.message + .message.user {
  margin-top: 2px;
}

/* 不同角色切换时增加间距 */
.message.ai + .message.user,
.message.user + .message.ai {
  margin-top: 12px;
}
</style>
