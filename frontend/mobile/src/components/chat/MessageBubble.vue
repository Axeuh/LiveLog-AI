<template>
  <div class="message" :class="role">
    <!-- 头像 -->
    <div class="avatar" :class="role">
      {{ role === 'ai' ? 'AI' : '我' }}
    </div>

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
      <!-- 用户消息: 纯文本, 不渲染 markdown -->
      <template v-else>{{ messageText }}</template>

      <!-- 时间戳 -->
      <div v-if="formattedTime" class="msg-time">{{ formattedTime }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import MarkdownContent from './MarkdownContent.vue'
import ReasoningBlock from './ReasoningBlock.vue'
import ToolCardMini from './ToolCardMini.vue'
import type { ChatMessage } from '@/types'

const props = defineProps<{
  message: ChatMessage
  role: 'ai' | 'user'
}>()

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

/** 将 part 的工具状态映射为 ToolCardMini 的三态 */
function mapStreamStatus(part: { state?: { status?: string } }): 'running' | 'completed' | 'error' {
  const s = part.state?.status
  if (s === 'completed' || s === 'done' || s === 'success') return 'completed'
  if (s === 'error' || s === 'failed') return 'error'
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
  margin-bottom: 14px;
  gap: 10px;
}

.message.ai {
  align-items: start;
}

.message.user {
  flex-direction: row-reverse;
}

/* 头像 */
.avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 15px;
  font-weight: 700;
}

.avatar.ai {
  background: linear-gradient(135deg, var(--primary), #8b7cf7);
  color: #fff;
}

.avatar.user {
  background: var(--surface3);
  color: var(--text2);
}

/* 气泡 */
.bubble {
  max-width: 80%;
  padding: 10px 14px;
  border-radius: 16px;
  font-size: 14px;
  line-height: 1.5;
  word-break: break-word;
}

.message.ai .bubble {
  background: var(--surface2);
  border-bottom-left-radius: 4px;
}

.message.user .bubble {
  background: var(--primary);
  color: #fff;
  border-bottom-right-radius: 4px;
}

/* 消息时间 */
.msg-time {
  font-size: 9px;
  color: var(--text3);
  margin-top: 2px;
  text-align: right;
  opacity: 0.7;
}

.message.user .msg-time {
  color: rgba(255, 255, 255, 0.5);
}
</style>
