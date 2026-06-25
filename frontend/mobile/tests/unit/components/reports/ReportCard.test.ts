/// <reference types="vitest/globals" />

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import ReportCard from '@/components/reports/ReportCard.vue'
import type { ReportItem } from '@/types'

// ==================== 工厂函数 ====================

function createReport(overrides: Partial<ReportItem> = {}): ReportItem {
  return {
    title: '健康日报',
    date: '2026-06-22',
    type: '日报',
    tags: ['日常报告'],
    path: '/reports/2026-06-22.md',
    md: '## 今日概况\n今天心率正常，步数达标。\n\n### 详细数据\n- 心率: 72bpm\n- 步数: 8000',
    ...overrides,
  }
}

// ==================== 测试 ====================

describe('ReportCard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  // ==================== 基本信息 ====================

  describe('basic info', () => {
    it('显示标题', () => {
      const wrapper = mount(ReportCard, {
        props: { report: createReport({ title: '今日报告' }) },
      })

      expect(wrapper.find('.report-title').text()).toBe('今日报告')
    })

    it('显示格式化日期 (M月D日)', () => {
      const wrapper = mount(ReportCard, {
        props: { report: createReport({ date: '2026-06-22' }) },
      })

      expect(wrapper.text()).toContain('6月22日')
    })

    it('显示报告类型', () => {
      const wrapper = mount(ReportCard, {
        props: { report: createReport({ type: '周报' }) },
      })

      expect(wrapper.find('.report-type').text()).toBe('周报')
    })

    it('无报告类型时不显示类型标签', () => {
      const wrapper = mount(ReportCard, {
        props: { report: createReport({ type: '' }) },
      })

      expect(wrapper.find('.report-type').exists()).toBe(false)
    })

    it('日期格式异常时返回原字符串', () => {
      const wrapper = mount(ReportCard, {
        props: { report: createReport({ date: '20260622' }) },
      })

      expect(wrapper.text()).toContain('20260622')
    })

    it('日期为空时显示空字符串', () => {
      const wrapper = mount(ReportCard, {
        props: { report: createReport({ date: '' }) },
      })

      // 日期间应有 fa-calendar-alt 图标, 日期部分应为空
      expect(wrapper.find('.report-date-badge').exists()).toBe(true)
    })
  })

  // ==================== 预览文本 ====================

  describe('preview text', () => {
    it('从 md 提取纯文本预览', () => {
      const wrapper = mount(ReportCard, {
        props: { report: createReport({ md: '# 标题\n正文内容' }) },
      })

      const summary = wrapper.find('.report-summary')
      // 注意: newline 被替换为空格, 所以 "标题" 和 "正文内容" 间有空格
      expect(summary.text()).toContain('标题 正文内容')
    })

    it('去除 YAML frontmatter', () => {
      const wrapper = mount(ReportCard, {
        props: {
          report: createReport({
            md: '---\ntitle: test\ndate: 2026-06-22\n---\n# 实际内容',
          }),
        },
      })

      const summary = wrapper.find('.report-summary')
      expect(summary.text()).not.toContain('title: test')
      expect(summary.text()).toContain('实际内容')
    })

    it('链接保留文字', () => {
      const wrapper = mount(ReportCard, {
        props: { report: createReport({ md: '查看[详情](https://example.com)页面' }) },
      })

      const summary = wrapper.find('.report-summary')
      expect(summary.text()).toContain('详情')
    })

    it('超过 80 字符截断并加省略号', () => {
      const longText = 'A'.repeat(100)
      const wrapper = mount(ReportCard, {
        props: { report: createReport({ md: longText }) },
      })

      const summary = wrapper.find('.report-summary')
      expect(summary.text()).toHaveLength(83) // 80 + '...'
      expect(summary.text()).toContain('...')
    })

    it('不足 80 字符不截断', () => {
      const wrapper = mount(ReportCard, {
        props: { report: createReport({ md: '简短文本' }) },
      })

      const summary = wrapper.find('.report-summary')
      expect(summary.text()).toBe('简短文本')
    })

    it('无 md 时不显示预览', () => {
      const wrapper = mount(ReportCard, {
        props: { report: createReport({ md: undefined }) },
      })

      expect(wrapper.find('.report-summary').exists()).toBe(false)
    })

    it('空 md 时不显示预览', () => {
      const wrapper = mount(ReportCard, {
        props: { report: createReport({ md: '' }) },
      })

      expect(wrapper.find('.report-summary').exists()).toBe(false)
    })
  })

  // ==================== 标签 ====================

  describe('tags', () => {
    it('显示标签列表', () => {
      const wrapper = mount(ReportCard, {
        props: { report: createReport({ tags: ['日常报告', '周报'] }) },
      })

      const tags = wrapper.findAll('.r-tag')
      expect(tags).toHaveLength(2)
      expect(tags[0].text()).toBe('日常报告')
      expect(tags[1].text()).toBe('周报')
    })

    it('无标签时不显示标签区域', () => {
      const wrapper = mount(ReportCard, {
        props: { report: createReport({ tags: undefined }) },
      })

      expect(wrapper.find('.report-tags').exists()).toBe(false)
    })

    it('空标签数组不显示', () => {
      const wrapper = mount(ReportCard, {
        props: { report: createReport({ tags: [] }) },
      })

      expect(wrapper.find('.report-tags').exists()).toBe(false)
    })

    it('异常报告标签添加 warn 类', () => {
      const wrapper = mount(ReportCard, {
        props: { report: createReport({ tags: ['异常报告', '日常报告'] }) },
      })

      const tags = wrapper.findAll('.r-tag')
      expect(tags[0].classes()).toContain('warn')
      expect(tags[1].classes()).not.toContain('warn')
    })
  })

  // ==================== 点击事件 ====================

  describe('click event', () => {
    it('点击卡片触发 click emit', async () => {
      const report = createReport()
      const wrapper = mount(ReportCard, {
        props: { report },
      })

      await wrapper.find('.report-card').trigger('click')

      expect(wrapper.emitted('click')).toBeTruthy()
      expect(wrapper.emitted('click')![0]).toEqual([report])
    })
  })
})
