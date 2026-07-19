<template>
  <div class="file-item" :class="{ selected: isSelected }">
    <div
      class="file-item__row"
      :style="{ paddingLeft: depth * 20 + 12 + 'px' }"
      @click="handleClick"
    >
      <span class="file-item__icon">
        <i v-if="isFolder" class="fas" :class="isExpanded ? 'fa-folder-open' : 'fa-folder'" style="color:var(--accent3)"></i>
        <i v-else class="fas" :class="fileIconClass"></i>
      </span>
      <span class="file-item__name">{{ entry.name }}</span>
      <span v-if="entry.size != null" class="file-item__size">{{ formatSize(entry.size) }}</span>
      <span v-if="entry.modified_at" class="file-item__date">{{ formatDate(entry.modified_at) }}</span>
      <button v-if="!isFolder" class="file-item__download" title="下载" @click.stop="handleDownload">
        <i class="fas fa-download"></i>
      </button>
      <span v-if="isFolder" class="file-item__arrow">
        <i class="fas fa-chevron-right" :class="{ rotated: isExpanded }"></i>
      </span>
    </div>
    <transition name="file-expand">
      <div v-if="isExpanded" class="file-item__children">
        <LoadingSpinner v-if="childrenLoading" size="sm" text="加载中..." />
        <FileItem
          v-for="child in children"
          :key="child.name"
          :entry="child"
          :depth="depth + 1"
          :parent-path="fullPath"
          :is-selected="false"
          @preview="(entry, path) => emit('preview', entry, path)"
        />
        <div v-if="!childrenLoading && children.length === 0" class="file-item__empty">
          空目录
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, defineOptions } from 'vue'
import type { FileEntry } from '@/types'
import { fetchDirectory } from '@/api/files'
import { getFileRawUrl } from '@/api/files'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import FileItem from './FileItem.vue'

defineOptions({ name: 'FileItem' })

const props = withDefaults(defineProps<{
  entry: FileEntry
  depth?: number
  isSelected?: boolean
  parentPath?: string
}>(), {
  depth: 0,
  isSelected: false,
  parentPath: '',
})

const emit = defineEmits<{
  preview: [entry: FileEntry, path: string]
}>()

const isExpanded = ref(false)
const children = ref<FileEntry[]>([])
const childrenLoading = ref(false)

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

const fullPath = computed(() => {
  if (props.parentPath) {
    return props.parentPath + '/' + props.entry.name
  }
  return props.entry.name
})

async function handleClick(): Promise<void> {
  if (!isFolder.value) {
    emit('preview', props.entry, fullPath.value)
    return
  }
  if (isExpanded.value) {
    isExpanded.value = false
    return
  }
  isExpanded.value = true
  if (children.value.length === 0) {
    await loadChildren()
  }
}

async function loadChildren(): Promise<void> {
  childrenLoading.value = true
  try {
    const result = await fetchDirectory('/' + fullPath.value)
    if (result && result.entries) {
      children.value = result.entries
    } else {
      children.value = []
    }
  } catch {
    children.value = []
  } finally {
    childrenLoading.value = false
  }
}

/** 下载文件 */
function handleDownload(): void {
  const url = getFileRawUrl('/' + fullPath.value)
  const a = document.createElement('a')
  a.href = url
  a.download = props.entry.name
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

function formatDate(isoStr: string): string {
  try {
    const d = new Date(isoStr)
    if (isNaN(d.getTime())) return isoStr
    const h = d.getHours().toString().padStart(2, '0')
    const m = d.getMinutes().toString().padStart(2, '0')
    return h + ':' + m
  } catch {
    return isoStr
  }
}
</script>

<style scoped>
.file-item {
  user-select: none;
  display: block; /* 覆盖全局 CSS 的 display: flex */
}

.file-item__row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 1px 10px;
  cursor: pointer;
  border-radius: 6px;
  transition: background 0.12s;
}

.file-item__row:hover {
  background: var(--surface2);
}
.file-item__icon {
  width: 22px;
  text-align: center;
  flex-shrink: 0;
  font-size: 15px;
  color: var(--text3);
}

.file-item.selected > .file-item__row .file-item__icon {
  color: inherit;
}

.file-item__name {
  flex: 1;
  font-size: 13px;
  font-weight: 500;
  color: var(--text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-item.selected > .file-item__row .file-item__name {
  color: inherit;
}

.file-item__size {
  font-size: 11px;
  color: var(--text3);
  flex-shrink: 0;
  min-width: 50px;
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.file-item.selected > .file-item__row .file-item__size {
  color: inherit;
  opacity: 0.8;
}

.file-item__date {
  font-size: 11px;
  color: var(--text3);
  flex-shrink: 0;
  min-width: 40px;
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.file-item.selected > .file-item__row .file-item__date {
  color: inherit;
  opacity: 0.8;
}

.file-item__arrow {
  width: 16px;
  text-align: center;
  flex-shrink: 0;
  font-size: 10px;
  color: var(--text3);
}

.file-item__download {
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  color: var(--text3);
  font-size: 12px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  flex-shrink: 0;
  opacity: 0;
  transition: opacity 0.15s, background 0.15s, color 0.15s;
}

.file-item__row:hover .file-item__download {
  opacity: 1;
}

.file-item__download:active {
  background: var(--surface3);
  color: var(--primary-light);
}

.file-item.selected > .file-item__row .file-item__arrow {
  color: inherit;
}

.file-item__arrow i {
  transition: transform 0.2s;
}

.file-item__arrow i.rotated {
  transform: rotate(90deg);
}

.file-item__children {
  overflow: hidden;
}

.file-item__empty {
  padding: 8px 12px 8px 44px;
  font-size: 12px;
  color: var(--text3);
  font-style: italic;
}

.file-expand-enter-active,
.file-expand-leave-active {
  transition: all 0.2s ease;
  max-height: 1000px;
}

.file-expand-enter-from,
.file-expand-leave-to {
  max-height: 0;
  opacity: 0;
}
</style>
