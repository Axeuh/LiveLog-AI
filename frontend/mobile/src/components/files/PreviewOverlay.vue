<template>
  <Teleport to="body">
    <Transition name="preview-overlay">
      <div
        v-if="visible"
        class="preview-overlay"
        @keydown.escape="handleClose"
        tabindex="-1"
        ref="overlayRef"
      >
        <!-- 头部 -->
        <div class="preview-header">
          <div class="preview-header__left">
            <i class="fas preview-header__icon" :class="fileTypeIcon"></i>
            <span class="preview-header__title">{{ fileName }}</span>
          </div>
          <button class="preview-header__close" @click="handleClose" aria-label="关闭">
            <i class="fas fa-times"></i>
          </button>
        </div>

        <!-- 内容区域 -->
        <div class="preview-body">
          <!-- 加载状态 -->
          <div v-if="loading" class="preview-state preview-state--loading">
            <LoadingSpinner size="md" text="加载文件内容..." />
          </div>

          <!-- 错误状态 -->
          <div v-else-if="error" class="preview-state preview-state--error">
            <i class="fas fa-exclamation-triangle"></i>
            <span class="preview-state__text">{{ error }}</span>
            <button class="preview-state__retry" @click="loadContent">重试</button>
          </div>

          <!-- Markdown 预览 -->
          <div
            v-else-if="fileType === 'md' && mdHtml"
            class="preview-md md-content"
            v-html="mdHtml"
          ></div>

          <!-- JSON 预览 -->
          <div
            v-else-if="fileType === 'json' && jsonHtml"
            class="preview-json md-content"
            v-html="jsonHtml"
          ></div>

          <!-- JSONL 预览 -->
          <div v-else-if="fileType === 'jsonl'" class="preview-jsonl">
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
                    <pre class="jsonl-item__json">{{ formatJson(line) }}</pre>
                  </div>
                </Transition>
              </div>
            </div>
          </div>

          <!-- 音频预览 -->
          <div v-else-if="fileType === 'audio'" class="preview-audio">
            <div class="audio-player">
              <div class="audio-player__icon">
                <i class="fas fa-file-audio"></i>
              </div>
              <div class="audio-player__info">
                <span class="audio-player__name">{{ fileName }}</span>
                <span class="audio-player__hint">音频文件</span>
              </div>
              <audio
                controls
                :src="audioSrc"
                class="audio-player__controls"
              >
                您的浏览器不支持音频播放
              </audio>
            </div>
          </div>

          <!-- 空状态 -->
          <div v-else class="preview-state preview-state--empty">
            <i class="fas fa-file"></i>
            <span class="preview-state__text">无法预览此文件</span>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { fetchFileContent, getFileRawUrl } from '@/api/files'
import { renderMarkdown } from '@/utils/markdown'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import type { FileContentJsonResponse } from '@/types'

type FileType = 'md' | 'jsonl' | 'audio' | 'json'

const props = defineProps<{
  filePath: string
  fileType: FileType
  visible: boolean
}>()

const emit = defineEmits<{
  close: []
}>()

const overlayRef = ref<HTMLElement | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const mdHtml = ref<string>('')
const jsonHtml = ref<string>('')
const jsonlLines = ref<Record<string, unknown>[]>([])
const expandedLines = ref<Set<number>>(new Set())
const audioSrc = ref<string>('')

/** 从路径提取文件名 */
const fileName = computed(() => {
  if (!props.filePath) return ''
  const parts = props.filePath.split('/')
  return parts[parts.length - 1] || props.filePath
})

/** 文件类型对应的图标 class */
const fileTypeIcon = computed(() => {
  switch (props.fileType) {
    case 'md': return 'fa-file-alt'
    case 'json': return 'fa-file-code'
    case 'jsonl': return 'fa-file-code'
    case 'audio': return 'fa-file-audio'
    default: return 'fa-file'
  }
})

/** 处理关闭 */
function handleClose(): void {
  emit('close')
}

/** 键盘 ESC 处理 */
function handleKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape' && props.visible) {
    handleClose()
  }
}

/** 加载文件内容 */
async function loadContent(): Promise<void> {
  if (!props.filePath) return

  loading.value = true
  error.value = null
  mdHtml.value = ''
  jsonHtml.value = ''
  jsonlLines.value = []
  expandedLines.value = new Set()

  try {
    // 音频文件直接构造 URL, 不请求内容
    if (props.fileType === 'audio') {
      audioSrc.value = getFileRawUrl(props.filePath)
      loading.value = false
      return
    }

    const result = await fetchFileContent(props.filePath)

    if (result === null) {
      error.value = '加载文件失败'
      return
    }

    if (props.fileType === 'md') {
      // Markdown 文件: 从 content 字段或直接使用字符串
      const text = extractTextContent(result)
      if (text === null) {
        error.value = '无法读取文件内容'
        return
      }
      mdHtml.value = renderMarkdown(text)
    } else if (props.fileType === 'json') {
      // JSON 文件: 格式化显示
      const text = extractTextContent(result)
      if (text === null) {
        error.value = '无法读取文件内容'
        return
      }
      try {
        const parsed = JSON.parse(text)
        jsonHtml.value = renderMarkdown('```json\n' + JSON.stringify(parsed, null, 2) + '\n```')
      } catch {
        // 不是有效 JSON, 直接显示原文
        jsonHtml.value = renderMarkdown('```\n' + text + '\n```')
      }
    } else if (props.fileType === 'jsonl') {
      // JSONL 文件: 从 objects 数组或解析 content
      if (Array.isArray(result) && result.length > 0 && typeof result[0] === 'object' && result[0] !== null && 'objects' in result[0]) {
        // FileContentJsonResponse with objects
        const jsonResp = result[0] as FileContentJsonResponse
        if (Array.isArray(jsonResp.objects)) {
          jsonlLines.value = jsonResp.objects
        }
      } else if (typeof result === 'object' && result !== null && 'objects' in result) {
        const jsonResp = result as FileContentJsonResponse
        if (Array.isArray(jsonResp.objects)) {
          jsonlLines.value = jsonResp.objects
        }
      } else {
        // 尝试逐行解析 JSONL 文本
        const text = extractTextContent(result)
        if (text) {
          jsonlLines.value = text
            .split('\n')
            .filter(line => line.trim())
            .map(line => {
              try {
                return JSON.parse(line) as Record<string, unknown>
              } catch {
                return { _raw: line } as Record<string, unknown>
              }
            })
        }
      }
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载文件失败'
  } finally {
    loading.value = false
  }
}

/** 从 API 返回值中提取文本内容 */
function extractTextContent(result: FileContentJsonResponse | string | null): string | null {
  if (result === null) return null
  if (typeof result === 'string') return result
  if (typeof result === 'object' && 'content' in result && typeof result.content === 'string') {
    return result.content
  }
  // 如果是 FileContentJsonResponse 但没有 content, 尝试序列化 objects
  if (typeof result === 'object' && 'objects' in result && Array.isArray(result.objects)) {
    return result.objects.map(obj => JSON.stringify(obj)).join('\n')
  }
  return null
}

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
  // 优先取 text/content/summary 字段
  for (const key of ['text', 'content', 'summary', 'message', 'name']) {
    if (obj[key] && typeof obj[key] === 'string') {
      const val = obj[key] as string
      return val.length > 80 ? val.slice(0, 80) + '...' : val
    }
  }
  // 取第一个 string 值
  for (const val of Object.values(obj)) {
    if (typeof val === 'string' && val.length > 0) {
      return val.length > 80 ? val.slice(0, 80) + '...' : val
    }
  }
  return '{...}'
}

/** 格式化 JSON 用于展示 */
function formatJson(obj: Record<string, unknown>): string {
  try {
    return JSON.stringify(obj, null, 2)
  } catch {
    return String(obj)
  }
}

// 监听 visible 变化, 打开时加载内容
watch(() => props.visible, async (newVal) => {
  if (newVal) {
    await nextTick()
    overlayRef.value?.focus()
    loadContent()
  }
})

// 生命周期钩子
onMounted(() => {
  document.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeydown)
})
</script>

<style scoped>
/* 浮层容器 */
.preview-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.88);
  backdrop-filter: blur(14px);
  display: flex;
  flex-direction: column;
  z-index: 700;
  outline: none;
}

/* 过渡动画 */
.preview-overlay-enter-active,
.preview-overlay-leave-active {
  transition: opacity 0.3s ease, transform 0.3s ease;
}

.preview-overlay-enter-from,
.preview-overlay-leave-to {
  opacity: 0;
  transform: scale(0.95);
}

/* 头部 */
.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 20px;
  flex-shrink: 0;
  background: var(--surface);
}

.preview-header__left {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.preview-header__icon {
  font-size: 16px;
  color: var(--primary-light);
  flex-shrink: 0;
}

.preview-header__title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.preview-header__close {
  background: transparent;
  border: none;
  color: var(--text3);
  font-size: 20px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 6px;
  transition: background 0.15s;
  flex-shrink: 0;
}

.preview-header__close:hover {
  background: var(--surface2);
}

.preview-header__close:active {
  background: var(--surface3);
}

/* 内容区域 */
.preview-body {
  flex: 1;
  overflow-y: auto;
  padding: 14px 20px 90px;
  -webkit-overflow-scrolling: touch;
}

/* 状态 (加载/错误/空) */
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

.preview-state--loading i {
  color: var(--primary-light);
}

.preview-state--error i {
  color: #ff6b6b;
}

.preview-state__text {
  font-size: 14px;
  color: var(--text2);
  text-align: center;
}

.preview-state__retry {
  margin-top: 8px;
  padding: 8px 20px;
  background: var(--primary);
  color: #fff;
  border: none;
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s;
}

.preview-state__retry:hover {
  background: var(--primary-light);
}

/* Markdown 预览 */
.preview-md {
  font-size: 14px;
  line-height: 1.7;
  color: var(--text);
}

/* JSON 预览 */
.preview-json {
  font-size: 13px;
  line-height: 1.6;
}

.preview-json :deep(pre) {
  background: var(--surface2);
  border-radius: var(--radius-sm);
  padding: 14px;
  overflow-x: auto;
  font-size: 12px;
  line-height: 1.5;
}

/* JSONL 列表 */
.preview-jsonl {
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
  border-color: rgba(255, 255, 255, 0.1);
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
.jsonl-type--notify { background: rgba(255, 107, 107, 0.2); color: #ff6b6b; }
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

/* 音频预览 */
.preview-audio {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
}

.audio-player {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20px;
  background: var(--surface);
  border-radius: var(--radius);
  padding: 30px 24px;
  width: 100%;
  max-width: 360px;
}

.audio-player__icon {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: var(--surface2);
  display: flex;
  align-items: center;
  justify-content: center;
}

.audio-player__icon i {
  font-size: 28px;
  color: var(--primary-light);
}

.audio-player__info {
  text-align: center;
}

.audio-player__name {
  display: block;
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
  margin-bottom: 4px;
  word-break: break-all;
}

.audio-player__hint {
  font-size: 12px;
  color: var(--text3);
}

.audio-player__controls {
  width: 100%;
  height: 36px;
  border-radius: 18px;
}
</style>
