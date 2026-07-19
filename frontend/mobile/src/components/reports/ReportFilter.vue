<template>
  <nav class="tag-filter-bar">
    <button
      class="pill"
      :class="{ active: activeTag === '' }"
      @click="$emit('update:activeTag', '')"
    >
      全部
    </button>
    <button
      v-for="tag in visibleTags"
      :key="tag"
      class="pill"
      :class="{ active: activeTag === tag }"
      @click="$emit('update:activeTag', tag)"
    >
      {{ tag }}
    </button>
    <button
      v-if="availableTags.length > 10"
      class="pill more-btn"
      @click="showAllTags = !showAllTags"
    >
      {{ showAllTags ? '收起' : `更多 ${availableTags.length - 10}` }}
    </button>
  </nav>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { ReportTag } from '@/types'

const props = defineProps<{
  /** 所有报告中出现的标签 */
  tags: ReportTag[]
  /** 当前激活的标签筛选 */
  activeTag: string
}>()

defineEmits<{
  'update:activeTag': [tag: string]
}>()

/** 去重后的可用标签列表, 保持固定顺序 */
const fixedOrder: ReportTag[] = ['日常报告', '异常报告', '周报', '日志']

const availableTags = computed(() => {
  const unique = new Set(props.tags)
  // 先按固定顺序排列已知标签, 再追加未知标签
  const sorted: string[] = []
  for (const tag of fixedOrder) {
    if (unique.has(tag)) {
      sorted.push(tag)
      unique.delete(tag)
    }
  }
  // 追加剩余未知标签
  for (const tag of unique) {
    sorted.push(tag)
  }
  return sorted
})

/** 是否展开显示全部标签 */
const showAllTags = ref(false)

/** 根据展开状态控制可见标签数量（默认只显示前10个） */
const visibleTags = computed(() => {
  if (showAllTags.value) return availableTags.value
  return availableTags.value.slice(0, 10)
})
</script>

<style scoped>
/* iOS pill 风格标签筛选栏 */
.tag-filter-bar {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding: 4px 0 12px;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
}

.tag-filter-bar::-webkit-scrollbar {
  display: none;
}

.pill {
  flex-shrink: 0;
  padding: 6px 14px;
  border-radius: 16px;
  border: none;
  font-size: 13px;
  font-weight: 500;
  font-family: inherit;
  cursor: pointer;
  transition: all 0.2s ease;
  background: var(--surface2);
  color: var(--text2);
}

.pill:active {
  transform: scale(0.95);
}

.pill.active {
  background: var(--primary);
  color: var(--text-inverse);
}

.more-btn {
  background: transparent;
  color: var(--text3);
  font-size: 12px;
}
</style>
