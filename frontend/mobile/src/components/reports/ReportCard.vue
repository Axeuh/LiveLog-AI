<template>
  <div class="report-card" @click="$emit('click', report)">
    <!-- 标题 -->
    <h3 class="card-title">{{ report.title }}</h3>

    <!-- 日期 + 标签行 -->
    <div class="card-meta">
      <span class="card-date">{{ formattedDate }}</span>
      <div v-if="report.tags && report.tags.length > 0" class="card-tags">
        <span
          v-for="tag in report.tags"
          :key="tag"
          class="tag-pill"
        >
          {{ tag }}
        </span>
      </div>
    </div>

    <!-- 摘要预览 (2行截断) -->
    <p v-if="summaryText" class="card-summary">{{ summaryText }}</p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ReportItem } from '@/types'

const props = defineProps<{
  report: ReportItem
}>()

defineEmits<{
  click: [report: ReportItem]
}>()

/** 格式化日期: YYYY-MM-DD -> M月D日 */
const formattedDate = computed(() => {
  const dateStr = props.report.date
  if (!dateStr) return ''

  const parts = dateStr.split('-')
  if (parts.length !== 3) return dateStr

  const month = parseInt(parts[1], 10)
  const day = parseInt(parts[2], 10)
  return `${month}月${day}日`
})

/** 摘要文本: 从 md 内容提取前 100 个字符 */
const summaryText = computed(() => {
  const md = props.report.md
  if (!md) return ''

  // 去除 Markdown 标记, 提取纯文本
  const plain = md
    .replace(/^---[\s\S]*?---\n?/m, '') // 去除 YAML frontmatter
    .replace(/#{1,6}\s+/g, '') // 去除标题标记
    .replace(/[*_~`]+/g, '') // 去除加粗/斜体/删除线/行内代码
    .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1') // 链接保留文字
    .replace(/!\[[^\]]*\]\([^)]*\)/g, '') // 去除图片
    .replace(/^\s*[-*+]\s+/gm, '') // 去除无序列表标记
    .replace(/^\s*\d+\.\s+/gm, '') // 去除有序列表标记
    .replace(/^\s*>/gm, '') // 去除引用标记
    .replace(/\n{2,}/g, ' ') // 多换行合并为空格
    .replace(/\n/g, ' ')
    .trim()

  if (plain.length <= 100) return plain
  return plain.slice(0, 100) + '...'
})
</script>

<style scoped>
.report-card {
  background: var(--surface);
  border-radius: 16px;
  padding: 16px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 8px;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.report-card:active {
  transform: scale(0.98);
}

/* 标题 */
.card-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text);
  line-height: 1.35;
  margin: 0;
}

/* 日期 + 标签行 */
.card-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.card-date {
  font-size: 12px;
  color: var(--text3);
  flex-shrink: 0;
}

.card-tags {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.tag-pill {
  font-size: 10px;
  padding: 2px 8px;
  border-radius: 10px;
  background: var(--surface2);
  color: var(--text2);
  white-space: nowrap;
}

/* 摘要预览 (2行截断) */
.card-summary {
  font-size: 13px;
  color: var(--text2);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  margin: 0;
}
</style>
