/// <reference types="vitest/globals" />

import { mount } from '@vue/test-utils'
import ChatInput from '@/components/chat/ChatInput.vue'

describe('ChatInput', () => {
  // ==================== 输入绑定 ====================

  describe('v-model input', () => {
    it('输入文本更新 input value', async () => {
      const wrapper = mount(ChatInput)
      const input = wrapper.find('input')

      await input.setValue('测试消息')

      expect((input.element as HTMLInputElement).value).toBe('测试消息')
    })
  })

  // ==================== 发送事件 ====================

  describe('send event', () => {
    it('Enter 键触发 send emit', async () => {
      const wrapper = mount(ChatInput)
      const input = wrapper.find('input')

      await input.setValue('Hello')
      await input.trigger('keydown.enter')

      expect(wrapper.emitted('send')).toBeTruthy()
      expect(wrapper.emitted('send')![0]).toEqual(['Hello'])
    })

    it('发送后清空输入框', async () => {
      const wrapper = mount(ChatInput)
      const input = wrapper.find('input')

      await input.setValue('Hello')
      await input.trigger('keydown.enter')

      expect((input.element as HTMLInputElement).value).toBe('')
    })

    it('按钮点击触发 send emit', async () => {
      const wrapper = mount(ChatInput)
      const input = wrapper.find('input')
      const button = wrapper.find('button')

      await input.setValue('点击发送')
      await button.trigger('click')

      expect(wrapper.emitted('send')).toBeTruthy()
      expect(wrapper.emitted('send')![0]).toEqual(['点击发送'])
    })

    it('空输入不触发 send', async () => {
      const wrapper = mount(ChatInput)
      const input = wrapper.find('input')

      await input.setValue('')
      await input.trigger('keydown.enter')

      expect(wrapper.emitted('send')).toBeFalsy()
    })

    it('纯空格不触发 send', async () => {
      const wrapper = mount(ChatInput)
      const input = wrapper.find('input')

      await input.setValue('   ')
      await input.trigger('keydown.enter')

      expect(wrapper.emitted('send')).toBeFalsy()
    })
  })

  // ==================== 禁用状态 ====================

  describe('disabled state', () => {
    it('disabled 时输入框不可用', () => {
      const wrapper = mount(ChatInput, {
        props: { disabled: true },
      })

      const input = wrapper.find('input')
      expect((input.element as HTMLInputElement).disabled).toBe(true)
    })

    it('disabled 时按钮不可用', () => {
      const wrapper = mount(ChatInput, {
        props: { disabled: true },
      })

      const button = wrapper.find('button')
      expect((button.element as HTMLButtonElement).disabled).toBe(true)
    })

    it('disabled 时 Enter 不触发 send', async () => {
      const wrapper = mount(ChatInput, {
        props: { disabled: true },
      })
      const input = wrapper.find('input')

      await input.setValue('Hello')
      await input.trigger('keydown.enter')

      expect(wrapper.emitted('send')).toBeFalsy()
    })

    it('disabled 时点击按钮不触发 send', async () => {
      const wrapper = mount(ChatInput, {
        props: { disabled: true },
      })
      const input = wrapper.find('input')
      const button = wrapper.find('button')

      await input.setValue('Hello')
      await button.trigger('click')

      expect(wrapper.emitted('send')).toBeFalsy()
    })

    it('输入为空时发送按钮被禁用', () => {
      const wrapper = mount(ChatInput)

      const button = wrapper.find('button')
      expect((button.element as HTMLButtonElement).disabled).toBe(true)
    })

    it('输入不为空时发送按钮可用', async () => {
      const wrapper = mount(ChatInput)
      const input = wrapper.find('input')

      await input.setValue('有内容')

      const button = wrapper.find('button')
      expect((button.element as HTMLButtonElement).disabled).toBe(false)
    })
  })
})
