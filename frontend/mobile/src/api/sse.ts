/**
 * SSE (Server-Sent Events) 连接管理器
 *
 * 对应 /api/screen/events/stream?token={token}
 * 接收 OpenCode AI 回复事件流
 *
 * 使用方式:
 *   import { createSSEConnection, disconnectSSE } from '@/api/sse'
 *   const sse = createSSEConnection(token, onMessage, onError)
 *   // 之后使用 disconnectSSE(sse) 断开
 *
 * 与原版一致:
 *   - 自动重连, 指数退避: [3s, 5s, 10s] (最多 3 次)
 *   - 连接成功重置重连计数
 *   - onopen / onmessage / onerror 处理
 */

import { getToken } from '@/api/client';

/** SSE 消息处理回调 */
export type SSEMessageHandler = (event: MessageEvent) => void;

/** SSE 连接状态变化回调 */
export type SSEStatusHandler = (connected: boolean) => void;

/** 重连配置 */
const RECONNECT_DELAYS = [3000, 5000, 10000];
const MAX_RECONNECT_ATTEMPTS = 3;

/**
 * 创建 SSE 连接
 *
 * @param customToken 可选: 自定义 token, 不传则使用 client.getToken()
 * @param onMessage 消息处理回调
 * @param onStatusChange 连接状态变化回调 (可选)
 * @returns EventSource 实例 (断开后设为 null)
 */
export function createSSEConnection(
  customToken?: string,
  onMessage?: SSEMessageHandler,
  onStatusChange?: SSEStatusHandler,
): EventSource | null {
  const token = customToken ?? getToken();
  if (!token) {
    console.warn('[SSE] 无 token, 无法建立 SSE 连接');
    return null;
  }

  let reconnectAttempt = 0;
  let sse: EventSource | null = null;

  function connect(): void {
    // 关闭旧连接
    if (sse) {
      sse.close();
      sse = null;
    }

    const url = '/api/screen/events/stream?token=' + encodeURIComponent(token);

    try {
      sse = new EventSource(url);
    } catch (e) {
      console.warn('[SSE] 连接失败:', e);
      scheduleReconnect();
      return;
    }

    sse.onopen = (): void => {
      console.log('[SSE] 已连接');
      reconnectAttempt = 0;
      if (onStatusChange) {
        onStatusChange(true);
      }
    };

    sse.onmessage = (event: MessageEvent): void => {
      if (onMessage) {
        onMessage(event);
      }
    };

    sse.onerror = (): void => {
      console.warn('[SSE] 连接错误');
      if (sse) {
        sse.close();
        sse = null;
      }
      if (onStatusChange) {
        onStatusChange(false);
      }
      scheduleReconnect();
    };
  }

  function scheduleReconnect(): void {
    if (reconnectAttempt >= MAX_RECONNECT_ATTEMPTS) {
      console.log('[SSE] 已达到最大重连次数 (' + MAX_RECONNECT_ATTEMPTS + '), 停止重连');
      return;
    }
    const idx = Math.min(reconnectAttempt, RECONNECT_DELAYS.length - 1);
    const delay = RECONNECT_DELAYS[idx];
    reconnectAttempt++;
    console.log('[SSE] 将在 ' + delay + 'ms 后重连 (第' + reconnectAttempt + '次)');
    setTimeout(connect, delay);
  }

  // 立即连接
  connect();

  // 返回断开函数
  return sse;
}

/**
 * 断开 SSE 连接
 */
export function disconnectSSE(sse: EventSource | null): void {
  if (sse) {
    sse.close();
    console.log('[SSE] 已断开');
  }
}

/**
 * 创建自动管理的 SSE 连接 (返回断开控制函数)
 *
 * 与 createSSEConnection 不同, 此函数返回一个 dispose 函数,
 * 适合在 Vue 组件的 onUnmounted 中调用。
 */
export function useSSEConnection(
  onMessage?: SSEMessageHandler,
  onStatusChange?: SSEStatusHandler,
): { dispose: () => void; reconnect: () => void } {
  let sse: EventSource | null = null;
  let currentToken = getToken();

  function connect(): void {
    if (sse) {
      disconnectSSE(sse);
    }
    sse = createSSEConnection(currentToken, onMessage, onStatusChange);
  }

  function dispose(): void {
    disconnectSSE(sse);
    sse = null;
  }

  function reconnect(): void {
    currentToken = getToken();
    connect();
  }

  connect();

  return { dispose, reconnect };
}
