/// <reference types="vitest/globals" />

import { useStreamingMessage, type UseStreamingMessageReturn } from '@/composables/useStreamingMessage'

describe('useStreamingMessage', () => {
  let sm: UseStreamingMessageReturn

  beforeEach(() => {
    sm = useStreamingMessage()
  })

  // ==================== handleSSEEvent ====================

  describe('handleSSEEvent', () => {
    it('处理 message.part.updated text 事件', () => {
      sm.handleSSEEvent({
        type: 'message.part.updated',
        payload: {
          type: 'message.part.updated',
          properties: {
            part: { id: 'p1', type: 'text', text: 'hello' },
            messageID: 'msg1',
          },
        },
      })

      const part = sm.streamParts['p1']
      expect(part).toBeDefined()
      expect(part!.type).toBe('text')
      expect(part!.text).toBe('hello')
    })

    it('处理 message.part.updated reasoning 事件', () => {
      sm.handleSSEEvent({
        type: 'message.part.updated',
        payload: {
          type: 'message.part.updated',
          properties: {
            part: { id: 'p1', type: 'reasoning', text: '思考中...' },
          },
        },
      })

      expect(sm.streamParts['p1']?.type).toBe('reasoning')
      expect(sm.streamParts['p1']?.text).toBe('思考中...')
    })

    it('忽略 step-start / step-finish 事件', () => {
      sm.handleSSEEvent({
        type: 'message.part.updated',
        payload: {
          type: 'message.part.updated',
          properties: {
            part: { id: 'p1', type: 'step-start', text: 'start' },
          },
        },
      })

      expect(sm.streamParts['p1']).toBeUndefined()
    })

    it('忽略 proxy.connected / server.connected 事件', () => {
      sm.handleSSEEvent({
        type: 'proxy.connected',
        payload: { type: 'proxy.connected', properties: {} },
      })

      expect(sm.isStreaming.value).toBe(false)
    })

    it('处理 null/undefined 输入不报错', () => {
      expect(() => sm.handleSSEEvent(null)).not.toThrow()
      expect(() => sm.handleSSEEvent(undefined as unknown as Record<string, unknown>)).not.toThrow()
    })

    it('处理不含 payload 的事件不报错', () => {
      expect(() => sm.handleSSEEvent({ type: 'unknown' })).not.toThrow()
    })
  })

  // ==================== Delta 事件 ====================

  describe('message.part.delta', () => {
    it('追加 delta 到已存在的 part', () => {
      sm.handleSSEEvent({
        type: 'message.part.updated',
        payload: {
          type: 'message.part.updated',
          properties: {
            part: { id: 'p1', type: 'text', text: 'hello' },
          },
        },
      })

      sm.handleSSEEvent({
        type: 'message.part.delta',
        payload: {
          type: 'message.part.delta',
          properties: {
            partID: 'p1',
            field: 'text',
            delta: ' world',
          } as Record<string, unknown>,
        },
      })

      expect(sm.streamParts['p1']?.text).toBe('hello world')
    })

    it('忽略来自未知 part 的 delta', () => {
      sm.handleSSEEvent({
        type: 'message.part.delta',
        payload: {
          type: 'message.part.delta',
          properties: {
            partID: 'unknown',
            field: 'text',
            delta: ' world',
          } as Record<string, unknown>,
        },
      })

      expect(Object.keys(sm.streamParts).length).toBe(0)
    })
  })

  // ==================== message.updated ====================

  describe('message.updated', () => {
    it('收到 message.updated(assistant) 触发 finalize 使 promise resolve', async () => {
      const promise = sm.createPendingPromise()

      sm.handleSSEEvent({
        type: 'message.updated',
        payload: {
          type: 'message.updated',
          properties: {
            info: { role: 'assistant' },
          } as Record<string, unknown>,
        },
      })

      await expect(promise).resolves.toBeUndefined()
    })

    it('收到 message.updated(user) 不触发 finalize, promise 不 resolve', async () => {
      let resolved = false
      const promise = sm.createPendingPromise()
      promise.then(() => { resolved = true })

      sm.handleSSEEvent({
        type: 'message.updated',
        payload: {
          type: 'message.updated',
          properties: {
            info: { role: 'user' },
          } as Record<string, unknown>,
        },
      })

      // 等待微任务执行, 确认没有 resolve
      await new Promise((r) => setTimeout(r, 10))
      expect(resolved).toBe(false)
    })
  })

  // ==================== isStreaming ====================

  describe('isStreaming', () => {
    it('初始为 false', () => {
      expect(sm.isStreaming.value).toBe(false)
    })

    it('添加 part 后为 true', () => {
      sm.handleSSEEvent({
        type: 'message.part.updated',
        payload: {
          type: 'message.part.updated',
          properties: {
            part: { id: 'p1', type: 'text', text: 'hi' },
          },
        },
      })

      expect(sm.isStreaming.value).toBe(true)
    })

    it('clearStreaming 后恢复为 false', () => {
      sm.handleSSEEvent({
        type: 'message.part.updated',
        payload: {
          type: 'message.part.updated',
          properties: {
            part: { id: 'p1', type: 'text', text: 'hi' },
          },
        },
      })
      expect(sm.isStreaming.value).toBe(true)

      sm.clearStreaming()
      expect(sm.isStreaming.value).toBe(false)
    })
  })

  // ==================== createPendingPromise + finalizeStreaming ====================

  describe('createPendingPromise + finalizeStreaming', () => {
    it('promise 在 finalizeStreaming 时 resolve', async () => {
      const promise = sm.createPendingPromise()

      setTimeout(() => sm.finalizeStreaming(), 5)

      await expect(promise).resolves.toBeUndefined()
    })
  })

  // ==================== clearStreaming ====================

  describe('clearStreaming', () => {
    it('清除所有流式状态', () => {
      sm.handleSSEEvent({
        type: 'message.part.updated',
        payload: {
          type: 'message.part.updated',
          properties: {
            part: { id: 'p1', type: 'text', text: 'hi' },
            messageID: 'msg1',
          },
        },
      })

      expect(Object.keys(sm.streamParts).length).toBeGreaterThan(0)
      expect(sm.streamMessageId.value).toBe('msg1')

      sm.clearStreaming()

      expect(Object.keys(sm.streamParts).length).toBe(0)
      expect(sm.streamMessageId.value).toBeNull()
      expect(sm.hasPendingReply.value).toBe(false)
    })
  })
})
