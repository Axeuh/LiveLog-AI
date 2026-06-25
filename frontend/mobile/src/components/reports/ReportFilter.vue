<template>
  <div class="report-filter">
    <button
      class="filter-chip"
      :class="{ active: activeTag === '' }"
      @click="$emit('update:activeTag', '')"
    >
      全部
    </button>
    <button
      v-for="tag in visibleTags"
      :key="tag"
      class="filter-chip"
      :class="{ active: activeTag === tag, warn: tag === '异常报告' }"
      @click="$emit('update:activeTag', tag)"
    >
      {{ tag }}
    </button>
    <button
      v-if="availableTags.length > 10"
      class="toggle-btn"
      @click="showAllTags = !showAllTags"
    >
      {{ showAllTags ? '收起 ▲' : `更多 ${availableTags.length - 10}个标签 ▶` }}
    </button>
  </div>
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
.report-filter {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  padding: 8px 0;
  margin-bottom: 10px;
}

.filter-chip {
  font-size: 11px;
  padding: 4px 12px;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text3);
  cursor: pointer;
  font-family: inherit;
  font-weight: 500;
  transition: all 0.15s;
  white-space: nowrap;
}

.filter-chip:active {
  opacity: 0.7;
}

.filter-chip.active {
  background: var(--primary);
  color: #fff;
  border-color: var(--primary);
}

.filter-chip.warn.active {
  background: #ff6b6b;
  border-color: #ff6b6b;
}

.toggle-btn {
  font-size: 10px;
  padding: 4px 8px;
  border: none;
  background: transparent;
  color: var(--text3);
  cursor: pointer;
  font-family: inherit;
  white-space: nowrap;
}
</style>
