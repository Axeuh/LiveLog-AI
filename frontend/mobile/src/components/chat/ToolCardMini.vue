<template>
  <div class="tool-card-mini" :class="{ expanded: isExpanded }">
    <div class="tcm-header" @click="toggle">
      <span class="tcm-icon"><i class="fas fa-wrench"></i></span>
      <span class="tcm-name">{{ tool.name || 'tool' }}</span>
      <span class="tcm-status" :class="status"></span>
    </div>
    <div class="tcm-body">
      <template v-if="argsPreview">
        <div class="tcm-label">{{ tool.output ? '输入' : '参数' }}</div>
        <pre><code>{{ argsPreview }}</code></pre>
      </template>
      <template v-if="tool.output">
        <div class="tcm-label">输出</div>
        <pre><code>{{ truncatedOutput }}</code></pre>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

/** 工具调用数据 */
export interface ToolCall {
  id: string
  name: string
  args: Record<string, unknown> | string
  status: string
  output?: string
}

const props = defineProps<{
  tool: ToolCall
  status: 'running' | 'completed' | 'error'
  expanded?: boolean
}>()

const isExpanded = ref(props.expanded ?? false)

function toggle() {
  isExpanded.value = !isExpanded.value
}

/** 将 args 格式化为 JSON 字符串 */
const argsPreview = computed<string>(() => {
  const args = props.tool.args
  if (!args) return ''
  if (typeof args === 'string') return args
  try {
    return JSON.stringify(args, null, 2)
  } catch {
    return String(args)
  }
})

/** 截断输出内容 (最长 500 字符) */
const truncatedOutput = computed<string>(() => {
  const output = props.tool.output || ''
  if (output.length <= 500) return output
  return output.slice(0, 500) + '...'
})
</script>

<style scoped>
.tool-card-mini {
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 6px 10px;
  margin: 6px 0;
  background: var(--surface);
}

.tcm-header {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  user-select: none;
}

.tcm-icon {
  color: var(--primary-light);
  font-size: 12px;
  width: 16px;
  text-align: center;
}

.tcm-name {
  flex: 1;
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
}

.tcm-body {
  display: none;
  margin-top: 6px;
  padding-top: 6px;
  border-top: 1px solid var(--border);
  font-size: 12px;
}

.tool-card-mini.expanded .tcm-body {
  display: block;
}

.tcm-body pre {
  background: var(--surface2);
  padding: 8px;
  border-radius: 6px;
  overflow-x: auto;
  margin: 4px 0;
  font-size: 11px;
}

.tcm-body pre code {
  background: none;
  padding: 0;
}

.tcm-label {
  font-size: 10px;
  color: var(--text3);
  margin: 6px 0 2px;
  font-weight: 600;
}

/* 状态指示点 */
.tcm-status {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  display: inline-block;
  flex-shrink: 0;
}

.tcm-status.running {
  background: var(--accent3);
  animation: pulse 1.5s infinite;
}

.tcm-status.completed {
  background: var(--accent);
}

.tcm-status.error {
  background: #ff6b6b;
}

@keyframes pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.4;
  }
}
</style>
