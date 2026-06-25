<template>
  <div class="report-card" @click="$emit('click', report)">
    <!-- 日期 + 类型 -->
    <div class="report-date-badge">
      <i class="fas fa-calendar-alt"></i>
      <span>{{ formattedDate }}</span>
      <span v-if="report.type" class="report-type">{{ report.type }}</span>
    </div>

    <!-- 标题 -->
    <h3 class="report-title">{{ report.title }}</h3>

    <!-- 预览文本 -->
    <p v-if="previewText" class="report-summary">{{ previewText }}</p>

    <!-- 标签 -->
    <div v-if="report.tags && report.tags.length > 0" class="report-tags">
      <span
        v-for="tag in report.tags"
        :key="tag"
        class="r-tag"
        :class="{ warn: tag === '异常报告' }"
      >
        {{ tag }}
      </span>
    </div>
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

/** 预览文本: 从 md 内容提取前 80 个字符 */
const previewText = computed(() => {
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

  if (plain.length <= 80) return plain
  return plain.slice(0, 80) + '...'
})
</script>

<style scoped>
.report-card {
  background: var(--surface);
  border-radius: var(--radius-sm);
  padding: 16px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 6px;
  transition: transform 0.15s, background 0.15s;
}

.report-card:active {
  transform: scale(0.97);
  background: var(--surface2);
}

.report-date-badge {
  font-size: 10px;
  color: var(--text3);
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 2px;
}

.report-date-badge i {
  font-size: 10px;
  opacity: 0.7;
}

.report-type {
  display: inline-block;
  font-size: 9px;
  padding: 1px 6px;
  border-radius: 3px;
  margin-left: 6px;
  background: var(--surface3);
  color: var(--text2);
}

.report-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
  line-height: 1.3;
  margin: 0;
}

.report-summary {
  font-size: 11px;
  color: var(--text2);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
  margin: 0;
}

.report-tags {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  margin-top: 2px;
}

.r-tag {
  font-size: 9px;
  padding: 1px 6px;
  border-radius: 3px;
  background: rgba(255, 255, 255, 0.05);
  color: var(--text2);
}

.r-tag.warn {
  background: rgba(255, 107, 107, 0.12);
  color: #ff6b6b;
}
</style>
