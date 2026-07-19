<template>
  <div class="preview-code">
    <div class="preview-code__header">
      <span class="preview-code__lang">{{ language || 'text' }}</span>
      <span class="preview-code__name">{{ fileName }}</span>
    </div>
    <div class="preview-code__body line-numbers" v-html="addLineNumbers(content)"></div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

defineProps<{
  content: string
  language: string
  fileName: string
}>()

/** HTML 转义 */
function escapeHtml(str: string): string {
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

/** 纯文本添加行号 */
function addLineNumbers(text: string): string {
  if (!text) return ''
  const safe = escapeHtml(text)
  const lines = safe.split('\n')
  const w = Math.max(2, String(lines.length).length)
  return lines.map(line => {
    return `<span class="code-line" style="--ln-w:${w}ch">${line}</span>`
  }).join('')
}
</script>

<style scoped>
.preview-code {
  display: flex;
  flex-direction: column;
}

.preview-code__header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-bottom: none;
  border-radius: var(--radius-sm) var(--radius-sm) 0 0;
}

.preview-code__lang {
  font-size: 11px;
  font-weight: 600;
  color: var(--primary-light);
  text-transform: uppercase;
  padding: 2px 6px;
  background: rgba(10, 132, 255, 0.15);
  border-radius: 4px;
}

.preview-code__name {
  font-size: 12px;
  color: var(--text2);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 行号代码块 */
.preview-code__body {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 0 0 var(--radius-sm) var(--radius-sm);
  padding: 16px 0;
  overflow-x: auto;
  font-size: 12px;
  line-height: 1.5;
  scrollbar-width: thin;
  scrollbar-color: rgba(255, 255, 255, 0.15) transparent;
  white-space: pre-wrap;
  word-break: break-word;
  overflow-wrap: break-word;
}
.preview-code__body::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
.preview-code__body::-webkit-scrollbar-track {
  background: transparent;
}
.preview-code__body::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.15);
  border-radius: 3px;
}
.preview-code__body::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.3);
}

:deep(.code-line) {
  display: block;
  padding: 0 16px 0 0;
  white-space: pre-wrap;
  word-break: break-word;
}
:deep(.code-line::before) {
  content: counter(code-line);
  counter-increment: code-line;
  display: inline-block;
  width: var(--ln-w, 3ch);
  padding: 0 12px 0 4px;
  margin-right: 12px;
  color: var(--text3);
  text-align: right;
  user-select: none;
  border-right: 2px solid var(--border);
}
.preview-code__body.line-numbers {
  counter-reset: code-line;
}
</style>
