/// <reference types="vitest/globals" />

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// ==================== Mock API 模块 ====================

const mockFilesApi = vi.hoisted(() => ({
  fetchDirectory: vi.fn(),
  fetchFileContent: vi.fn(),
}))

vi.mock('@/api/files', () => mockFilesApi)

// ==================== 测试 ====================

import { useFileBrowser } from '@/composables/useFileBrowser'
import type { UseFileBrowserReturn, JsonlState } from '@/composables/useFileBrowser'

describe('useFileBrowser', () => {
  let fb: UseFileBrowserReturn

  beforeEach(() => {
    vi.clearAllMocks()
    fb = useFileBrowser()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  // ==================== loadDirectory ====================

  describe('loadDirectory', () => {
    it('加载目录成功时更新 fileEntries', async () => {
      const entries = [
        { name: 'file1.txt', type: 'file' as const, size: 100 },
        { name: 'subdir', type: 'dir' as const },
      ]
      mockFilesApi.fetchDirectory.mockResolvedValue({ entries })

      await fb.loadDirectory('/')

      expect(fb.fileEntries.value).toEqual(entries)
      expect(fb.loading.value).toBe(false)
    })

    it('API 返回 null 时清空 fileEntries', async () => {
      mockFilesApi.fetchDirectory.mockResolvedValue(null)

      await fb.loadDirectory('/')

      expect(fb.fileEntries.value).toEqual([])
    })

    it('API 返回不含 entries 字段时清空', async () => {
      mockFilesApi.fetchDirectory.mockResolvedValue({})

      await fb.loadDirectory('/')

      expect(fb.fileEntries.value).toEqual([])
    })

    it('API 异常时清空 fileEntries', async () => {
      mockFilesApi.fetchDirectory.mockRejectedValue(new Error('Network error'))

      await fb.loadDirectory('/')

      expect(fb.fileEntries.value).toEqual([])
      expect(fb.loading.value).toBe(false)
    })

    it('加载期间 loading 为 true', async () => {
      let resolvePromise: (value: unknown) => void
      mockFilesApi.fetchDirectory.mockImplementation(() => {
        return new Promise((resolve) => {
          resolvePromise = resolve
        })
      })

      const promise = fb.loadDirectory('/')

      // loading 应为 true (promise pending)
      expect(fb.loading.value).toBe(true)

      // resolve 让测试完成
      resolvePromise!({ entries: [] })
      await promise

      expect(fb.loading.value).toBe(false)
    })
  })

  // ==================== loadFileContent ====================

  describe('loadFileContent', () => {
    it('返回 JSON 文件内容', async () => {
      const content = { objects: [{ t: 100, type: 'voice' }] }
      mockFilesApi.fetchFileContent.mockResolvedValue(content)

      const result = await fb.loadFileContent('/data.json')

      expect(result).toEqual(content)
      expect(mockFilesApi.fetchFileContent).toHaveBeenCalledWith('/data.json')
    })

    it('返回文本文件内容', async () => {
      mockFilesApi.fetchFileContent.mockResolvedValue('Hello world')

      const result = await fb.loadFileContent('/hello.txt')

      expect(result).toBe('Hello world')
    })

    it('API 返回 null 时返回 null', async () => {
      mockFilesApi.fetchFileContent.mockResolvedValue(null)

      const result = await fb.loadFileContent('/missing.txt')

      expect(result).toBeNull()
    })

    it('API 异常时返回 null', async () => {
      mockFilesApi.fetchFileContent.mockRejectedValue(new Error('error'))

      const result = await fb.loadFileContent('/broken.txt')

      expect(result).toBeNull()
    })
  })

  // ==================== renderJsonlPage ====================

  describe('renderJsonlPage', () => {
    it('jsonlState 为 null 时返回 null', () => {
      expect(fb.renderJsonlPage()).toBeNull()
    })

    it('返回分页切片信息', () => {
      fb.jsonlState.value = {
        objects: [{ t: 1 }, { t: 2 }, { t: 3 }, { t: 4 }, { t: 5 }],
        _allObjects: [{ t: 1 }, { t: 2 }, { t: 3 }, { t: 4 }, { t: 5 }],
        page: 1,
        pageSize: 3,
        isPerception: false,
        searchText: '',
        timeFrom: '',
        timeTo: '',
      }

      const info = fb.renderJsonlPage()

      expect(info).not.toBeNull()
      expect(info!.visibleObjects).toHaveLength(3)
      expect(info!.total).toBe(5)
      expect(info!.displayed).toBe(3)
      expect(info!.hasMore).toBe(true)
    })

    it('最后一页返回 hasMore = false', () => {
      fb.jsonlState.value = {
        objects: [{ t: 1 }, { t: 2 }, { t: 3 }],
        _allObjects: [{ t: 1 }, { t: 2 }, { t: 3 }],
        page: 1,
        pageSize: 3,
        isPerception: false,
        searchText: '',
        timeFrom: '',
        timeTo: '',
      }

      const info = fb.renderJsonlPage()

      expect(info!.displayed).toBe(3)
      expect(info!.hasMore).toBe(false)
    })

    it('空对象数组返回 displayed = 0', () => {
      fb.jsonlState.value = {
        objects: [],
        _allObjects: [],
        page: 1,
        pageSize: 3,
        isPerception: false,
        searchText: '',
        timeFrom: '',
        timeTo: '',
      }

      const info = fb.renderJsonlPage()

      expect(info!.total).toBe(0)
      expect(info!.displayed).toBe(0)
      expect(info!.hasMore).toBe(false)
    })
  })

  // ==================== loadMoreJsonl ====================

  describe('loadMoreJsonl', () => {
    it('增加页码', () => {
      fb.jsonlState.value = {
        objects: [],
        _allObjects: [],
        page: 1,
        pageSize: 3,
        isPerception: false,
        searchText: '',
        timeFrom: '',
        timeTo: '',
      }

      fb.loadMoreJsonl()

      expect(fb.jsonlState.value!.page).toBe(2)
    })

    it('jsonlState 为 null 时不报错', () => {
      expect(() => fb.loadMoreJsonl()).not.toThrow()
    })

    it('多次调用累加页码', () => {
      fb.jsonlState.value = {
        objects: [],
        _allObjects: [],
        page: 1,
        pageSize: 3,
        isPerception: false,
        searchText: '',
        timeFrom: '',
        timeTo: '',
      }

      fb.loadMoreJsonl()
      fb.loadMoreJsonl()
      fb.loadMoreJsonl()

      expect(fb.jsonlState.value!.page).toBe(4)
    })
  })

  // ==================== doJsonlSearch ====================

  describe('doJsonlSearch', () => {
    it('设置搜索文本和重置页码', () => {
      fb.jsonlState.value = {
        objects: [{ t: 1, text: 'hello' }],
        _allObjects: [{ t: 1, text: 'hello' }],
        page: 3,
        pageSize: 3,
        isPerception: false,
        searchText: '',
        timeFrom: '',
        timeTo: '',
      }

      fb.doJsonlSearch('hello')

      expect(fb.jsonlState.value!.searchText).toBe('hello')
      expect(fb.jsonlState.value!.page).toBe(1)
    })

    it('空文本清除搜索并恢复全部对象', () => {
      const all = [{ t: 1 }, { t: 2 }]
      fb.jsonlState.value = {
        objects: [{ t: 2 }],
        _allObjects: all,
        page: 1,
        pageSize: 3,
        isPerception: false,
        searchText: 'filtered',
        timeFrom: '',
        timeTo: '',
      }

      fb.doJsonlSearch('')

      expect(fb.jsonlState.value!.objects).toEqual(all)
      expect(fb.jsonlState.value!.searchText).toBe('')
    })

    it('jsonlState 为 null 时不报错', () => {
      expect(() => fb.doJsonlSearch('test')).not.toThrow()
    })
  })

  // ==================== doJsonlTimeFilter ====================

  describe('doJsonlTimeFilter', () => {
    const allObjects = [
      { t: '00:30:00' },
      { t: '06:00:00' },
      { t: '12:00:00' },
      { t: '18:00:00' },
      { t: '23:30:00' },
    ]

    beforeEach(() => {
      fb.jsonlState.value = {
        objects: [...allObjects],
        _allObjects: [...allObjects],
        page: 1,
        pageSize: 3,
        isPerception: false,
        searchText: '',
        timeFrom: '',
        timeTo: '',
      }
    })

    it('按时间范围筛选对象', () => {
      fb.doJsonlTimeFilter('06:00', '18:00')

      expect(fb.jsonlState.value!.objects).toHaveLength(3)
      expect(fb.jsonlState.value!.searchText).toBe('')
    })

    it('空 from 和 to 清除筛选', () => {
      fb.jsonlState.value!.objects = [{ t: '06:00:00' }]

      fb.doJsonlTimeFilter('', '')

      expect(fb.jsonlState.value!.objects).toEqual(allObjects)
    })

    it('未设置 timeFrom/timeTo 时更新状态', () => {
      fb.doJsonlTimeFilter('08:00', '20:00')

      expect(fb.jsonlState.value!.timeFrom).toBe('08:00')
      expect(fb.jsonlState.value!.timeTo).toBe('20:00')
    })

    it('jsonlState 为 null 时不报错', () => {
      fb = useFileBrowser()
      expect(() => fb.doJsonlTimeFilter('00:00', '12:00')).not.toThrow()
    })
  })

  // ==================== doJsonlReset ====================

  describe('doJsonlReset', () => {
    it('重置所有筛选状态', () => {
      const all = [{ t: 1 }, { t: 2 }, { t: 3 }]
      fb.jsonlState.value = {
        objects: [{ t: 1 }],
        _allObjects: all,
        page: 3,
        pageSize: 3,
        isPerception: false,
        searchText: 'test',
        timeFrom: '08:00',
        timeTo: '20:00',
      }

      fb.doJsonlReset()

      const s = fb.jsonlState.value!
      expect(s.objects).toEqual(all)
      expect(s.searchText).toBe('')
      expect(s.timeFrom).toBe('')
      expect(s.timeTo).toBe('')
      expect(s.page).toBe(1)
    })

    it('jsonlState 为 null 时不报错', () => {
      expect(() => fb.doJsonlReset()).not.toThrow()
    })
  })

  // ==================== doJsonlScrollBottom ====================

  describe('doJsonlScrollBottom', () => {
    it('跳转到最后一页', () => {
      fb.jsonlState.value = {
        objects: [1, 2, 3, 4, 5, 6, 7, 8] as any,
        _allObjects: [1, 2, 3, 4, 5, 6, 7, 8] as any,
        page: 1,
        pageSize: 3,
        isPerception: false,
        searchText: '',
        timeFrom: '',
        timeTo: '',
      }

      fb.doJsonlScrollBottom()

      expect(fb.jsonlState.value!.page).toBe(3)
    })

    it('空对象时 page 设为 0', () => {
      fb.jsonlState.value = {
        objects: [],
        _allObjects: [],
        page: 1,
        pageSize: 3,
        isPerception: false,
        searchText: '',
        timeFrom: '',
        timeTo: '',
      }

      fb.doJsonlScrollBottom()

      // Math.ceil(0 / 3) = 0
      expect(fb.jsonlState.value!.page).toBe(0)
    })

    it('jsonlState 为 null 时不报错', () => {
      expect(() => fb.doJsonlScrollBottom()).not.toThrow()
    })
  })

  // ==================== parseJsonlTime ====================

  describe('parseJsonlTime', () => {
    it('解析 HH:MM:SS 字符串', () => {
      expect(fb.parseJsonlTime('01:30:45')).toBe(1 * 3600 + 30 * 60 + 45)
    })

    it('解析 HH:MM 字符串', () => {
      expect(fb.parseJsonlTime('02:15')).toBe(2 * 3600 + 15 * 60)
    })

    it('解析数字时间戳', () => {
      expect(fb.parseJsonlTime(3661)).toBe(3661)
    })

    it('null 返回 null', () => {
      expect(fb.parseJsonlTime(null)).toBeNull()
    })

    it('undefined 返回 null', () => {
      expect(fb.parseJsonlTime(undefined)).toBeNull()
    })

    it('无效字符串返回 null', () => {
      expect(fb.parseJsonlTime('abc')).toBeNull()
    })

    it('空对象返回 null', () => {
      expect(fb.parseJsonlTime({})).toBeNull()
    })
  })

  // ==================== fmtJsonlTime ====================

  describe('fmtJsonlTime', () => {
    it('格式化 0 秒', () => {
      expect(fb.fmtJsonlTime(0)).toBe('00:00')
    })

    it('格式化 3661 秒', () => {
      expect(fb.fmtJsonlTime(3661)).toBe('01:01')
    })

    it('格式化 86399 秒 (23:59:59)', () => {
      expect(fb.fmtJsonlTime(86399)).toBe('23:59')
    })

    it('null 返回空字符串', () => {
      expect(fb.fmtJsonlTime(null)).toBe('')
    })

    it('undefined 返回空字符串', () => {
      expect(fb.fmtJsonlTime(undefined)).toBe('')
    })
  })
})
