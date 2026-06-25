/**
 * 聊天集成 Composable — App 级别的聊天初始化
 *
 * 在 App.vue 的 setup 中调用一次:
 *   useChatIntegration()
 *
 * 负责:
 * 1. 注册 SSE 事件路由 (useRealTime -> useStreamingMessage)
 * 2. 建立实时连接 (SSE + WebSocket)
 *
 * SSE 事件路由通过 useSendMessage.ensureSSEWired 完成,
 * 将 useRealTime 接收到的 SSE 消息解析为 JSON 后,
 * 转发到 useStreamingMessage.handleSSEEvent 进行流式渲染。
 *
 * 使用方式:
 *   // App.vue setup 中
 *   useChatIntegration()
 */

import { useRealTimeSingleton } from '@/composables/useRealTime';
import { ensureSSEWired } from '@/composables/useSendMessage';
import { wireTtsPlayer } from '@/composables/useTtsPlayer';

// ==================== Composable ====================

/**
 * 初始化聊天集成
 *
 * 在 App.vue setup 中调用一次即可。
 * 负责注册 SSE 事件路由、TTS 播放器并建立实时连接。
 */
export function useChatIntegration(): void {
  // 1. 注册 SSE 事件路由 (useRealTime -> useStreamingMessage)
  //    ensureSSEWired 使用模块级标记确保只注册一次
  ensureSSEWired();

  // 2. 注册 TTS WebSocket 音频播放器
  wireTtsPlayer();

  // 3. 建立实时连接 (SSE + WebSocket)
  const rt = useRealTimeSingleton();
  rt.connect();
}
