<template>
  <div class="streaming-text">
    <!-- 所有文本 parts 合并为一块连续渲染 -->
    <MarkdownContent v-if="mergedText" :content="mergedText" />

    <!-- 非文本部分: 按顺序渲染 -->
    <template v-for="(part, index) in nonTextParts" :key="index">
      <ReasoningBlock
        v-if="part.type === 'reasoning' || part.type === 'thought'"
        :content="part.text || ''"
        label="思考过程"
        :collapsed="true"
      />
      <ToolCardMini
        v-else-if="part.type === 'tool_call' || part.type === 'tool'"
        :tool="mapToToolCall(part)"
        :status="mapToolStatus(part)"
      />
      <ReasoningBlock
        v-else-if="part.type === 'tool_result'"
        :content="part.text || ''"
        label="工具结果"
        :collapsed="true"
      />
    </template>

    <!-- 流式光标 - 紧跟文本末尾 -->
    <span v-if="isStreaming" class="streaming-cursor">|</span>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import MarkdownContent from './MarkdownContent.vue'
import ReasoningBlock from './ReasoningBlock.vue'
import ToolCardMini from './ToolCardMini.vue'
import type { ToolCall } from './ToolCardMini.vue'
import type { MessagePart } from '@/types'

const props = defineProps<{
  parts: MessagePart[]
  isStreaming: boolean
}>()

/** 合并所有文本 parts 为连续文本 (源数据, 每 delta 更新) */
const rawMergedText = computed(() => {
  const texts = props.parts.filter((p) => p.type === 'text' && p.text)
  return texts.map((p) => p.text).join('')
})

/**
 * 防抖后的展示文本 — 使用 requestAnimationFrame 节流,
 * 避免每字符 delta 都触发完整 markdown 重渲染
 */
const displayedText = ref('')
let _rafId: number | null = null

watch(rawMergedText, (val) => {
  if (_rafId !== null) {
    cancelAnimationFrame(_rafId)
  }
  _rafId = requestAnimationFrame(() => {
    displayedText.value = val
    _rafId = null
  })
})

// 首次赋值 (streaming 开始时立即显示)
if (rawMergedText.value) {
  displayedText.value = rawMergedText.value
}

/** 防抖后的文本 (给模板用) */
const mergedText = displayedText

/** 非文本 parts (按原始顺序) */
const nonTextParts = computed(() => {
  return props.parts.filter((p) => p.type !== 'text')
})

/** 将 MessagePart 映射为 ToolCardMini 所需的 ToolCall */
function mapToToolCall(part: MessagePart): ToolCall {
  return {
    id: part.tool || 'tool',
    name: part.tool || 'tool',
    args: part.state?.input || {},
    status: part.state?.status || 'running',
    output: part.state?.output,
  }
}

/** 将 MessagePart 的工具状态映射为 ToolCardMini 的三态 */
function mapToolStatus(
  part: MessagePart
): 'running' | 'completed' | 'error' {
  const s = part.state?.status
  if (s === 'completed' || s === 'done' || s === 'success') return 'completed'
  if (s === 'error' || s === 'failed') return 'error'
  return 'running'
}
</script>

<style scoped>
.streaming-text {
  line-height: 1.6;
}

.streaming-cursor {
  display: inline-block;
  animation: blink 1s step-end infinite;
  color: var(--text3);
  margin-left: 2px;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}
</style>
