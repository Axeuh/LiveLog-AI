/// <reference types="vitest/globals" />

import { shallowMount } from '@vue/test-utils'
import MessageBubble from '@/components/chat/MessageBubble.vue'
import MarkdownContent from '@/components/chat/MarkdownContent.vue'
import type { ChatMessage } from '@/types'

function createMessage(overrides: Partial<ChatMessage> = {}): ChatMessage {
  return {
    content: '',
    role: 'user' as const,
    timestamp: '2026-06-23T10:30:00',
    ...overrides,
  }
}

describe('MessageBubble', () => {
  // ==================== AI 角色 ====================

  describe('role = ai', () => {
    it('渲染 AI 头像', () => {
      const wrapper = shallowMount(MessageBubble, {
        props: {
          message: createMessage({ content: 'Hello' }),
          role: 'ai',
        },
      })

      const avatar = wrapper.find('.avatar')
      expect(avatar.exists()).toBe(true)
      expect(avatar.text()).toBe('AI')
    })

    it('添加 .message.ai 类', () => {
      const wrapper = shallowMount(MessageBubble, {
        props: {
          message: createMessage({ content: 'Hello' }),
          role: 'ai',
        },
      })

      expect(wrapper.classes()).toContain('ai')
    })

    it('传递 content 给 MarkdownContent 组件', () => {
      const wrapper = shallowMount(MessageBubble, {
        props: {
          message: createMessage({ content: '**bold**' }),
          role: 'ai',
        },
      })

      const mdContent = wrapper.findComponent(MarkdownContent)
      expect(mdContent.exists()).toBe(true)
      expect(mdContent.props('content')).toBe('**bold**')
    })

    it('优先使用 parts 中的文本', () => {
      const wrapper = shallowMount(MessageBubble, {
        props: {
          message: createMessage({
            content: 'fallback',
            parts: [{ type: 'text', text: 'parts-text' }],
          }),
          role: 'ai',
        },
      })

      const mdContent = wrapper.findComponent(MarkdownContent)
      expect(mdContent.props('content')).toBe('parts-text')
    })

    it('合并多个 text parts', () => {
      const wrapper = shallowMount(MessageBubble, {
        props: {
          message: createMessage({
            parts: [
              { type: 'text', text: 'Hello ' },
              { type: 'text', text: 'World' },
            ],
          }),
          role: 'ai',
        },
      })

      const mdContent = wrapper.findComponent(MarkdownContent)
      expect(mdContent.props('content')).toBe('Hello World')
    })
  })

  // ==================== 用户角色 ====================

  describe('role = user', () => {
    it('渲染用户头像', () => {
      const wrapper = shallowMount(MessageBubble, {
        props: {
          message: createMessage({ content: 'Hello' }),
          role: 'user',
        },
      })

      const avatar = wrapper.find('.avatar')
      expect(avatar.exists()).toBe(true)
      expect(avatar.text()).toBe('我')
    })

    it('添加 .message.user 类', () => {
      const wrapper = shallowMount(MessageBubble, {
        props: {
          message: createMessage({ content: 'Hello' }),
          role: 'user',
        },
      })

      expect(wrapper.classes()).toContain('user')
    })

    it('显示纯文本（不渲染 Markdown）', () => {
      const wrapper = shallowMount(MessageBubble, {
        props: {
          message: createMessage({ content: '用户消息' }),
          role: 'user',
        },
      })

      expect(wrapper.text()).toContain('用户消息')
      // 用户消息不应包含 MarkdownContent
      expect(wrapper.findComponent(MarkdownContent).exists()).toBe(false)
    })
  })

  // ==================== 时间戳 ====================

  describe('timestamp', () => {
    it('显示格式化的时间 (HH:MM)', () => {
      const wrapper = shallowMount(MessageBubble, {
        props: {
          message: createMessage({ timestamp: '2026-06-23T10:30:00' }),
          role: 'user',
        },
      })

      expect(wrapper.text()).toContain('10:30')
    })

    it('使用 created_at 作为备选时间戳', () => {
      const wrapper = shallowMount(MessageBubble, {
        props: {
          message: createMessage({
            timestamp: undefined,
            created_at: '2026-06-23T14:45:00',
          }),
          role: 'user',
        },
      })

      expect(wrapper.text()).toContain('14:45')
    })

    it('无时间戳时不显示时间', () => {
      const wrapper = shallowMount(MessageBubble, {
        props: {
          message: createMessage({
            timestamp: undefined,
            created_at: undefined,
          }),
          role: 'user',
        },
      })

      expect(wrapper.find('.msg-time').exists()).toBe(false)
    })

    it('无效时间戳不显示', () => {
      const wrapper = shallowMount(MessageBubble, {
        props: {
          message: createMessage({ timestamp: 'invalid-date' }),
          role: 'user',
        },
      })

      expect(wrapper.find('.msg-time').exists()).toBe(false)
    })
  })
})
