<template>
  <div class="chat-input-bar">
    <!-- 已选文件标签列表 -->
    <div v-if="selectedFiles.length > 0" class="file-tags">
      <div v-for="(f, idx) in selectedFiles" :key="idx" class="file-tag">
        <i class="fas fa-paperclip file-tag-icon"></i>
        <span class="file-tag-name">{{ f.name }}</span>
        <button class="file-tag-remove" @click="removeFile(idx)" title="移除文件">
          <i class="fas fa-times"></i>
        </button>
      </div>
    </div>

    <div class="input-row">
      <!-- 文件选择按钮 -->
      <button class="file-btn" @click="openFilePicker" title="选择文件">
        <i class="fas fa-paperclip"></i>
      </button>
      <input
        ref="fileInputRef"
        type="file"
        multiple
        class="file-input-hidden"
        @change="onFilesSelected"
      />

      <input
        ref="inputRef"
        v-model="messageText"
        type="text"
        placeholder="输入消息..."
        :disabled="disabled"
        @keydown.enter="handleSend"
      />
      <button
        class="send-btn"
        :disabled="disabled || (!messageText.trim() && selectedFiles.length === 0)"
        @click="handleSend"
      >
        <i class="fas fa-arrow-up"></i>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'

const props = withDefaults(defineProps<{
  disabled?: boolean
}>(), {
  disabled: false,
})

const emit = defineEmits<{
  send: [text: string, files: File[]]
}>()

const inputRef = ref<HTMLInputElement | null>(null)
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

/** 发送消息: emit send 事件并清空输入框 */
function handleSend(): void {
  const text = messageText.value.trim()
  if (!text && selectedFiles.value.length === 0) return
  if (props.disabled) return

  emit('send', text || '', [...selectedFiles.value])
  messageText.value = ''
  selectedFiles.value = []
}

onMounted(() => {
  // 自动聚焦输入框
  inputRef.value?.focus()
})
</script>

<style scoped>
.chat-input-bar {
  flex-shrink: 0;
  padding: 6px 8px;
  margin: 0 -8px;
  background: var(--surface);
  border-top: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  gap: 6px;
  position: relative;
  z-index: 600;
}

/* 文件标签容器 */
.file-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
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

.file-tag-icon {
  color: var(--primary);
  font-size: 12px;
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
  font-size: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.file-tag-remove:active {
  background: var(--surface3);
  color: var(--text);
}

/* 输入行 */
.input-row {
  display: flex;
  gap: 6px;
  align-items: center;
}

/* 文件选择按钮 */
.file-btn {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: none;
  background: var(--surface2);
  color: var(--text2);
  font-size: 13px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
  flex-shrink: 0;
}

.file-btn:active {
  background: var(--primary-light);
  color: #fff;
}

/* 隐藏的文件输入 */
.file-input-hidden {
  display: none;
}

.chat-input-bar input[type="text"] {
  flex: 1;
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: 20px;
  padding: 10px 12px;
  color: var(--text);
  font-family: inherit;
  font-size: 14px;
  outline: none;
}

.chat-input-bar input[type="text"]:focus {
  border-color: var(--primary);
}

.chat-input-bar input[type="text"]::placeholder {
  color: var(--text3);
}

.chat-input-bar .send-btn {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  border: none;
  background: var(--primary);
  color: #fff;
  font-size: 15px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s;
  flex-shrink: 0;
}

.chat-input-bar .send-btn:active {
  background: var(--primary-light);
}

.chat-input-bar .send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
