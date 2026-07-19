<template>
  <div class="chat-input-bar">
    <!-- 已选文件标签列表 -->
    <div v-if="selectedFiles.length > 0" class="file-tags">
      <div v-for="(f, idx) in selectedFiles" :key="idx" class="file-tag">
        <img v-if="f.type.startsWith('image/')" :src="getFilePreviewUrl(f)" class="file-tag-thumb" />
        <svg v-else class="file-tag-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48" />
        </svg>
        <span class="file-tag-name">{{ f.name }}</span>
        <button class="file-tag-remove" @click="removeFile(idx)" title="移除文件">
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
            <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>
      </div>
    </div>

    <div class="input-container">
      <!-- 附件按钮 -->
      <button class="attach-btn" @click="openFilePicker" title="选择文件">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48" />
        </svg>
      </button>
      <input
        ref="fileInputRef"
        type="file"
        multiple
        class="file-input-hidden"
        @change="onFilesSelected"
      />

      <!-- 输入框 -->
      <textarea
        ref="inputRef"
        v-model="messageText"
        placeholder="输入消息..."
        :disabled="disabled"
        rows="1"
        @keydown="handleKeydown"
        @paste="handlePaste"
      ></textarea>

      <!-- 发送按钮 -->
      <button
        class="send-btn"
        :disabled="disabled || (!messageText.trim() && selectedFiles.length === 0)"
        @click="handleSend"
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 14v-4H7l5-5 5 5h-4v4h-2z" />
        </svg>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'

const props = withDefaults(defineProps<{
  disabled?: boolean
}>(), {
  disabled: false,
})

const emit = defineEmits<{
  send: [text: string, files: File[]]
}>()

const inputRef = ref<HTMLTextAreaElement | null>(null)
const fileInputRef = ref<HTMLInputElement | null>(null)
const messageText = ref('')
const selectedFiles = ref<File[]>([])

/** 打开文件选择器 */
function openFilePicker(): void {
  fileInputRef.value?.click()
}

/** 文件选择回调 -- 支持多选，追加到已有列表 */
function onFilesSelected(e: Event): void {
  const input = e.target as HTMLInputElement
  const files = input.files
  if (files && files.length > 0) {
    for (let i = 0; i < files.length; i++) {
      selectedFiles.value.push(files[i])
    }
  }
  // 重置 input，允许重复选择同一文件
  input.value = ''
}

/** 移除单个文件 */
function removeFile(index: number): void {
  selectedFiles.value.splice(index, 1)
}

/** 清除所有文件（释放对象URL） */
function clearFiles(): void {
  selectedFiles.value = []
}

/** 粘贴事件 -- 从剪贴板提取图片文件 */
function handlePaste(e: ClipboardEvent): void {
  const items = e.clipboardData?.items
  if (!items) return

  for (let i = 0; i < items.length; i++) {
    const item = items[i]
    if (item.type.startsWith('image/')) {
      const file = item.getAsFile()
      if (file) {
        // 给粘贴的图片一个易读的文件名
        const ext = item.type.split('/')[1] || 'png'
        const renamed = new File(
          [file],
          `粘贴图片_${Date.now()}.${ext}`,
          { type: item.type },
        )
        selectedFiles.value.push(renamed)
      }
    }
  }
}

/** 生成文件的本地预览 URL */
function getFilePreviewUrl(file: File): string {
  return URL.createObjectURL(file)
}

/** 键盘事件: Shift+Enter 换行, Enter 发送 */
function handleKeydown(e: KeyboardEvent): void {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
  // 自动调整 textarea 高度
  nextTick(autoResize)
}

/** 自动调整 textarea 高度 */
function autoResize(): void {
  const el = inputRef.value
  if (el) {
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 120) + 'px'
  }
}

/** 发送消息: emit send 事件并清空输入框 */
function handleSend(): void {
  const text = messageText.value.trim()
  if (!text && selectedFiles.value.length === 0) return
  if (props.disabled) return

  emit('send', text || '', [...selectedFiles.value])
  messageText.value = ''
  clearFiles()
}

onMounted(() => {
  // 自动聚焦输入框
  inputRef.value?.focus()
})
</script>

<style scoped>
.chat-input-bar {
  flex-shrink: 0;
  padding: 8px 12px 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

/* PC 上匹配消息区边距 */
@media (min-width: 768px) {
  .chat-input-bar {
    width: 100%;
    max-width: 1200px;
    margin: 0 auto;
    padding: 8px 24px 12px;
  }
}

/* 文件标签容器 */
.file-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 0 4px;
}

/* 文件标签 */
.file-tag {
  display: flex;
  align-items: center;
  gap: 6px;
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 4px 10px;
  font-size: 12px;
  color: var(--text2);
  max-width: 100%;
}

.file-tag-thumb {
  width: 22px;
  height: 22px;
  border-radius: 4px;
  object-fit: cover;
  flex-shrink: 0;
}

.file-tag-icon {
  color: var(--primary);
  flex-shrink: 0;
}

.file-tag-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-tag-remove {
  width: 18px;
  height: 18px;
  border: none;
  background: transparent;
  color: var(--text3);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  flex-shrink: 0;
}

.file-tag-remove:active {
  background: var(--surface3);
  color: var(--text);
}

/* 输入容器 - iMessage 风格胶囊 */
.input-container {
  display: flex;
  align-items: flex-end;
  gap: 4px;
  background: var(--surface2);
  border: 0.5px solid var(--border);
  border-radius: 20px;
  padding: 6px 8px 6px 4px;
  transition: border-color 0.2s;
}

.input-container:focus-within {
  border-color: var(--primary);
}

/* 附件按钮 */
.attach-btn {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: none;
  background: transparent;
  color: var(--text3);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: color 0.15s;
  flex-shrink: 0;
}

.attach-btn:active {
  color: var(--primary);
}

/* 隐藏的文件输入 */
.file-input-hidden {
  display: none;
}

/* 输入框 */
.chat-input-bar textarea {
  flex: 1;
  background: transparent;
  border: none;
  padding: 8px 4px;
  color: var(--text);
  font-family: inherit;
  font-size: 15px;
  outline: none;
  resize: none;
  min-height: 24px;
  max-height: 120px;
  line-height: 1.4;
}

.chat-input-bar textarea::placeholder {
  color: var(--text3);
}

/* 发送按钮 - 蓝色圆形箭头 */
.send-btn {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: none;
  background: var(--primary);
  color: #fff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: opacity 0.15s, transform 0.1s;
  flex-shrink: 0;
}

.send-btn:active {
  transform: scale(0.92);
}

.send-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
</style>
