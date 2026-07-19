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
          <div class="preview-header__actions">
            <button class="preview-header__download" @click="handleDownload" aria-label="下载">
              <i class="fas fa-download"></i>
            </button>
            <button class="preview-header__close" @click="handleClose" aria-label="关闭">
              <i class="fas fa-times"></i>
            </button>
          </div>
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

          <!-- 图片预览 -->
          <ImagePreview
            v-else-if="fileType === 'image'"
            :src="imageSrc"
            :fileName="fileName"
            @download="handleDownload"
          />

          <!-- 代码/文本预览 (纯文本+行号, 无额外容器) -->
          <TextPreview
            v-else-if="fileType === 'code' || fileType === 'md' || fileType === 'json' || fileType === 'jsonl'"
            :content="fileType === 'code' ? codeContentStr : contentStr"
            :fileType="fileType === 'code' ? 'text' : fileType"
            :fileName="fileName"
          />

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

          <!-- 空状态 (无法预览的文件类型) -->
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
import ImagePreview from './ImagePreview.vue'
import TextPreview from './TextPreview.vue'

type FileType = 'md' | 'jsonl' | 'audio' | 'json' | 'image' | 'code'

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
const contentStr = ref<string>('')         // md/json/jsonl 内容 (md/json 为已渲染 HTML, jsonl 为原始文本)
const codeContentStr = ref<string>('')     // code 预览内容 (已渲染 HTML)
const audioSrc = ref<string>('')
const imageSrc = ref<string>('')

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
    case 'image': return 'fa-file-image'
    case 'code': return 'fa-file-code'
    default: return 'fa-file'
  }
})

/** 处理关闭 */
function handleClose(): void {
  emit('close')
}

/** 下载文件 */
function handleDownload(): void {
  const url = getFileRawUrl(props.filePath)
  const a = document.createElement('a')
  a.href = url
  a.download = fileName.value
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
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
  contentStr.value = ''
  codeContentStr.value = ''
  audioSrc.value = ''
  imageSrc.value = ''

  try {
    // 音频文件直接构造 URL, 不请求内容
    if (props.fileType === 'audio') {
      audioSrc.value = getFileRawUrl(props.filePath)
      loading.value = false
      return
    }

    // 图片文件直接构造 URL
    if (props.fileType === 'image') {
      imageSrc.value = getFileRawUrl(props.filePath)
      loading.value = false
      return
    }

    const result = await fetchFileContent(props.filePath)

    if (result === null) {
      error.value = '加载文件失败'
      return
    }

    if (props.fileType === 'md') {
      const text = extractTextContent(result)
      if (text === null) {
        error.value = '无法读取文件内容'
        return
      }
      contentStr.value = renderMarkdown(text)
    } else if (props.fileType === 'code') {
      const text = extractTextContent(result)
      if (text === null) {
        error.value = '无法读取文件内容'
        return
      }
      // 传原始文本, 由 CodePreview 添加行号
      codeContentStr.value = text
    } else if (props.fileType === 'json') {
      const text = extractTextContent(result)
      if (text === null) {
        error.value = '无法读取文件内容'
        return
      }
      // 传原始 JSON 文本, 由 TextPreview 处理高亮+行号
      contentStr.value = text
    } else if (props.fileType === 'jsonl') {
      // JSONL 文件: 从 objects 数组或解析 content, 统一转为纯文本传给 TextPreview
      let rawText: string | null = null
      if (Array.isArray(result) && result.length > 0 && typeof result[0] === 'object' && result[0] !== null && 'objects' in result[0]) {
        const jsonResp = result[0] as FileContentJsonResponse
        if (Array.isArray(jsonResp.objects)) {
          rawText = jsonResp.objects.map(obj => JSON.stringify(obj)).join('\n')
        }
      } else if (typeof result === 'object' && result !== null && 'objects' in result) {
        const jsonResp = result as FileContentJsonResponse
        if (Array.isArray(jsonResp.objects)) {
          rawText = jsonResp.objects.map(obj => JSON.stringify(obj)).join('\n')
        }
      } else {
        rawText = extractTextContent(result)
      }
      contentStr.value = rawText || ''
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
  if (typeof result === 'object' && 'objects' in result && Array.isArray(result.objects)) {
    return result.objects.map(obj => JSON.stringify(obj)).join('\n')
  }
  return null
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
  background: var(--overlay-bg);
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
  flex: 1;
}

.preview-header__actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.preview-header__download {
  background: transparent;
  border: none;
  color: var(--text3);
  font-size: 16px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 6px;
  transition: background 0.15s, color 0.15s;
  flex-shrink: 0;
}

.preview-header__download:hover {
  background: var(--surface2);
  color: var(--primary-light);
}

.preview-header__download:active {
  background: var(--surface3);
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
  padding: 14px 8px 90px;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: thin;
  scrollbar-color: rgba(255, 255, 255, 0.15) transparent;
}
.preview-body::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
.preview-body::-webkit-scrollbar-track {
  background: transparent;
}
.preview-body::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.15);
  border-radius: 3px;
}
.preview-body::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.3);
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
  color: var(--danger);
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

/* PC 模式: 居中模态窗口 */
@media (min-width: 768px) {
  .preview-overlay {
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--overlay-bg-pc);
  }
  .preview-overlay-inner {
    max-width: 600px;
    max-height: 80vh;
    width: 90vw;
    border-radius: 12px;
  }
}
</style>
