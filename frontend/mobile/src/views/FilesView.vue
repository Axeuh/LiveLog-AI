<template>
  <div id="page-files" class="page active">
    <!-- 顶栏: 面包屑 + 搜索 -->
    <div class="files-toolbar">
      <div class="files-breadcrumb">
        <span class="crumb-item" @click="navigateTo('')">/</span>
        <template v-for="(seg, idx) in pathSegments" :key="idx">
          <span class="crumb-sep">/</span>
          <span
            class="crumb-item"
            :class="{ active: idx === pathSegments.length - 1 }"
            @click="navigateTo(getPathUpTo(idx))"
          >
            {{ seg }}
          </span>
        </template>
      </div>
      <SearchBar
        v-model="searchQuery"
        :loading="isSearching"
        @clear="handleSearchClear"
      />
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

    <!-- 文件树 -->
    <FileTree
      v-show="!searchQuery && pageState === null"
      :files="filteredFiles"
      :loading="isLoading"
      :parent-path="currentPath"
      @preview="handleFilePreview"
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
import SearchBar from '@/components/files/SearchBar.vue'
import SearchResultItem from '@/components/files/SearchResultItem.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import PreviewOverlay from '@/components/files/PreviewOverlay.vue'
import { useFileBrowserSingleton } from '@/composables/useFileBrowser'
import type { FileEntry } from '@/types'

type PreviewFileType = 'md' | 'jsonl' | 'audio' | 'json'

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

function handleSearchClear(): void {
  searchQuery.value = ''
}

function handleSearchResultClick(entry: FileEntry, path: string): void {
  if (entry.type === 'dir') {
    // 导航到目录
    const dirPath = path.replace(/^\//, '')
    navigateTo(dirPath)
  } else {
    // 预览文件
    handleFilePreview(entry, path)
  }
}

/** 根据文件扩展名推断预览类型 */
function getFilePreviewType(fileName: string): PreviewFileType {
  const lower = fileName.toLowerCase()
  if (lower.endsWith('.md')) return 'md'
  if (lower.endsWith('.jsonl')) return 'jsonl'
  if (lower.endsWith('.json')) return 'json'
  if (lower.endsWith('.mp3') || lower.endsWith('.wav') || lower.endsWith('.ogg') || lower.endsWith('.m4a') || lower.endsWith('.aac') || lower.endsWith('.flac')) return 'audio'
  // 默认尝试 JSONL (perception.jsonl 等无扩展名文件)
  return 'jsonl'
}

function handleFilePreview(entry: FileEntry, path: string): void {
  if (entry.type === 'dir') return
  previewPath.value = '/' + path
  previewType.value = getFilePreviewType(entry.name)
  previewVisible.value = true
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
  padding: 16px 16px 12px;
  overflow: hidden;
}

.files-toolbar {
  flex-shrink: 0;
  margin-bottom: 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.files-breadcrumb {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 2px;
  padding: 6px 4px;
  font-size: 13px;
  color: var(--text2);
  background: var(--surface);
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
}

.crumb-item {
  cursor: pointer;
  padding: 3px 6px;
  border-radius: 4px;
  transition: background 0.12s;
  font-weight: 500;
}

.crumb-item:hover {
  background: var(--surface2);
  color: var(--text);
}

.crumb-item.active {
  color: var(--primary);
  font-weight: 600;
}

.crumb-sep {
  color: var(--text3);
  font-size: 11px;
}

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
  padding: 40px 0;
  font-size: 13px;
  color: var(--text3);
}

.files-search-results__empty i {
  font-size: 24px;
  opacity: 0.5;
}

.files-search-results__list {
  padding: 4px 0;
}
</style>
