<template>
  <div id="page-reports" class="page active">
    <!-- 页面状态: 加载中 / 错误 -->
    <PageState
      v-if="pageState"
      :state="pageState.state"
      :message="pageState.message"
      :description="pageState.description"
      @retry="handleRetry"
    />

    <!-- 正常内容 -->
    <template v-else>
      <!-- 筛选栏 -->
      <ReportFilter
        :tags="allTags"
        :active-tag="reportTagFilter"
        @update:active-tag="handleFilterChange"
      />

      <!-- 报告数量提示 -->
      <div class="reports-count">
        共 {{ reportCount }} 份报告
      </div>

      <!-- 空筛选结果 -->
      <PageState
        v-if="filteredReports.length === 0"
        state="empty"
        message="暂无匹配报告"
        description="尝试切换其他标签筛选"
        icon="fa-file-alt"
      />

      <!-- 报告网格 -->
      <div v-else class="report-grid">
        <ReportCard
          v-for="report in filteredReports"
          :key="report.path || report.date + report.title"
          :report="report"
          @click="handleReportClick"
        />
      </div>
    </template>

    <!-- 报告详情浮层 -->
    <DetailOverlay
      :visible="reportDetailVisible"
      :title="selectedReport?.title || ''"
      @close="reportDetailVisible = false"
    >
      <div class="report-detail-body" v-if="selectedReport?.md">
        <MarkdownContent :content="selectedReport.md" />
      </div>
    </DetailOverlay>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import PageState from '@/components/common/PageState.vue'
import DetailOverlay from '@/components/common/DetailOverlay.vue'
import MarkdownContent from '@/components/chat/MarkdownContent.vue'
import ReportCard from '@/components/reports/ReportCard.vue'
import ReportFilter from '@/components/reports/ReportFilter.vue'
import { useReportsSingleton } from '@/composables/useReports'
import { getToken } from '@/api/client'
import type { ReportItem, ReportTag } from '@/types'

// ==================== Composables ====================

const reportsApi = useReportsSingleton()

// ==================== 解构响应式状态 ====================

const loading = computed(() => reportsApi.loading.value)
const reportTagFilter = computed(() => reportsApi.reportTagFilter.value)
const filteredReports = computed(() => reportsApi.filteredReports.value)
const reportCount = computed(() => reportsApi.reportCount.value)
const reports = computed(() => reportsApi.reports.value)

// ==================== 页面状态 ====================

interface PageStateInfo {
  state: 'loading' | 'empty' | 'error'
  message: string
  description?: string
}

const pageState = computed<PageStateInfo | null>(() => {
  // 加载中且无数据
  if (loading.value && reports.value.length === 0) {
    return { state: 'loading', message: '加载中...', description: '正在加载报告列表' }
  }
  // 非加载状态且无数据 (非筛选导致)
  if (!loading.value && reports.value.length === 0 && !reportTagFilter.value) {
    return { state: 'empty', message: '暂无报告', description: 'AI 生成的报告将在这里显示' }
  }
  return null
})

// ==================== 标签筛选 ====================

/** 从所有报告中提取去重标签 */
const allTags = computed<ReportTag[]>(() => {
  const tagSet = new Set<ReportTag>()
  for (const report of reports.value) {
    if (report.tags) {
      for (const tag of report.tags) {
        tagSet.add(tag)
      }
    }
  }
  return Array.from(tagSet)
})

/** 筛选变化处理 */
function handleFilterChange(tag: string): void {
  reportsApi.onReportFilterChange(tag)
}

// ==================== 报告详情 ====================

const reportDetailVisible = ref(false)
const selectedReport = ref<ReportItem | null>(null)

async function handleReportClick(report: ReportItem): Promise<void> {
  selectedReport.value = report
  reportDetailVisible.value = true

  // 如果已加载过内容, 不再重复请求
  if (report.md) return

  // 依据 path 获取报告 Markdown 内容
  if (!report.path) return
  try {
    const token = getToken()
    const url = '/api/mobile/files/content?path=' + encodeURIComponent(report.path) + '&scope=root'
    const headers: Record<string, string> = {}
    if (token) headers['Authorization'] = 'Bearer ' + token

    const resp = await fetch(url, { headers })
    if (!resp.ok) throw new Error('HTTP ' + resp.status)

    const text = await resp.text()
    selectedReport.value = { ...report, md: text }
  } catch (e) {
    console.warn('[ReportsView] 加载报告内容失败:', e)
  }
}

// ==================== 重试 ====================

function handleRetry(): void {
  reportsApi.loadReportList()
}

// ==================== 生命周期 ====================

onMounted(() => {
  reportsApi.loadReportList()
})
</script>

<style scoped>
/* 页面容器 */
#page-reports {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  padding: 16px 20px 70px;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
}

/* 报告数量提示 */
.reports-count {
  font-size: 11px;
  color: var(--text3);
  margin-bottom: 10px;
  padding-left: 2px;
}

/* 报告网格 */
.report-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  padding-bottom: 16px;
}

/* 报告详情正文 */
.report-detail-body {
  font-size: 14px;
  line-height: 1.7;
  color: var(--text);
}
</style>
