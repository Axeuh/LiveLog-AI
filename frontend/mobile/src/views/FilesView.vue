<template>
  <div id="page-files" class="page active">
    <!-- iOS 风格搜索栏 -->
    <div class="files-search-bar">
      <div class="files-search-bar__inner">
        <i class="fas fa-search files-search-bar__icon"></i>
        <input
          v-model="searchQuery"
          type="text"
          class="files-search-bar__input"
          placeholder="搜索"
          @keydown.escape="searchQuery = ''"
        />
        <button
          v-if="searchQuery"
          class="files-search-bar__clear"
          @click="searchQuery = ''"
          aria-label="清除搜索"
        >
          <i class="fas fa-times-circle"></i>
        </button>
      </div>
    </div>

    <!-- 面包屑导航 -->
    <div class="files-breadcrumb">
      <span class="crumb-item root" @click="navigateTo('')">
        <i class="fas fa-folder"></i>
      </span>
      <template v-for="(seg, idx) in pathSegments" :key="idx">
        <i class="fas fa-chevron-right crumb-sep"></i>
        <span
          class="crumb-item"
          :class="{ active: idx === pathSegments.length - 1 }"
          @click="navigateTo(getPathUpTo(idx))"
        >
          {{ seg }}
        </span>
      </template>
    </div>

    <!-- 搜索结果 -->
    <div v-if="searchQuery" class="files-search-results">
      <div v-if="isSearching" class="files-search-results__loading">
        <LoadingSpinner size="sm" text="搜索中..." />
      </div>
      <div v-else-if="filteredFiles.length === 0" class="files-search-results__empty">
        <i class="fas fa-search"></i>
        <span>未找到匹配的文件</span>
      </div>
      <div v-else class="files-search-results__list">
        <SearchResultItem
          v-for="entry in filteredFiles"
          :key="entry.name"
          :entry="entry"
          :path="getEntryFullPath(entry)"
          @click="handleSearchResultClick"
        />
      </div>
    </div>

    <!-- 页面状态 -->
    <PageState
      v-else-if="pageState !== null"
      :state="pageState.state"
      :message="pageState.message"
      :description="pageState.description"
      @retry="handleRetry"
    />

    <!-- 文件列表 -->
    <FileTree
      v-show="!searchQuery && pageState === null"
      :files="filteredFiles"
      :loading="isLoading"
      :parent-path="currentPath"
      @preview="handleFilePreview"
      @navigate="handleFolderNavigate"
    />

    <!-- 文件预览浮层 -->
    <PreviewOverlay
      :visible="previewVisible"
      :file-path="previewPath"
      :file-type="previewType"
      @close="closePreview"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import PageState from '@/components/common/PageState.vue'
import FileTree from '@/components/files/FileTree.vue'
import SearchResultItem from '@/components/files/SearchResultItem.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import PreviewOverlay from '@/components/files/PreviewOverlay.vue'
import { useFileBrowserSingleton } from '@/composables/useFileBrowser'
import type { FileEntry } from '@/types'

type PreviewFileType = 'md' | 'jsonl' | 'audio' | 'json' | 'image' | 'code'

const browser = useFileBrowserSingleton()

const currentPath = ref('')
const searchQuery = ref('')
const pageError = ref<string | null>(null)
const isSearching = ref(false)

// 预览状态
const previewVisible = ref(false)
const previewPath = ref('')
const previewType = ref<PreviewFileType>('md')

const isLoading = computed(() => browser.loading.value)

type PageStateInfo = {
  state: 'loading' | 'empty' | 'error'
  message: string
  description?: string
} | null

const pageState = computed<PageStateInfo>(() => {
  if (isLoading.value && browser.fileEntries.value.length === 0) {
    return { state: 'loading', message: '加载中...', description: '正在加载文件列表' }
  }
  if (pageError.value) {
    return { state: 'error', message: '加载失败', description: pageError.value }
  }
  if (!isLoading.value && filteredFiles.value.length === 0 && !searchQuery.value) {
    return { state: 'empty', message: '暂无文件', description: '当前目录为空' }
  }
  return null
})

const pathSegments = computed(() => {
  const p = currentPath.value
  if (!p) return []
  return p.split('/').filter(Boolean)
})

function getPathUpTo(idx: number): string {
  const segs = pathSegments.value
  return segs.slice(0, idx + 1).join('/')
}

function getFullPath(segmentPath: string): string {
  if (!segmentPath) return ''
  return segmentPath.startsWith('/') ? segmentPath : '/' + segmentPath
}

function getEntryFullPath(entry: FileEntry): string {
  const base = currentPath.value ? '/' + currentPath.value : ''
  return base + '/' + entry.name
}

async function navigateTo(path: string): Promise<void> {
  searchQuery.value = ''
  pageError.value = null
  currentPath.value = path
  const fullPath = getFullPath(path)
  try {
    await browser.loadDirectory(fullPath)
  } catch (e) {
    pageError.value = e instanceof Error ? e.message : '加载失败'
  }
}

const filteredFiles = computed(() => {
  const entries = browser.fileEntries.value
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return entries
  return entries.filter((e) => e.name.toLowerCase().includes(q))
})

function handleSearchResultClick(entry: FileEntry, path: string): void {
  if (entry.type === 'dir') {
    const dirPath = path.replace(/^\//, '')
    navigateTo(dirPath)
  } else {
    handleFilePreview(entry, path)
  }
}

/** 根据文件扩展名推断预览类型 */
function getFilePreviewType(fileName: string): PreviewFileType {
  const lower = fileName.toLowerCase()
  if (lower.match(/\.(png|jpg|jpeg|gif|bmp|webp|svg|ico)$/)) return 'image'
  if (lower.match(/\.(py|js|ts|tsx|jsx|vue|kt|java|go|rs|c|cpp|h|hpp|rb|php|sh|bash|ps1|sql|yaml|yml|toml|ini|cfg|conf|xml)$/)) return 'code'
  if (lower.endsWith('.md')) return 'md'
  if (lower.endsWith('.jsonl')) return 'jsonl'
  if (lower.endsWith('.json')) return 'json'
  if (lower.endsWith('.mp3') || lower.endsWith('.wav') || lower.endsWith('.ogg') || lower.endsWith('.m4a') || lower.endsWith('.aac') || lower.endsWith('.flac')) return 'audio'
  if (lower.match(/\.(txt|log)$/)) return 'code'
  return 'jsonl'
}

function handleFilePreview(entry: FileEntry, path: string): void {
  if (entry.type === 'dir') return
  const base = currentPath.value ? '/' + currentPath.value : ''
  previewPath.value = base + '/' + path
  previewType.value = getFilePreviewType(entry.name)
  previewVisible.value = true
}

/** 处理文件夹导航 (点击文件夹时) */
function handleFolderNavigate(folderName: string): void {
  const newPath = currentPath.value
    ? currentPath.value + '/' + folderName
    : folderName
  navigateTo(newPath)
}

function closePreview(): void {
  previewVisible.value = false
}

function handleRetry(): void {
  pageError.value = null
  navigateTo(currentPath.value)
}

onMounted(() => {
  navigateTo('')
})
</script>

<style scoped>
#page-files {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* iOS 风格搜索栏 */
.files-search-bar {
  flex-shrink: 0;
  padding: 8px 16px 4px;
}

.files-search-bar__inner {
  position: relative;
  display: flex;
  align-items: center;
}

.files-search-bar__icon {
  position: absolute;
  left: 10px;
  font-size: 13px;
  color: var(--text3);
  pointer-events: none;
  z-index: 1;
}

.files-search-bar__input {
  width: 100%;
  height: 36px;
  padding: 0 32px 0 32px;
  border: none;
  border-radius: 10px;
  background: var(--surface2);
  color: var(--text);
  font-size: 15px;
  font-family: inherit;
  outline: none;
  transition: background 0.15s;
}

.files-search-bar__input::placeholder {
  color: var(--text3);
}

.files-search-bar__input:focus {
  background: var(--surface3);
}

.files-search-bar__clear {
  position: absolute;
  right: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  padding: 0;
  border: none;
  background: transparent;
  color: var(--text3);
  font-size: 14px;
  cursor: pointer;
  z-index: 1;
}

/* 面包屑导航 */
.files-breadcrumb {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 16px 8px;
  font-size: 13px;
  color: var(--text2);
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

.files-breadcrumb::-webkit-scrollbar {
  display: none;
}

.crumb-item {
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
  transition: background 0.12s;
  font-weight: 500;
  white-space: nowrap;
  flex-shrink: 0;
}

.crumb-item:hover {
  background: var(--surface2);
  color: var(--text);
}

.crumb-item.active {
  color: var(--primary);
  font-weight: 600;
}

.crumb-item.root {
  font-size: 14px;
  color: var(--primary);
}

.crumb-sep {
  font-size: 9px;
  color: var(--text3);
  opacity: 0.6;
  flex-shrink: 0;
}

/* 搜索结果 */
.files-search-results {
  flex: 1;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  padding: 4px 0;
}

.files-search-results__loading {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 0;
}

.files-search-results__empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 60px 0;
  font-size: 14px;
  color: var(--text3);
}

.files-search-results__empty i {
  font-size: 32px;
  opacity: 0.4;
}

.files-search-results__list {
  padding: 0;
}

/* PC 模式 */
@media (min-width: 768px) {
  #page-files {
    padding: 0 !important;
  }
  .files-search-bar {
    padding: 12px 20px 8px;
  }
  .files-breadcrumb {
    padding: 8px 20px 10px;
  }
}
</style>
