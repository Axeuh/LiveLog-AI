/// <reference types="vitest/globals" />

import { describe, it, expect, vi, beforeEach } from 'vitest'

// ==================== Mock API 模块 ====================

const mockSessionApi = vi.hoisted(() => ({
  listSessions: vi.fn(),
  getSessionMessages: vi.fn(),
  sendMessage: vi.fn(),
  createSession: vi.fn(),
  switchSession: vi.fn(),
}))

const mockStreamingMethods = vi.hoisted(() => ({
  clearStreaming: vi.fn(),
  createPendingPromise: vi.fn(),
  finalizeStreaming: vi.fn(),
  buildStreamMessage: vi.fn(() => ({
    role: 'assistant',
    parts: [{ type: 'text', text: 'Hello' }],
  })),
}))

const mockUseStreamingMessageSingleton = vi.hoisted(() => vi.fn(() => ({
  clearStreaming: mockStreamingMethods.clearStreaming,
  createPendingPromise: mockStreamingMethods.createPendingPromise,
  finalizeStreaming: mockStreamingMethods.finalizeStreaming,
  buildStreamMessage: mockStreamingMethods.buildStreamMessage,
  hasPendingReply: { value: false },
  streamParts: {},
  streamCollapsed: {},
  streamMessageId: { value: null },
  isStreaming: { value: false },
})))

vi.mock('@/api/session', () => mockSessionApi)
vi.mock('@/composables/useStreamingMessage', () => ({
  useStreamingMessageSingleton: mockUseStreamingMessageSingleton,
}))

// ==================== 测试 ====================

import { useChat } from '@/composables/useChat'
import type { UseChatReturn } from '@/composables/useChat'

describe('useChat', () => {
  let chat: UseChatReturn

  beforeEach(() => {
    vi.clearAllMocks()
    // createPendingPromise 默认立即 resolve
    mockStreamingMethods.createPendingPromise.mockResolvedValue(undefined)
    chat = useChat()
  })

  // ==================== loadSessions ====================

  describe('loadSessions', () => {
    it('加载会话列表并设置当前会话（按 active 标记）', async () => {
      const sessions = [
        { id: 's1', title: 'S1', date: '今日', preview: '' },
        { id: 's2', title: 'S2', date: '昨日', preview: '', active: true },
      ]
      mockSessionApi.listSessions.mockResolvedValue(sessions)

      await chat.loadSessions()

      expect(chat.sessions.value).toEqual(sessions)
      expect(chat.currentSessionId.value).toBe('s2')
    })

    it('没有 active 会话时使用第一个会话', async () => {
      const sessions = [
        { id: 's1', title: 'S1', date: '今日', preview: '' },
        { id: 's2', title: 'S2', date: '昨日', preview: '' },
      ]
      mockSessionApi.listSessions.mockResolvedValue(sessions)

      await chat.loadSessions()

      expect(chat.currentSessionId.value).toBe('s1')
    })

    it('空会话列表不设置 currentSessionId', async () => {
      mockSessionApi.listSessions.mockResolvedValue([])

      await chat.loadSessions()

      expect(chat.sessions.value).toEqual([])
      expect(chat.currentSessionId.value).toBe('')
    })

    it('API 返回 null 不崩溃', async () => {
      mockSessionApi.listSessions.mockResolvedValue(null)

      await chat.loadSessions()

      expect(chat.sessions.value).toEqual([])
    })
  })

  // ==================== switchSession ====================

  describe('switchSession', () => {
    beforeEach(async () => {
      mockSessionApi.listSessions.mockResolvedValue([
        { id: 's1', title: 'S1', date: '今日', preview: '' },
        { id: 's2', title: 'S2', date: '昨日', preview: '' },
      ])
      mockSessionApi.getSessionMessages.mockResolvedValue([])
      mockSessionApi.switchSession.mockResolvedValue(true)
      await chat.loadSessions()
    })

    it('切换会话并加载历史消息', async () => {
      await chat.switchSession('s2')

      expect(mockStreamingMethods.clearStreaming).toHaveBeenCalled()
      expect(mockSessionApi.switchSession).toHaveBeenCalledWith('s2')
      expect(mockSessionApi.getSessionMessages).toHaveBeenCalledWith('s2')
      expect(chat.currentSessionId.value).toBe('s2')
      expect(chat.sessions.value.find((s) => s.id === 's2')?.active).toBe(true)
    })

    it('切换会话时标记目标为 active', async () => {
      await chat.switchSession('s1')

      expect(chat.sessions.value.find((s) => s.id === 's1')?.active).toBe(true)
      expect(chat.sessions.value.find((s) => s.id === 's2')?.active).toBe(false)
    })
  })

  // ==================== sendMessage ====================

  describe('sendMessage', () => {
    beforeEach(async () => {
      mockSessionApi.listSessions.mockResolvedValue([
        { id: 's1', title: 'S1', date: '今日', preview: '' },
      ])
      mockSessionApi.getSessionMessages.mockResolvedValue([])
      mockSessionApi.sendMessage.mockResolvedValue({ status: 'ok' })
      await chat.loadSessions()
    })

    it('发送消息并等待流式回复完成', async () => {
      const result = await chat.sendMessage('Hello')

      expect(result).toBe(true)
      expect(mockSessionApi.sendMessage).toHaveBeenCalledWith({
        session_id: 's1',
        content: 'Hello',
      })
      expect(mockStreamingMethods.createPendingPromise).toHaveBeenCalled()
      // 不再调用 loadChatHistory, 改用 buildStreamMessage 直接追加到消息列表
      expect(mockStreamingMethods.buildStreamMessage).toHaveBeenCalled()
      expect(chat.messages.value.length).toBe(1)
      expect(chat.messages.value[0].role).toBe('assistant')
      expect(mockSessionApi.getSessionMessages).not.toHaveBeenCalled()
    })

    it('空文本不发送', async () => {
      const result = await chat.sendMessage('')
      expect(result).toBe(false)
      expect(mockSessionApi.sendMessage).not.toHaveBeenCalled()
    })

    it('无当前会话不发送', async () => {
      // 重置 currentSessionId
      chat = useChat()
      const result = await chat.sendMessage('test')
      expect(result).toBe(false)
    })

    it('API 发送失败返回 false', async () => {
      mockSessionApi.sendMessage.mockResolvedValue(null)

      const result = await chat.sendMessage('Hello')
      expect(result).toBe(false)
      expect(mockStreamingMethods.clearStreaming).toHaveBeenCalled()
    })

    it('发送异常时返回 false', async () => {
      mockSessionApi.sendMessage.mockRejectedValue(new Error('Network error'))

      const result = await chat.sendMessage('Hello')
      expect(result).toBe(false)
      expect(mockStreamingMethods.clearStreaming).toHaveBeenCalled()
    })
  })

  // ==================== createNewSession ====================

  describe('createNewSession', () => {
    beforeEach(async () => {
      mockSessionApi.listSessions.mockResolvedValue([
        { id: 's1', title: 'S1', date: '今日', preview: '' },
      ])
      await chat.loadSessions()
    })

    it('创建新会话并添加到列表头部', async () => {
      mockSessionApi.createSession.mockResolvedValue('s2')

      const sessionId = await chat.createNewSession('新会话')

      expect(sessionId).toBe('s2')
      expect(chat.sessions.value[0].id).toBe('s2')
      expect(chat.sessions.value[0].active).toBe(true)
      expect(chat.currentSessionId.value).toBe('s2')
      // 旧会话应标记为非活跃
      expect(chat.sessions.value.find((s) => s.id === 's1')?.active).toBe(false)
    })

    it('API 创建失败返回 null', async () => {
      mockSessionApi.createSession.mockResolvedValue(null)

      const sessionId = await chat.createNewSession('测试')
      expect(sessionId).toBeNull()
    })
  })

  // ==================== loadChatHistory ====================

  describe('loadChatHistory', () => {
    it('加载会话消息', async () => {
      const messages = [
        { role: 'user' as const, content: 'Hi', timestamp: '2026-06-23T10:00:00' },
        { role: 'assistant' as const, content: 'Hello!', timestamp: '2026-06-23T10:00:05' },
      ]
      mockSessionApi.getSessionMessages.mockResolvedValue(messages)

      await chat.loadChatHistory('s1')

      expect(chat.messages.value).toEqual(messages)
      expect(chat.loadingMessages.value).toBe(false)
    })

    it('API 返回 null 时清空消息', async () => {
      mockSessionApi.getSessionMessages.mockResolvedValue(null)

      await chat.loadChatHistory('s1')

      expect(chat.messages.value).toEqual([])
    })

    it('空 sessionId 不发送请求', async () => {
      await chat.loadChatHistory('')

      expect(mockSessionApi.getSessionMessages).not.toHaveBeenCalled()
    })

    it('API 异常时清空消息', async () => {
      mockSessionApi.getSessionMessages.mockRejectedValue(new Error('error'))

      await chat.loadChatHistory('s1')

      expect(chat.messages.value).toEqual([])
    })
  })

  // ==================== clearMessages ====================

  describe('clearMessages', () => {
    it('清空本地消息', () => {
      chat.messages.value = [
        { role: 'user', content: 'test' },
      ] as any[]

      chat.clearMessages()

      expect(chat.messages.value).toEqual([])
    })
  })

  // ==================== currentSessionTitle ====================

  describe('currentSessionTitle', () => {
    it('返回当前会话标题', async () => {
      mockSessionApi.listSessions.mockResolvedValue([
        { id: 's1', title: '测试会话', date: '今日', preview: '' },
      ])
      await chat.loadSessions()

      expect(chat.currentSessionTitle.value).toBe('测试会话')
    })

    it('无当前会话时返回空字符串', () => {
      expect(chat.currentSessionTitle.value).toBe('')
    })
  })
})
