<template>
  <div class="search-bar">
    <div class="search-bar__input-wrapper">
      <i class="fas fa-search search-bar__icon"></i>
      <input
        v-model="inputValue"
        type="text"
        class="search-bar__input"
        :placeholder="placeholder"
        @input="handleInput"
        @keydown.escape="handleClear"
      />
      <button
        v-if="inputValue"
        class="search-bar__clear"
        @click="handleClear"
        aria-label="清除搜索"
      >
        <i class="fas fa-times"></i>
      </button>
      <div v-if="loading" class="search-bar__spinner">
        <i class="fas fa-spinner fa-spin"></i>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onUnmounted } from 'vue'

const props = withDefaults(defineProps<{
  /** 初始搜索文本 */
  modelValue?: string
  /** 占位符文本 */
  placeholder?: string
  /** 防抖延迟 (毫秒) */
  debounce?: number
  /** 是否正在搜索 */
  loading?: boolean
}>(), {
  modelValue: '',
  placeholder: '搜索文件...',
  debounce: 300,
  loading: false,
})

const emit = defineEmits<{
  /** 搜索文本变化 (防抖后触发) */
  'update:modelValue': [value: string]
  /** 清除搜索 */
  'clear': []
}>()

const inputValue = ref(props.modelValue)
let debounceTimer: ReturnType<typeof setTimeout> | null = null

/**
 * 处理输入事件 - 带防抖
 */
function handleInput(): void {
  if (debounceTimer) {
    clearTimeout(debounceTimer)
  }
  debounceTimer = setTimeout(() => {
    emit('update:modelValue', inputValue.value)
  }, props.debounce)
}

/**
 * 清除搜索
 */
function handleClear(): void {
  inputValue.value = ''
  if (debounceTimer) {
    clearTimeout(debounceTimer)
    debounceTimer = null
  }
  emit('update:modelValue', '')
  emit('clear')
}

// 组件卸载时清理定时器
onUnmounted(() => {
  if (debounceTimer) {
    clearTimeout(debounceTimer)
  }
})
</script>

<style scoped>
.search-bar {
  position: relative;
  display: flex;
  align-items: center;
}

.search-bar__input-wrapper {
  position: relative;
  display: flex;
  align-items: center;
  width: 100%;
}

.search-bar__icon {
  position: absolute;
  left: 10px;
  font-size: 12px;
  color: var(--text3);
  pointer-events: none;
  z-index: 1;
}

.search-bar__input {
  width: 100%;
  padding: 8px 32px 8px 30px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface);
  color: var(--text);
  font-size: 13px;
  font-family: inherit;
  outline: none;
  transition: border-color 0.15s;
}

.search-bar__input:focus {
  border-color: var(--primary);
}

.search-bar__input::placeholder {
  color: var(--text3);
}

.search-bar__clear {
  position: absolute;
  right: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  padding: 0;
  border: none;
  border-radius: 50%;
  background: var(--surface3);
  color: var(--text2);
  font-size: 10px;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
  z-index: 1;
}

.search-bar__clear:hover {
  background: var(--primary);
  color: #fff;
}

.search-bar__spinner {
  position: absolute;
  right: 32px;
  font-size: 12px;
  color: var(--text3);
}
</style>
