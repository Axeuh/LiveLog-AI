/// <reference types="vitest/globals" />

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'

// ==================== Mock Composables ====================

const mockRouterPush = vi.hoisted(() => vi.fn())

const mockApi = vi.hoisted(() => ({
  isLoggedIn: { value: true },
  token: 'test-token-12345',
  logout: vi.fn(),
  onAuthFail: vi.fn(),
  offAuthFail: vi.fn(),
}))

const mockRealTime = vi.hoisted(() => ({
  connectionState: { value: 'connected' },
  sseConnected: { value: true },
  wsConnected: { value: true },
}))

const mockListSessions = vi.hoisted(() => vi.fn().mockResolvedValue([]))
const mockFetchCurrentSessionId = vi.hoisted(() => vi.fn().mockResolvedValue(null))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mockRouterPush }),
}))

vi.mock('@/composables/useApi', () => ({
  useApi: () => mockApi,
  listSessions: mockListSessions,
  fetchCurrentSessionId: mockFetchCurrentSessionId,
}))

vi.mock('@/composables/useRealTime', () => ({
  useRealTimeSingleton: () => mockRealTime,
}))

// ==================== Helpers ====================

function mountSettingsView() {
  return mount(SettingsView)
}

import SettingsView from '@/views/SettingsView.vue'

describe('SettingsView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // 重置 mock 默认值
    mockApi.isLoggedIn.value = true
    mockApi.logout.mockClear()
    mockRouterPush.mockClear()
    mockRealTime.connectionState.value = 'connected'
    mockRealTime.sseConnected.value = true
    mockRealTime.wsConnected.value = true
    mockListSessions.mockResolvedValue([])
    mockFetchCurrentSessionId.mockResolvedValue(null)
    vi.stubGlobal('confirm', vi.fn(() => true))
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  // ==================== 渲染 ====================

  describe('rendering', () => {
    it('渲染页面标题', () => {
      const wrapper = mountSettingsView()
      expect(wrapper.find('.settings-header').exists()).toBe(true)
      expect(wrapper.find('.settings-header h1').text()).toBe('设置')
    })

    it('渲染连接状态区域', () => {
      const wrapper = mountSettingsView()
      const statusItems = wrapper.findAll('.status-item')
      expect(statusItems.length).toBe(3)
      expect(statusItems[0].text()).toContain('服务器')
      expect(statusItems[1].text()).toContain('SSE')
      expect(statusItems[2].text()).toContain('WebSocket')
    })

    it('渲染系统信息区域', () => {
      const wrapper = mountSettingsView()
      const infoItems = wrapper.findAll('.info-item')
      expect(infoItems.length).toBe(4)
      expect(infoItems[0].text()).toContain('登录状态')
      expect(infoItems[1].text()).toContain('屏幕尺寸')
      expect(infoItems[2].text()).toContain('DPR')
      expect(infoItems[3].text()).toContain('在线状态')
    })

    it('渲染 DebugPanel 开关', () => {
      const wrapper = mountSettingsView()
      expect(wrapper.find('.debug-toggle').exists()).toBe(true)
      expect(wrapper.find('.debug-toggle').text()).toContain('调试信息')
    })

    it('渲染退出登录按钮', () => {
      const wrapper = mountSettingsView()
      const btn = wrapper.find('.logout-btn')
      expect(btn.exists()).toBe(true)
      expect(btn.text()).toContain('退出登录')
    })

    it('渲染版本信息', () => {
      const wrapper = mountSettingsView()
      const version = wrapper.find('.version-info')
      expect(version.exists()).toBe(true)
      expect(version.text()).toContain('Axeuh Health Monitor')
      expect(version.text()).toContain('v1.0.0')
    })
  })

  // ==================== 连接状态 ====================

  describe('connection state', () => {
    it('connected 状态显示已连接', () => {
      mockRealTime.connectionState.value = 'connected'
      const wrapper = mountSettingsView()
      expect(wrapper.text()).toContain('已连接')
      expect(wrapper.find('.status-dot--success').exists()).toBe(true)
    })

    it('connecting 状态显示连接中...', () => {
      mockRealTime.connectionState.value = 'connecting'
      const wrapper = mountSettingsView()
      expect(wrapper.text()).toContain('连接中...')
    })

    it('disconnected 状态显示已断开', () => {
      mockRealTime.connectionState.value = 'disconnected'
      mockRealTime.sseConnected.value = false
      mockRealTime.wsConnected.value = false
      const wrapper = mountSettingsView()
      expect(wrapper.text()).toContain('已断开')
      expect(wrapper.find('.status-dot--error').exists()).toBe(true)
    })

    it('SSE 连接状态显示', () => {
      mockRealTime.sseConnected.value = true
      const wrapper = mountSettingsView()
      const statusItems = wrapper.findAll('.status-item')
      expect(statusItems[1].text()).toContain('已连接')

      mockRealTime.sseConnected.value = false
      const wrapper2 = mountSettingsView()
      const statusItems2 = wrapper2.findAll('.status-item')
      expect(statusItems2[1].text()).toContain('未连接')
    })

    it('WebSocket 连接状态显示', () => {
      mockRealTime.wsConnected.value = true
      const wrapper = mountSettingsView()
      const statusItems = wrapper.findAll('.status-item')
      expect(statusItems[2].text()).toContain('已连接')

      mockRealTime.wsConnected.value = false
      const wrapper2 = mountSettingsView()
      const statusItems2 = wrapper2.findAll('.status-item')
      expect(statusItems2[2].text()).toContain('未连接')
    })
  })

  // ==================== 登录状态 ====================

  describe('login status', () => {
    it('登录状态显示已登录', () => {
      mockApi.isLoggedIn.value = true
      const wrapper = mountSettingsView()
      expect(wrapper.text()).toContain('已登录')
      expect(wrapper.find('.text-success').exists()).toBe(true)
    })

    it('未登录状态显示未登录', () => {
      mockApi.isLoggedIn.value = false
      const wrapper = mountSettingsView()
      expect(wrapper.text()).toContain('未登录')
      expect(wrapper.find('.text-error').exists()).toBe(true)
    })
  })

  // ==================== 退出登录 ====================

  describe('logout interaction', () => {
    it('确认退出时调用 logout 并跳转到 /chat', async () => {
      vi.stubGlobal('confirm', vi.fn(() => true))
      const wrapper = mountSettingsView()
      await wrapper.find('.logout-btn').trigger('click')

      expect(mockApi.logout).toHaveBeenCalledOnce()
      expect(mockRouterPush).toHaveBeenCalledWith('/chat')
    })

    it('取消退出时不做任何操作', async () => {
      vi.stubGlobal('confirm', vi.fn(() => false))
      const wrapper = mountSettingsView()
      await wrapper.find('.logout-btn').trigger('click')

      expect(mockApi.logout).not.toHaveBeenCalled()
      expect(mockRouterPush).not.toHaveBeenCalled()
    })
  })

  // ==================== Debug 面板 ====================

  describe('debug panel toggle', () => {
    it('点击切换 Debug 面板展开/折叠', async () => {
      const wrapper = mountSettingsView()

      // 初始折叠
      expect(wrapper.find('.debug-content').exists()).toBe(false)

      // 点击展开
      await wrapper.find('.debug-toggle').trigger('click')
      expect(wrapper.find('.debug-content').exists()).toBe(true)
      expect(wrapper.find('.debug-toggle__arrow.rotated').exists()).toBe(true)

      // 再次点击折叠
      await wrapper.find('.debug-toggle').trigger('click')
      expect(wrapper.find('.debug-content').exists()).toBe(false)
      expect(wrapper.find('.debug-toggle__arrow.rotated').exists()).toBe(false)
    })

    it('展开 Debug 面板后显示连接和会话信息', async () => {
      const wrapper = mountSettingsView()
      await wrapper.find('.debug-toggle').trigger('click')

      expect(wrapper.find('.debug-content').text()).toContain('API')
      expect(wrapper.find('.debug-content').text()).toContain('实时连接')
      expect(wrapper.find('.debug-content').text()).toContain('会话信息')
      expect(wrapper.find('.debug-content').text()).toContain('客户端信息')
    })
  })
})
