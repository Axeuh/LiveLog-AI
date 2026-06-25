/**
 * 发送消息 Composable — 发送消息并等待 SSE 流式完成
 *
 * 整合 useRealTime (SSE 连接) + useStreamingMessage (流式渲染) + API (消息发送)
 * 提供统一的 sendMessage 入口, 返回 Promise 在 SSE 流完成后 resolve。
 *
 * 模块初始化时自动注册 SSE 事件路由 (仅一次),
 * 将 useRealTime 收到的 SSE 事件转发到 useStreamingMessage.handleSSEEvent。
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

// ==================== 模块初始化 (SSE 路由, 仅一次) ====================

let _sseWired = false;

/**
 * 注册 SSE 事件路由 (useRealTime -> useStreamingMessage)
 *
 * 将 useRealTime 接收到的 SSE 消息解析为 JSON 后,
 * 转发到 useStreamingMessage.handleSSEEvent 处理。
 * 使用模块级标记确保只注册一次。
 */
export function ensureSSEWired(): void {
  if (_sseWired) return;
  _sseWired = true;

  const rt = useRealTimeSingleton();
  rt.onSSEMessage((event: MessageEvent) => {
    try {
      const raw = event.data;
      if (!raw || typeof raw !== 'string') return;
      const data = JSON.parse(raw);
      useStreamingMessageSingleton().handleSSEEvent(data);
    } catch (e) {
      console.error('[useSendMessage] SSE 事件解析失败:', e);
    }
  });
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

  // 确保 SSE 路由已注册 (调用 Composable 时触发, 仅首次有效)
  ensureSSEWired();

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
