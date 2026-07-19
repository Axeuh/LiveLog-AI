/**
 * 发送消息 Composable — 发送消息并等待 SSE 流式完成
 *
 * 提供统一的 sendMessage 入口, 返回 Promise 在 SSE 流完成后 resolve。
 * SSE 事件路由已由 useStreamingMessage.connectToSSE() 在 App 初始化时注册。
 *
 * 使用方式:
 *   const { sendMessage, sendError } = useSendMessage()
 *   await sendMessage('你好')
 *   if (sendError.value) { ... }
 */

import { ref, readonly, type Ref } from 'vue';
import { sendMessage as apiSendMessage } from '@/api/session';
import { useChatSingleton } from '@/composables/useChat';
import { useStreamingMessageSingleton } from '@/composables/useStreamingMessage';
import { useRealTimeSingleton } from '@/composables/useRealTime';
import { usePrefixConfig } from '@/composables/usePrefixConfig';

// ==================== 类型定义 ====================

/** useSendMessage 返回值 */
export interface UseSendMessageReturn {
  /** 发送消息, 返回 Promise 在 SSE 流完成后 resolve */
  sendMessage: (text: string) => Promise<void>;
  /** 发送错误信息 (为 null 表示无错误) */
  sendError: Readonly<Ref<string | null>>;
}

// ==================== Composable ====================

/**
 * 发送消息 Composable
 *
 * 封装发送消息 + 等待 SSE 流式完成的完整流程:
 * 1. 确保 SSE 已连接 (未连接则建立)
 * 2. 创建 pending promise (SSE message.updated 时 resolve)
 * 3. 调用 API POST /api/screen/session/message
 * 4. 等待 pending promise 完成
 * 5. API 失败时 resolve pending 并设置错误 (避免 hanging)
 */
export function useSendMessage(): UseSendMessageReturn {
  const sendError = ref<string | null>(null);

  /**
   * 发送消息并等待 SSE 流式回复完成
   *
   * @param text 消息文本
   */
  async function sendMessage(text: string): Promise<void> {
    sendError.value = null;

    const chat = useChatSingleton();
    const sessionId = chat.currentSessionId.value;
    if (!sessionId) {
      sendError.value = '无活跃会话';
      return;
    }

    // 1. 确保 SSE 已连接
    const rt = useRealTimeSingleton();
    if (!rt.sseConnected.value) {
      rt.connect();
    }

    // 2. 创建 pending promise (SSE message.updated 时 resolve)
    const sm = useStreamingMessageSingleton();
    const pending = sm.createPendingPromise();

    // 3. 调用 POST /api/screen/session/message
    let apiOk = false;
    try {
      const prefix = usePrefixConfig();
      const result = await apiSendMessage({
        session_id: sessionId,
        content: text,
        prefix_data: {
          speaker: prefix.prefixConfig.value.speaker,
          prompt: prefix.prefixConfig.value.prompt,
        },
      });
      apiOk = result !== null && result !== undefined;
    } catch (e) {
      console.error('[useSendMessage] API 发送失败:', e);
    }

    if (!apiOk) {
      // 4a. 发送失败: resolve pending promise (避免 hanging) 并设置错误
      sm.finalizeStreaming();
      sendError.value = '发送消息失败，请重试';
      return;
    }

    // 4b. 等待 SSE 流式回复完成
    // handleSSEEvent -> message.updated(assistant) -> finalizeStreaming -> resolve pending
    try {
      await pending;
    } catch (e) {
      console.error('[useSendMessage] 等待 SSE 回复异常:', e);
    }
  }

  return {
    sendMessage,
    sendError: readonly(sendError),
  };
}
