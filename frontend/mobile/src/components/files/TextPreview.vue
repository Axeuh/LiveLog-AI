<template>
  <!-- Markdown 预览 (保持原样, 无行号) -->
  <div v-if="fileType === 'md'" class="preview-text-md md-content" v-html="content"></div>

  <!-- JSON 预览 (纯文本+行号, 不格式化) -->
  <div v-else-if="fileType === 'json'" class="preview-text-lines line-numbers" v-html="addLineNumbers(content)"></div>

  <!-- 文本预览 (code, txt, log 等带行号+自动换行) -->
  <div v-else-if="fileType === 'text'" class="preview-text-lines line-numbers" v-html="addLineNumbers(content)"></div>

  <!-- JSONL 预览 -->
  <div v-else-if="fileType === 'jsonl'" class="preview-text-jsonl">
    <div v-if="jsonlLines.length === 0" class="preview-state preview-state--empty">
      <i class="fas fa-file-code"></i>
      <span class="preview-state__text">文件内容为空</span>
    </div>
    <div v-else class="jsonl-list">
      <div
        v-for="(line, idx) in jsonlLines"
        :key="idx"
        class="jsonl-item"
        :class="{ 'jsonl-item--expanded': expandedLines.has(idx) }"
      >
        <div class="jsonl-item__header" @click="toggleJsonlLine(idx)">
          <span class="jsonl-item__num">{{ idx + 1 }}</span>
          <span class="jsonl-item__type" :class="'jsonl-type--' + getJsonlType(line)">
            {{ getJsonlType(line) }}
          </span>
          <span class="jsonl-item__preview">{{ getJsonlPreview(line) }}</span>
          <i class="fas fa-chevron-right jsonl-item__arrow" :class="{ rotated: expandedLines.has(idx) }"></i>
        </div>
        <Transition name="jsonl-expand">
          <div v-if="expandedLines.has(idx)" class="jsonl-item__detail">
            <pre class="jsonl-item__json json-highlight" v-html="highlightJsonl(line)"></pre>
          </div>
        </Transition>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

type TextFileType = 'md' | 'json' | 'jsonl' | 'text'

const props = defineProps<{
  content: string
  fileType: TextFileType
  fileName: string
}>()

/** 从 JSONL 文本解析出的对象数组 */
const jsonlLines = computed<Record<string, unknown>[]>(() => {
  if (props.fileType !== 'jsonl' || !props.content) return []
  return props.content
    .split('\n')
    .filter(line => line.trim())
    .map(line => {
      try {
        return JSON.parse(line) as Record<string, unknown>
      } catch {
        return { _raw: line } as Record<string, unknown>
      }
    })
})

/** 已展开的 JSONL 条目索引 */
const expandedLines = ref<Set<number>>(new Set())

/** 切换 JSONL 条目展开/折叠 */
function toggleJsonlLine(idx: number): void {
  const newSet = new Set(expandedLines.value)
  if (newSet.has(idx)) {
    newSet.delete(idx)
  } else {
    newSet.add(idx)
  }
  expandedLines.value = newSet
}

/** 获取 JSONL 条目类型标签 */
function getJsonlType(obj: Record<string, unknown>): string {
  if (obj.type && typeof obj.type === 'string') return obj.type
  if (obj.source && typeof obj.source === 'string') return obj.source
  if (obj.event && typeof obj.event === 'string') return obj.event
  return 'data'
}

/** 获取 JSONL 条目预览文本 */
function getJsonlPreview(obj: Record<string, unknown>): string {
  for (const key of ['text', 'content', 'summary', 'message', 'name']) {
    if (obj[key] && typeof obj[key] === 'string') {
      const val = obj[key] as string
      return val.length > 80 ? val.slice(0, 80) + '...' : val
    }
  }
  for (const val of Object.values(obj)) {
    if (typeof val === 'string' && val.length > 0) {
      return val.length > 80 ? val.slice(0, 80) + '...' : val
    }
  }
  return '{...}'
}

/** HTML 转义防止 XSS */
function escapeHtml(str: string): string {
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

/** 对格式化后的 JSON 字符串添加语法高亮和行号 */
function highlightJsonString(formatted: string): string {
  const safe = escapeHtml(formatted)
  return safe.split('\n').map(line => {
    const highlighted = line
      // 键名: "key":
      .replace(/^(\s*)"([^"]+)"(\s*):/g, '$1<span class="json-key">"$2"</span>$3:')
      // 冒号后的字符串值
      .replace(/:(\s*)"((?:[^"\\]|\\.)*)"/g, ':<span class="json-string">$1"$2"</span>')
      // 数组中的独立字符串
      .replace(/^(\s*)"((?:[^"\\]|\\.)*)"(\s*[,\]]?)$/g, '$1<span class="json-string">"$2"</span>$3')
      // 冒号后的数字
      .replace(/:\s*(-?\d+\.?\d*(?:[eE][+-]?\d+)?)/g, ': <span class="json-number">$1</span>')
      // 数组中的独立数字
      .replace(/^(\s*)(-?\d+\.?\d*(?:[eE][+-]?\d+)?)(\s*[,\]]?)$/g, '$1<span class="json-number">$2</span>$3')
      // 冒号后的布尔值
      .replace(/:\s*(true|false)/g, ': <span class="json-boolean">$1</span>')
      // 数组中的独立布尔值
      .replace(/^(\s*)(true|false)(\s*[,\]]?)$/g, '$1<span class="json-boolean">$2</span>$3')
      // 冒号后的 null
      .replace(/:\s*(null)/g, ': <span class="json-null">$1</span>')
      // 数组中的独立 null
      .replace(/^(\s*)(null)(\s*[,\]]?)$/g, '$1<span class="json-null">$2</span>$3')
    return '<span class="json-line">' + highlighted + '</span>'
  }).join('')
}

/** 给纯文本添加行号 (用于 text/json 文件) */
function addLineNumbers(text: string): string {
  if (!text) return ''
  const safe = escapeHtml(text)
  const lines = safe.split('\n')
  const w = Math.max(2, String(lines.length).length)
  return lines.map(line => {
    return `<span class="code-line" style="--ln-w:${w}ch">${line}</span>`
  }).join('')
}

/** 高亮 JSONL 条目对象 */
function highlightJsonl(obj: Record<string, unknown>): string {
  try {
    const formatted = JSON.stringify(obj, null, 2)
    return highlightJsonString(formatted)
  } catch {
    return escapeHtml(String(obj))
  }
}

/** 给纯文本添加行号 (用于 code/txt/log 等非 JSON 文件) */
</script>

<style scoped>
/* 空状态 */
.preview-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  gap: 12px;
}

.preview-state i {
  font-size: 32px;
  color: var(--text3);
}

.preview-state__text {
  font-size: 14px;
  color: var(--text2);
  text-align: center;
}

/* Markdown 预览 (无行号) */
.preview-text-md {
  font-size: 14px;
  line-height: 1.7;
  color: var(--text);
}

/* JSON 预览 + 通用行号文本 */
.preview-text-json {
  font-size: 13px;
  line-height: 1.6;
}

.preview-text-lines {
  font-family: 'Plus Jakarta Sans', 'SF Mono', 'Consolas', monospace;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  overflow-wrap: break-word;
}

/* 行号通用样式 (JSON + 文本共用) */
.line-numbers {
  counter-reset: code-line;
  white-space: pre-wrap;
  word-break: break-word;
  overflow-wrap: break-word;
  font-family: 'Plus Jakarta Sans', 'SF Mono', 'Consolas', monospace;
  font-size: 12px;
  line-height: 1.6;
}
:deep(.code-line), :deep(.json-line) {
  display: block;
  counter-increment: code-line;
  padding: 0 4px;
}
:deep(.code-line::before), :deep(.json-line::before) {
  content: counter(code-line);
  display: inline-block;
  width: var(--ln-w, 3ch);
  padding: 0 8px 0 2px;
  margin-right: 6px;
  color: var(--text3);
  text-align: right;
  user-select: none;
  border-right: 2px solid var(--border);
}

.preview-text-json :deep(pre) {
  background: var(--surface2);
  border-radius: var(--radius-sm);
  padding: 14px;
  overflow-x: auto;
  font-size: 12px;
  line-height: 1.5;
  scrollbar-width: thin;
  scrollbar-color: rgba(255, 255, 255, 0.15) transparent;
}
.preview-text-json :deep(pre::-webkit-scrollbar) {
  width: 6px;
  height: 6px;
}
.preview-text-json :deep(pre::-webkit-scrollbar-track) {
  background: transparent;
}
.preview-text-json :deep(pre::-webkit-scrollbar-thumb) {
  background: rgba(255, 255, 255, 0.15);
  border-radius: 3px;
}
.preview-text-json :deep(pre::-webkit-scrollbar-thumb:hover) {
  background: rgba(255, 255, 255, 0.3);
}

/* JSONL 列表 */
.preview-text-jsonl {
  padding-bottom: 20px;
}

.jsonl-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.jsonl-item {
  background: var(--surface);
  border-radius: var(--radius-sm);
  overflow: hidden;
  border: 1px solid var(--border);
  transition: border-color 0.15s;
}

.jsonl-item:hover {
  border-color: var(--surface3);
}

.jsonl-item__header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  cursor: pointer;
  transition: background 0.1s;
}

.jsonl-item__header:active {
  background: var(--surface2);
}

.jsonl-item__num {
  font-size: 11px;
  color: var(--text3);
  font-family: 'Plus Jakarta Sans', monospace;
  min-width: 28px;
  text-align: right;
  flex-shrink: 0;
}

.jsonl-item__type {
  font-size: 10px;
  font-weight: 600;
  padding: 2px 6px;
  border-radius: 4px;
  text-transform: uppercase;
  flex-shrink: 0;
}

/* JSONL 类型标签颜色 */
.jsonl-type--voice { background: rgba(108, 92, 231, 0.2); color: var(--primary-light); }
.jsonl-type--sensor { background: rgba(0, 206, 201, 0.2); color: var(--accent); }
.jsonl-type--app { background: rgba(253, 203, 110, 0.2); color: var(--accent3); }
.jsonl-type--media { background: rgba(253, 121, 168, 0.2); color: var(--accent2); }
.jsonl-type--notify { background: rgba(255, 69, 58, 0.2); color: var(--danger); }
.jsonl-type--input { background: rgba(162, 155, 254, 0.2); color: var(--primary-light); }
.jsonl-type--screen { background: rgba(0, 206, 201, 0.2); color: var(--accent); }
.jsonl-type--data { background: var(--surface2); color: var(--text2); }

.jsonl-item__preview {
  flex: 1;
  font-size: 12px;
  color: var(--text2);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}

.jsonl-item__arrow {
  font-size: 10px;
  color: var(--text3);
  flex-shrink: 0;
  transition: transform 0.2s;
}

.jsonl-item__arrow.rotated {
  transform: rotate(90deg);
}

.jsonl-item__detail {
  border-top: 1px solid var(--border);
  padding: 10px 12px;
  background: var(--bg);
}

.jsonl-item__json {
  margin: 0;
  font-size: 11px;
  line-height: 1.5;
  color: var(--text2);
  font-family: 'Plus Jakarta Sans', monospace;
  white-space: pre-wrap;
  word-break: break-all;
  overflow-x: auto;
  scrollbar-width: thin;
  scrollbar-color: rgba(255, 255, 255, 0.15) transparent;
}
.jsonl-item__json::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
.jsonl-item__json::-webkit-scrollbar-track {
  background: transparent;
}
.jsonl-item__json::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.15);
  border-radius: 3px;
}
.jsonl-item__json::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.3);
}

/* JSONL 展开动画 */
.jsonl-expand-enter-active,
.jsonl-expand-leave-active {
  transition: all 0.2s ease;
  max-height: 500px;
}

.jsonl-expand-enter-from,
.jsonl-expand-leave-to {
  max-height: 0;
  opacity: 0;
  padding-top: 0;
  padding-bottom: 0;
}

/* JSON 语法高亮颜色 (行号复用 .line-numbers 样式) */
.json-highlight {
  font-family: 'Plus Jakarta Sans', 'SF Mono', 'Consolas', monospace;
  font-size: 12px;
  line-height: 1.6;
}
.json-highlight .json-key { color: var(--primary-light); }
.json-highlight .json-string { color: var(--accent); }
.json-highlight .json-number { color: var(--accent3); }
.json-highlight .json-boolean { color: var(--accent2); }
.json-highlight .json-null { color: var(--text3); font-style: italic; }
</style>
