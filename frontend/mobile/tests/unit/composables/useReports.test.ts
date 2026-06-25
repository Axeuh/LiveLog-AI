/// <reference types="vitest/globals" />

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// ==================== Mock API 模块 ====================

const mockApiGet = vi.hoisted(() => vi.fn())

vi.mock('@/api/client', () => ({
  apiGet: mockApiGet,
}))

// ==================== 测试 ====================

import { useReports } from '@/composables/useReports'
import type { UseReportsReturn } from '@/composables/useReports'
import type { ReportItem } from '@/types'

function makeReport(overrides: Partial<ReportItem> = {}): ReportItem {
  return {
    title: '报告标题',
    date: '2026-06-22',
    type: '日报',
    tags: ['日常报告'],
    path: '/reports/2026-06-22.md',
    md: '## 测试报告\n这是报告内容。',
    ...overrides,
  }
}

describe('useReports', () => {
  let rp: UseReportsReturn

  beforeEach(() => {
    vi.clearAllMocks()
    rp = useReports()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  // ==================== loadReportList ====================

  describe('loadReportList', () => {
    it('加载报告列表成功', async () => {
      const reports = [makeReport()]
      mockApiGet.mockResolvedValue({ reports })

      await rp.loadReportList()

      expect(rp.reports.value).toEqual(reports)
      expect(rp.loading.value).toBe(false)
    })

    it('API 返回空数组时清空列表', async () => {
      mockApiGet.mockResolvedValue({ reports: [] })

      await rp.loadReportList()

      expect(rp.reports.value).toEqual([])
    })

    it('API 返回 null 时清空列表', async () => {
      mockApiGet.mockResolvedValue(null)

      await rp.loadReportList()

      expect(rp.reports.value).toEqual([])
    })

    it('API 异常时清空列表', async () => {
      mockApiGet.mockRejectedValue(new Error('Network error'))

      await rp.loadReportList()

      expect(rp.reports.value).toEqual([])
      expect(rp.loading.value).toBe(false)
    })

    it('使用 filter 参数时更新 reportTagFilter', async () => {
      mockApiGet.mockResolvedValue({ reports: [] })

      await rp.loadReportList('异常报告')

      expect(rp.reportTagFilter.value).toBe('异常报告')
    })

    it('带标签筛选时 URL 包含 tag 参数', async () => {
      mockApiGet.mockResolvedValue({ reports: [] })
      rp.reportTagFilter.value = '异常报告'

      await rp.loadReportList()

      expect(mockApiGet).toHaveBeenCalledWith(
        expect.stringContaining('tag=%E5%BC%82%E5%B8%B8%E6%8A%A5%E5%91%8A'),
      )
    })

    it('空标签时不添加 tag 参数', async () => {
      mockApiGet.mockResolvedValue({ reports: [] })

      await rp.loadReportList()

      expect(mockApiGet).toHaveBeenCalledWith(
        expect.not.stringContaining('tag='),
      )
    })

    it('加载期间 loading 为 true', async () => {
      let resolvePromise: (value: unknown) => void
      mockApiGet.mockImplementation(() => {
        return new Promise((resolve) => {
          resolvePromise = resolve
        })
      })

      const promise = rp.loadReportList()

      // loading 应为 true (promise pending)
      expect(rp.loading.value).toBe(true)

      // resolve 让测试完成
      resolvePromise!({ reports: [] })
      await promise

      expect(rp.loading.value).toBe(false)
    })
  })

  // ==================== onReportFilterChange ====================

  describe('onReportFilterChange', () => {
    it('更新标签并重新加载', async () => {
      mockApiGet.mockResolvedValue({ reports: [makeReport({ tags: ['周报'] })] })

      rp.onReportFilterChange('周报')

      expect(rp.reportTagFilter.value).toBe('周报')
      // loadReportList 是异步的, 等待它完成
      await new Promise(process.nextTick)
      expect(mockApiGet).toHaveBeenCalledWith(
        expect.stringContaining('tag=%E5%91%A8%E6%8A%A5'),
      )
    })

    it('空字符串清除筛选', async () => {
      mockApiGet.mockResolvedValue({ reports: [makeReport()] })
      rp.reportTagFilter.value = '异常报告'

      rp.onReportFilterChange('')

      expect(rp.reportTagFilter.value).toBe('')
    })
  })

  // ==================== filteredReports ====================

  describe('filteredReports', () => {
    it('无筛选时返回所有报告', () => {
      rp.reports.value = [
        makeReport({ title: 'A', date: '2026-06-22', tags: ['日常报告'] }),
        makeReport({ title: 'B', date: '2026-06-21', tags: ['异常报告'] }),
      ]

      expect(rp.filteredReports.value).toHaveLength(2)
    })

    it('按标签筛选报告', () => {
      rp.reports.value = [
        makeReport({ title: 'A', date: '2026-06-22', tags: ['日常报告'] }),
        makeReport({ title: 'B', date: '2026-06-21', tags: ['异常报告'] }),
        makeReport({ title: 'C', date: '2026-06-20', tags: ['日常报告'] }),
      ]
      rp.reportTagFilter.value = '异常报告'

      const filtered = rp.filteredReports.value
      expect(filtered).toHaveLength(1)
      expect(filtered[0].title).toBe('B')
    })

    it('标签筛选不区分标签顺序', () => {
      rp.reports.value = [
        makeReport({ title: 'A', date: '2026-06-22', tags: ['日报', '日常报告'] }),
      ]
      rp.reportTagFilter.value = '日报'

      expect(rp.filteredReports.value).toHaveLength(1)
    })

    it('无匹配标签时返回空数组', () => {
      rp.reports.value = [
        makeReport({ title: 'A', date: '2026-06-22', tags: ['日常报告'] }),
      ]
      rp.reportTagFilter.value = '周报'

      expect(rp.filteredReports.value).toHaveLength(0)
    })

    it('报告无 tags 时不被筛选排除', () => {
      rp.reports.value = [
        makeReport({ title: 'A', date: '2026-06-22', tags: [] }),
        makeReport({ title: 'B', date: '2026-06-21', tags: undefined }),
      ]

      expect(rp.filteredReports.value).toHaveLength(2)
    })

    it('按日期降序排序', () => {
      rp.reports.value = [
        makeReport({ title: 'C', date: '2026-06-20' }),
        makeReport({ title: 'A', date: '2026-06-22' }),
        makeReport({ title: 'B', date: '2026-06-21' }),
      ]

      const titles = rp.filteredReports.value.map((r) => r.title)
      expect(titles).toEqual(['A', 'B', 'C'])
    })

    it('返回新数组不修改原数组', () => {
      const original = [
        makeReport({ title: 'B', date: '2026-06-21' }),
        makeReport({ title: 'A', date: '2026-06-22' }),
      ]
      rp.reports.value = original

      const filtered = rp.filteredReports.value
      expect(filtered).not.toBe(original)
      // 原数组顺序不变
      expect(original[0].title).toBe('B')
    })
  })

  // ==================== reportCount ====================

  describe('reportCount', () => {
    it('返回筛选后的报告数量', () => {
      rp.reports.value = [
        makeReport({ tags: ['日常报告'] }),
        makeReport({ tags: ['异常报告'] }),
        makeReport({ tags: ['日常报告'] }),
      ]
      rp.reportTagFilter.value = '日常报告'

      expect(rp.reportCount.value).toBe(2)
    })

    it('空列表返回 0', () => {
      rp.reports.value = []

      expect(rp.reportCount.value).toBe(0)
    })
  })
})
