/// <reference types="vitest/globals" />

import { describe, it, expect } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import DashboardCard from '@/components/dashboard/DashboardCard.vue'

describe('DashboardCard', () => {
  // ==================== Props 渲染 ====================

  describe('props 渲染', () => {
    it('渲染标签文本', () => {
      const wrapper = shallowMount(DashboardCard, {
        props: { blockId: 'b1', label: '心率', icon: 'fas fa-heart', color: 'red', sensor: 'hr' },
      })
      expect(wrapper.text()).toContain('心率')
    })

    it('设置 data-sensor 属性', () => {
      const wrapper = shallowMount(DashboardCard, {
        props: { blockId: 'b1', label: 'Test', icon: 'fas fa-heart', color: 'red', sensor: 'hr' },
      })
      expect(wrapper.attributes('data-sensor')).toBe('hr')
    })

    it('设置 data-block-id 属性', () => {
      const wrapper = shallowMount(DashboardCard, {
        props: { blockId: 'b1', label: 'Test', icon: 'fas fa-heart', color: 'red', sensor: 'hr' },
      })
      expect(wrapper.attributes('data-block-id')).toBe('b1')
    })
  })

  // ==================== 尺寸 ====================

  describe('尺寸类', () => {
    it('默认尺寸为 size-1', () => {
      const wrapper = shallowMount(DashboardCard, {
        props: { blockId: 'b1', label: 'Test', icon: 'fas fa-heart', color: 'red', sensor: 'hr' },
      })
      expect(wrapper.classes()).toContain('size-1')
    })

    it('size=1 时使用 size-1 类', () => {
      const wrapper = shallowMount(DashboardCard, {
        props: { blockId: 'b1', label: 'Test', icon: 'fas fa-heart', color: 'red', sensor: 'hr', size: 1 },
      })
      expect(wrapper.classes()).toContain('size-1')
    })

    it('size=2 时使用 size-2 类', () => {
      const wrapper = shallowMount(DashboardCard, {
        props: { blockId: 'b1', label: 'Test', icon: 'fas fa-heart', color: 'red', sensor: 'hr', size: 2 },
      })
      expect(wrapper.classes()).toContain('size-2')
    })

    it('size="2x2" 时使用 size-2x2 类', () => {
      const wrapper = shallowMount(DashboardCard, {
        props: { blockId: 'b1', label: 'Test', icon: 'fas fa-heart', color: 'red', sensor: 'hr', size: '2x2' },
      })
      expect(wrapper.classes()).toContain('size-2x2')
    })
  })

  // ==================== 展开/收起 ====================

  describe('展开/收起', () => {
    it('展开时 chevron 图标有 rotated 类', () => {
      const wrapper = shallowMount(DashboardCard, {
        props: { blockId: 'b1', label: 'Test', icon: 'fas fa-heart', color: 'red', sensor: 'hr', expanded: true },
      })
      const chevron = wrapper.find('.fa-chevron-down')
      expect(chevron.classes()).toContain('rotated')
    })

    it('收起时 chevron 图标无 rotated 类', () => {
      const wrapper = shallowMount(DashboardCard, {
        props: { blockId: 'b1', label: 'Test', icon: 'fas fa-heart', color: 'red', sensor: 'hr', expanded: false },
      })
      const chevron = wrapper.find('.fa-chevron-down')
      expect(chevron.classes()).not.toContain('rotated')
    })

    it('点击展开按钮发射 update:expanded(true)', async () => {
      const wrapper = shallowMount(DashboardCard, {
        props: { blockId: 'b1', label: 'Test', icon: 'fas fa-heart', color: 'red', sensor: 'hr', expanded: false },
      })
      await wrapper.find('.db-ctrl-btn--expand').trigger('click')
      expect(wrapper.emitted('update:expanded')).toBeTruthy()
      expect(wrapper.emitted('update:expanded')![0]).toEqual([true])
    })

    it('展开时点击收起按钮发射 update:expanded(false)', async () => {
      const wrapper = shallowMount(DashboardCard, {
        props: { blockId: 'b1', label: 'Test', icon: 'fas fa-heart', color: 'red', sensor: 'hr', expanded: true },
      })
      await wrapper.find('.db-ctrl-btn--expand').trigger('click')
      expect(wrapper.emitted('update:expanded')![0]).toEqual([false])
    })

    it('展开时渲染 expand 插槽', () => {
      const wrapper = shallowMount(DashboardCard, {
        props: { blockId: 'b1', label: 'Test', icon: 'fas fa-heart', color: 'red', sensor: 'hr', expanded: true },
        slots: { expand: '<div class="test-expand">扩展内容</div>' },
      })
      expect(wrapper.find('.test-expand').exists()).toBe(true)
    })

    it('收起时不渲染 expand 插槽', () => {
      const wrapper = shallowMount(DashboardCard, {
        props: { blockId: 'b1', label: 'Test', icon: 'fas fa-heart', color: 'red', sensor: 'hr', expanded: false },
        slots: { expand: '<div class="test-expand">扩展内容</div>' },
      })
      expect(wrapper.find('.test-expand').exists()).toBe(false)
    })
  })

  // ==================== 编辑模式 ====================

  describe('编辑模式', () => {
    it('编辑模式显示隐藏按钮', () => {
      const wrapper = shallowMount(DashboardCard, {
        props: { blockId: 'b1', label: 'Test', icon: 'fas fa-heart', color: 'red', sensor: 'hr', editing: true },
      })
      expect(wrapper.find('.fa-eye-slash').exists()).toBe(true)
    })

    it('编辑模式显示切换尺寸按钮', () => {
      const wrapper = shallowMount(DashboardCard, {
        props: { blockId: 'b1', label: 'Test', icon: 'fas fa-heart', color: 'red', sensor: 'hr', editing: true },
      })
      expect(wrapper.find('.fa-expand-arrows-alt').exists()).toBe(true)
    })

    it('非编辑模式不显示隐藏按钮', () => {
      const wrapper = shallowMount(DashboardCard, {
        props: { blockId: 'b1', label: 'Test', icon: 'fas fa-heart', color: 'red', sensor: 'hr', editing: false },
      })
      expect(wrapper.find('.fa-eye-slash').exists()).toBe(false)
    })

    it('非编辑模式不显示切换尺寸按钮', () => {
      const wrapper = shallowMount(DashboardCard, {
        props: { blockId: 'b1', label: 'Test', icon: 'fas fa-heart', color: 'red', sensor: 'hr', editing: false },
      })
      expect(wrapper.find('.fa-expand-arrows-alt').exists()).toBe(false)
    })

    it('编辑模式添加 db-block--editing 类', () => {
      const wrapper = shallowMount(DashboardCard, {
        props: { blockId: 'b1', label: 'Test', icon: 'fas fa-heart', color: 'red', sensor: 'hr', editing: true },
      })
      expect(wrapper.classes()).toContain('db-block--editing')
    })

    it('点击隐藏按钮发射 toggle-visibility', async () => {
      const wrapper = shallowMount(DashboardCard, {
        props: { blockId: 'b1', label: 'Test', icon: 'fas fa-heart', color: 'red', sensor: 'hr', editing: true },
      })
      await wrapper.find('[title="隐藏"]').trigger('click')
      expect(wrapper.emitted('toggle-visibility')).toBeTruthy()
    })
  })

  // ==================== 尺寸切换 ====================

  describe('尺寸切换', () => {
    it('点击切换尺寸按钮发射 update:size', async () => {
      const wrapper = shallowMount(DashboardCard, {
        props: { blockId: 'b1', label: 'Test', icon: 'fas fa-heart', color: 'red', sensor: 'hr', editing: true },
      })
      await wrapper.find('[title="切换尺寸"]').trigger('click')
      expect(wrapper.emitted('update:size')).toBeTruthy()
    })

    it('size=1 时循环到 size=2', async () => {
      const wrapper = shallowMount(DashboardCard, {
        props: { blockId: 'b1', label: 'Test', icon: 'fas fa-heart', color: 'red', sensor: 'hr', size: 1, editing: true },
      })
      await wrapper.find('[title="切换尺寸"]').trigger('click')
      expect(wrapper.emitted('update:size')![0]).toEqual([2])
    })

    it('size=2 时循环到 size="2x2"', async () => {
      const wrapper = shallowMount(DashboardCard, {
        props: { blockId: 'b1', label: 'Test', icon: 'fas fa-heart', color: 'red', sensor: 'hr', size: 2, editing: true },
      })
      await wrapper.find('[title="切换尺寸"]').trigger('click')
      expect(wrapper.emitted('update:size')![0]).toEqual(['2x2'])
    })

    it('size="2x2" 时循环到 size=1', async () => {
      const wrapper = shallowMount(DashboardCard, {
        props: { blockId: 'b1', label: 'Test', icon: 'fas fa-heart', color: 'red', sensor: 'hr', size: '2x2', editing: true },
      })
      await wrapper.find('[title="切换尺寸"]').trigger('click')
      expect(wrapper.emitted('update:size')![0]).toEqual([1])
    })
  })

  // ==================== 插槽内容 ====================

  describe('插槽内容', () => {
    it('渲染 value 插槽内容', () => {
      const wrapper = shallowMount(DashboardCard, {
        props: { blockId: 'b1', label: 'Test', icon: 'fas fa-heart', color: 'red', sensor: 'hr' },
        slots: { value: '<span class="test-value">72</span>' },
      })
      expect(wrapper.find('.test-value').exists()).toBe(true)
      expect(wrapper.find('.test-value').text()).toBe('72')
    })

    it('value 插槽为空时显示默认占位符 --', () => {
      const wrapper = shallowMount(DashboardCard, {
        props: { blockId: 'b1', label: 'Test', icon: 'fas fa-heart', color: 'red', sensor: 'hr' },
      })
      expect(wrapper.find('.cv-main').text()).toBe('--')
    })
  })
})
