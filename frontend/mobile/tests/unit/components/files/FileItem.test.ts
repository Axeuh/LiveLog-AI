/// <reference types="vitest/globals" />

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import FileItem from '@/components/files/FileItem.vue'
import type { FileEntry } from '@/types'

// ==================== Mock 依赖 ====================

vi.mock('@/api/files', () => ({
  fetchDirectory: vi.fn(),
}))

// ==================== 工厂函数 ====================

function createFileEntry(overrides: Partial<FileEntry> = {}): FileEntry {
  return {
    name: 'test.txt',
    type: 'file',
    size: 1024,
    modified_at: '2026-06-23T10:30:00',
    ...overrides,
  }
}

function createDirEntry(overrides: Partial<FileEntry> = {}): FileEntry {
  return {
    name: 'folder',
    type: 'dir',
    ...overrides,
  }
}

// ==================== 测试 ====================

describe('FileItem', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  // ==================== 文件条目渲染 ====================

  describe('file entry rendering', () => {
    it('显示文件名', () => {
      const wrapper = shallowMount(FileItem, {
        props: { entry: createFileEntry({ name: 'readme.md' }) },
      })

      expect(wrapper.find('.file-item__name').text()).toBe('readme.md')
    })

    it('显示文件图标 (根据类型)', () => {
      const wrapper = shallowMount(FileItem, {
        props: { entry: createFileEntry({ name: 'readme.md' }) },
      })

      const icon = wrapper.find('.file-item__icon i')
      expect(icon.classes()).toContain('fa-file-alt')
    })

    it('显示文件大小', () => {
      const wrapper = shallowMount(FileItem, {
        props: { entry: createFileEntry({ size: 2048 }) },
      })

      expect(wrapper.find('.file-item__size').text()).toBe('2.0 KB')
    })

    it('size 为 undefined 时不显示大小', () => {
      const wrapper = shallowMount(FileItem, {
        props: { entry: createFileEntry({ size: undefined }) },
      })

      expect(wrapper.find('.file-item__size').exists()).toBe(false)
    })

    it('显示修改日期', () => {
      const wrapper = shallowMount(FileItem, {
        props: { entry: createFileEntry({ modified_at: '2026-06-23T14:30:00' }) },
      })

      expect(wrapper.find('.file-item__date').text()).toBe('14:30')
    })

    it('modified_at 为 undefined 时不显示日期', () => {
      const wrapper = shallowMount(FileItem, {
        props: { entry: createFileEntry({ modified_at: undefined }) },
      })

      expect(wrapper.find('.file-item__date').exists()).toBe(false)
    })

    it('小文件显示 B 单位', () => {
      const wrapper = shallowMount(FileItem, {
        props: { entry: createFileEntry({ size: 500 }) },
      })

      expect(wrapper.find('.file-item__size').text()).toBe('500 B')
    })

    it('大文件显示 MB 单位', () => {
      const wrapper = shallowMount(FileItem, {
        props: { entry: createFileEntry({ size: 3 * 1024 * 1024 }) },
      })

      expect(wrapper.find('.file-item__size').text()).toBe('3.0 MB')
    })

    it('选中状态添加 selected 类', () => {
      const wrapper = shallowMount(FileItem, {
        props: { entry: createFileEntry(), isSelected: true },
      })

      expect(wrapper.classes()).toContain('selected')
    })

    it('未选中时不添加 selected 类', () => {
      const wrapper = shallowMount(FileItem, {
        props: { entry: createFileEntry() },
      })

      expect(wrapper.classes()).not.toContain('selected')
    })
  })

  // ==================== 目录条目渲染 ====================

  describe('folder entry rendering', () => {
    it('显示文件夹图标 (fa-folder)', () => {
      const wrapper = shallowMount(FileItem, {
        props: { entry: createDirEntry() },
      })

      const icon = wrapper.find('.file-item__icon i')
      expect(icon.classes()).toContain('fa-folder')
    })

    it('显示展开箭头', () => {
      const wrapper = shallowMount(FileItem, {
        props: { entry: createDirEntry() },
      })

      expect(wrapper.find('.file-item__arrow').exists()).toBe(true)
    })
  })

  // ==================== 点击文件名 ====================

  describe('click on file', () => {
    it('点击文件触发 preview emit', async () => {
      const entry = createFileEntry({ name: 'doc.txt' })
      const wrapper = shallowMount(FileItem, {
        props: { entry },
      })

      await wrapper.find('.file-item__row').trigger('click')

      expect(wrapper.emitted('preview')).toBeTruthy()
      expect(wrapper.emitted('preview')![0]).toEqual([entry, 'doc.txt'])
    })

    it('带 parentPath 时路径拼接正确', async () => {
      const entry = createFileEntry({ name: 'data.json' })
      const wrapper = shallowMount(FileItem, {
        props: { entry, parentPath: '/root/sub' },
      })

      await wrapper.find('.file-item__row').trigger('click')

      expect(wrapper.emitted('preview')![0]).toEqual([entry, '/root/sub/data.json'])
    })
  })

  // ==================== 点击文件夹 ====================

  describe('click on folder', () => {
    it('点击文件夹展开子节点', async () => {
      const wrapper = shallowMount(FileItem, {
        props: { entry: createDirEntry() },
      })

      await wrapper.find('.file-item__row').trigger('click')

      // 展开后应有子节点容器
      expect(wrapper.find('.file-item__children').exists()).toBe(true)
    })

    it('展开后箭头旋转', async () => {
      const wrapper = shallowMount(FileItem, {
        props: { entry: createDirEntry() },
      })

      await wrapper.find('.file-item__row').trigger('click')

      const arrow = wrapper.find('.file-item__arrow i')
      expect(arrow.classes()).toContain('rotated')
    })

    it('再次点击折叠子节点', async () => {
      const wrapper = shallowMount(FileItem, {
        props: { entry: createDirEntry() },
      })

      await wrapper.find('.file-item__row').trigger('click')
      expect(wrapper.find('.file-item__children').exists()).toBe(true)

      await wrapper.find('.file-item__row').trigger('click')
      expect(wrapper.find('.file-item__children').exists()).toBe(false)
    })

    it('展开后加载子目录内容', async () => {
      const { fetchDirectory } = await import('@/api/files')
      const mockFetchDir = fetchDirectory as unknown as ReturnType<typeof vi.fn>
      mockFetchDir.mockResolvedValue({
        entries: [
          { name: 'child.txt', type: 'file' },
        ],
      })

      const wrapper = shallowMount(FileItem, {
        props: { entry: createDirEntry({ name: 'parent' }) },
      })

      await wrapper.find('.file-item__row').trigger('click')

      expect(mockFetchDir).toHaveBeenCalled()
    })
  })

  // ==================== 子节点加载状态 ====================

  describe('children loading state', () => {
    it('加载中显示 LoadingSpinner', async () => {
      const { fetchDirectory } = await import('@/api/files')
      const mockFetchDir = fetchDirectory as unknown as ReturnType<typeof vi.fn>
      // 延迟 resolve 让 loading 状态保持
      mockFetchDir.mockImplementation(() => new Promise(() => {}))

      const wrapper = shallowMount(FileItem, {
        props: { entry: createDirEntry() },
      })

      await wrapper.find('.file-item__row').trigger('click')

      expect(wrapper.findComponent({ name: 'LoadingSpinner' }).exists()).toBe(true)
      // 清理
      mockFetchDir.mockReset()
      mockFetchDir.mockResolvedValue({ entries: [] })
    })

    it('空子目录显示空提示', async () => {
      const { fetchDirectory } = await import('@/api/files')
      const mockFetchDir = fetchDirectory as unknown as ReturnType<typeof vi.fn>
      mockFetchDir.mockResolvedValue({ entries: [] })

      const wrapper = shallowMount(FileItem, {
        props: { entry: createDirEntry() },
      })

      await wrapper.find('.file-item__row').trigger('click')
      await wrapper.vm.$nextTick()

      expect(wrapper.find('.file-item__empty').text()).toBe('空目录')
    })

    it('API 返回 null 时显示空提示', async () => {
      const { fetchDirectory } = await import('@/api/files')
      const mockFetchDir = fetchDirectory as unknown as ReturnType<typeof vi.fn>
      mockFetchDir.mockResolvedValue(null)

      const wrapper = shallowMount(FileItem, {
        props: { entry: createDirEntry() },
      })

      await wrapper.find('.file-item__row').trigger('click')
      await wrapper.vm.$nextTick()

      expect(wrapper.find('.file-item__empty').text()).toBe('空目录')
    })

    it('API 异常时显示空提示', async () => {
      const { fetchDirectory } = await import('@/api/files')
      const mockFetchDir = fetchDirectory as unknown as ReturnType<typeof vi.fn>
      mockFetchDir.mockRejectedValue(new Error('error'))

      const wrapper = shallowMount(FileItem, {
        props: { entry: createDirEntry() },
      })

      await wrapper.find('.file-item__row').trigger('click')
      await wrapper.vm.$nextTick()

      expect(wrapper.find('.file-item__empty').text()).toBe('空目录')
    })
  })

  // ==================== 深度缩进 ====================

  describe('depth indentation', () => {
    it('depth=0 时 paddingLeft 为 12px', () => {
      const wrapper = shallowMount(FileItem, {
        props: { entry: createFileEntry(), depth: 0 },
      })

      const row = wrapper.find('.file-item__row')
      expect(row.attributes('style')).toContain('padding-left: 12px')
    })

    it('depth=1 时 paddingLeft 为 32px (12 + 1*20)', () => {
      const wrapper = shallowMount(FileItem, {
        props: { entry: createFileEntry(), depth: 1 },
      })

      const row = wrapper.find('.file-item__row')
      expect(row.attributes('style')).toContain('padding-left: 32px')
    })

    it('depth=2 时 paddingLeft 为 52px', () => {
      const wrapper = shallowMount(FileItem, {
        props: { entry: createFileEntry(), depth: 2 },
      })

      const row = wrapper.find('.file-item__row')
      expect(row.attributes('style')).toContain('padding-left: 52px')
    })
  })

  // ==================== 格式化函数 ====================

  describe('formatSize', () => {
    it('formatSize 工具函数存在 (通过组件实例访问)', () => {
      // 格式化是组件内部函数, 通过验证渲染间接测试
      const wrapper = shallowMount(FileItem, {
        props: { entry: createFileEntry({ size: 0 }) },
      })

      expect(wrapper.find('.file-item__size').text()).toBe('0 B')
    })
  })

  describe('formatDate', () => {
    it('无效日期返回原始字符串', () => {
      const wrapper = shallowMount(FileItem, {
        props: { entry: createFileEntry({ modified_at: 'invalid-date' }) },
      })

      expect(wrapper.find('.file-item__date').text()).toBe('invalid-date')
    })
  })
})
