<template>
  <div class="search-result-item" @click="handleClick">
    <div class="search-result-item__icon">
      <i v-if="isFolder" class="fas fa-folder" style="color:var(--accent3)"></i>
      <i v-else class="fas" :class="fileIconClass"></i>
    </div>
    <div class="search-result-item__info">
      <div class="search-result-item__name">{{ entry.name }}</div>
      <div class="search-result-item__path">{{ displayPath }}</div>
    </div>
    <div v-if="entry.size != null" class="search-result-item__size">
      {{ formatSize(entry.size) }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { FileEntry } from '@/types'

const props = defineProps<{
  /** 文件条目 */
  entry: FileEntry
  /** 文件完整路径 */
  path?: string
}>()

const emit = defineEmits<{
  /** 点击条目 */
  'click': [entry: FileEntry, path: string]
}>()

const isFolder = computed(() => props.entry.type === 'dir')

function getFileIconClass(name: string): string {
  const lower = name.toLowerCase()
  if (lower.match(/\.(png|jpg|jpeg|gif|bmp|webp|svg|ico)$/)) return 'fa-file-image'
  if (lower.match(/\.(mp3|wav|ogg|m4a|aac|flac|wma)$/)) return 'fa-file-audio'
  if (lower.match(/\.(mp4|avi|mkv|mov|wmv|flv)$/)) return 'fa-file-video'
  if (lower.match(/\.(md|txt|log|jsonl?)$/)) return 'fa-file-alt'
  if (lower.match(/\.(js|ts|tsx|jsx|vue|html|css|scss|kt|java|py|go|rs)$/)) return 'fa-file-code'
  if (lower.match(/\.(pdf)$/)) return 'fa-file-pdf'
  if (lower.match(/\.(zip|rar|7z|tar|gz)$/)) return 'fa-file-archive'
  if (lower.match(/\.(doc|docx|xls|xlsx|ppt|pptx)$/)) return 'fa-file-word'
  return 'fa-file'
}

const fileIconClass = computed(() => getFileIconClass(props.entry.name))

const displayPath = computed(() => {
  if (!props.path) return ''
  // 显示父目录路径
  const parts = props.path.split('/')
  parts.pop() // 移除文件名
  return parts.join('/') || '/'
})

function formatSize(bytes: number): string {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

function handleClick(): void {
  emit('click', props.entry, props.path || '')
}
</script>

<style scoped>
.search-result-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  cursor: pointer;
  border-radius: var(--radius-sm);
  transition: background 0.1s;
}

.search-result-item:active {
  background: var(--surface2);
}

.search-result-item__icon {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 14px;
  color: var(--text3);
}

.search-result-item__info {
  flex: 1;
  min-width: 0;
}

.search-result-item__name {
  font-size: 13px;
  font-weight: 500;
  color: var(--text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.search-result-item__path {
  font-size: 11px;
  color: var(--text3);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-top: 2px;
}

.search-result-item__size {
  font-size: 11px;
  color: var(--text3);
  flex-shrink: 0;
}
</style>
