<template>
  <div class="file-list">
    <div v-if="loading" class="file-list__loading">
      <LoadingSpinner size="sm" text="加载文件列表..." />
    </div>
    <div v-else-if="files.length === 0" class="file-list__empty">
      <i class="fas fa-folder-open"></i>
      <span>当前目录为空</span>
    </div>
    <div v-else class="file-list__rows">
      <div
        v-for="entry in files"
        :key="entry.name"
        class="file-row"
        @click="handleClick(entry)"
      >
        <span class="file-row__icon">
          <i v-if="entry.type === 'dir'" class="fas fa-folder" style="color: var(--primary)"></i>
          <i v-else class="fas" :class="getFileIconClass(entry.name)"></i>
        </span>
        <span class="file-row__name">{{ entry.name }}</span>
        <span class="file-row__meta">
          <span v-if="entry.size != null" class="file-row__size">{{ formatSize(entry.size) }}</span>
          <span v-if="entry.modified_at" class="file-row__date">{{ formatDate(entry.modified_at) }}</span>
        </span>
        <span v-if="entry.type === 'dir'" class="file-row__chevron">
          <i class="fas fa-chevron-right"></i>
        </span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { FileEntry } from '@/types'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'

defineProps<{
  files: FileEntry[]
  loading: boolean
  parentPath?: string
}>()

const emit = defineEmits<{
  preview: [entry: FileEntry, path: string]
  navigate: [path: string]
}>()

function getFileIconClass(name: string): string {
  const lower = name.toLowerCase()
  // 图片
  if (lower.match(/\.(jpg|jpeg|png|gif|webp|bmp|svg|ico)$/)) return 'fa-file-image'
  // 文本
  if (lower.match(/\.(md|txt|log)$/)) return 'fa-file-alt'
  // 代码/数据
  if (lower.match(/\.(json|jsonl|yaml|yml|toml|ini|cfg|conf)$/)) return 'fa-file-code'
  // 音频
  if (lower.match(/\.(mp3|wav|ogg|m4a|aac|flac|wma)$/)) return 'fa-file-audio'
  // 视频
  if (lower.match(/\.(mp4|avi|mkv|mov|wmv|flv)$/)) return 'fa-file-video'
  // 代码文件
  if (lower.match(/\.(js|ts|tsx|jsx|vue|html|css|scss|kt|java|py|go|rs|c|cpp|h|hpp|rb|php|sh|bash|ps1|sql)$/)) return 'fa-file-code'
  // PDF
  if (lower.endsWith('.pdf')) return 'fa-file-pdf'
  // 压缩包
  if (lower.match(/\.(zip|rar|7z|tar|gz)$/)) return 'fa-file-archive'
  // Office
  if (lower.match(/\.(doc|docx|xls|xlsx|ppt|pptx)$/)) return 'fa-file-word'
  // 默认
  return 'fa-file'
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
  return (bytes / (1024 * 1024 * 1024)).toFixed(1) + ' GB'
}

function formatDate(isoStr: string): string {
  try {
    const d = new Date(isoStr)
    if (isNaN(d.getTime())) return isoStr
    const now = new Date()
    const isThisYear = d.getFullYear() === now.getFullYear()
    const m = (d.getMonth() + 1).toString().padStart(2, '0')
    const day = d.getDate().toString().padStart(2, '0')
    if (isThisYear) {
      return m + '-' + day
    }
    return d.getFullYear() + '-' + m + '-' + day
  } catch {
    return isoStr
  }
}

function handleClick(entry: FileEntry): void {
  if (entry.type === 'dir') {
    emit('navigate', entry.name)
  } else {
    emit('preview', entry, entry.name)
  }
}
</script>

<style scoped>
.file-list {
  flex: 1;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
}

.file-list__loading {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 0;
}

.file-list__empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 60px 0;
  font-size: 14px;
  color: var(--text3);
}

.file-list__empty i {
  font-size: 32px;
  opacity: 0.4;
}

.file-list__rows {
  padding: 0;
}

.file-row {
  display: flex;
  align-items: center;
  height: 44px;
  padding: 0 16px;
  cursor: pointer;
  border-bottom: 0.5px solid var(--border);
  transition: background 0.12s;
  gap: 12px;
}

.file-row:active {
  background: var(--surface2);
}

.file-row__icon {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 18px;
  color: var(--text3);
}

.file-row__icon .fa-folder {
  color: var(--primary);
}

.file-row__icon .fa-file-image {
  color: var(--accent2);
}

.file-row__icon .fa-file-audio {
  color: var(--accent3);
}

.file-row__icon .fa-file-video {
  color: var(--primary-light);
}

.file-row__icon .fa-file-code {
  color: var(--accent);
}

.file-row__icon .fa-file-alt {
  color: var(--primary-light);
}

.file-row__icon .fa-file-pdf {
  color: var(--danger);
}

.file-row__icon .fa-file-archive {
  color: var(--accent3);
}

.file-row__name {
  flex: 1;
  font-size: 15px;
  font-weight: 400;
  color: var(--text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}

.file-row__meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
  font-size: 12px;
  color: var(--text3);
  font-variant-numeric: tabular-nums;
}

.file-row__size {
  min-width: 48px;
  text-align: right;
}

.file-row__date {
  min-width: 44px;
  text-align: right;
}

.file-row__chevron {
  width: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 11px;
  color: var(--text3);
  opacity: 0.6;
}
</style>
