/**
 * WebSocket 连接管理器 (主 /ws)
 *
 * 对应 ws://{host}/ws?token={token}
 * 用于实时数据推送 (如通知、状态更新)
 *
 * 使用方式:
 *   import { createWsConnection, disconnectWs } from '@/api/ws'
 *   const ws = createWsConnection(token, { onMessage: (data) => ... })
 *   // 之后使用 disconnectWs(ws) 断开
 *
 * 与原版一致:
 *   - 自动重连, 指数退避: 3s * 2^attempt, 最大 30s
 *   - wsReconnectAttempt 跨连接持续 (原版全局变量)
 *   - onopen 重置重连计数
 */

import { getToken } from '@/api/client';

// ==================== 类型 ====================

/** WS 消息回调 */
export type WSMessageHandler = (data: unknown) => void;

/** WS 状态回调 */
export type WSStatusHandler = (connected: boolean) => void;

/** WS 连接配置 */
export interface WSOptions {
  /** 消息处理回调 */
  onMessage?: WSMessageHandler;
  /** 连接状态变化回调 */
  onStatusChange?: WSStatusHandler;
  /** 最大重连间隔 (ms), 默认 30000 */
  maxDelay?: number;
  /** 初始重连延迟 (ms), 默认 3000 */
  initialDelay?: number;
}

// ==================== 连接管理 ====================

/**
 * 创建 WebSocket 连接
 *
 * @param customToken 可选: 自定义 token, 不传则使用 client.getToken()
 * @param options 连接配置
 * @returns WebSocket 实例 (断开后设为 null)
 */
export function createWsConnection(
  customToken?: string,
  options?: WSOptions,
): WebSocket | null {
  const token = customToken ?? getToken();
  if (!token) {
    console.warn('[WS] 无 token, 无法建立 WebSocket 连接');
    return null;
  }

  const maxDelay = options?.maxDelay ?? 30000;
  const initialDelay = options?.initialDelay ?? 3000;
  let reconnectAttempt = 0;
  let ws: WebSocket | null = null;

  function connect(): void {
    const protocol = location.protocol === 'https:' ? 'wss://' : 'ws://';
    const wsUrl = protocol + location.host + '/ws?token=' + encodeURIComponent(token);

    try {
      ws = new WebSocket(wsUrl);
    } catch (e) {
      console.warn('[WS] 连接失败:', e);
      scheduleReconnect();
      return;
    }

    ws.onopen = (): void => {
      console.log('[WS] 已连接');
      reconnectAttempt = 0;
      if (options?.onStatusChange) {
        options.onStatusChange(true);
      }
    };

    ws.onmessage = (event: MessageEvent): void => {
      try {
        const data = JSON.parse(event.data as string);
        if (options?.onMessage) {
          options.onMessage(data);
        }
      } catch (e) {
        console.warn('[WS] 消息解析失败:', e);
      }
    };

    ws.onclose = (): void => {
      console.log('[WS] 已断开');
      if (options?.onStatusChange) {
        options.onStatusChange(false);
      }
      scheduleReconnect();
    };

    ws.onerror = (e: Event): void => {
      console.warn('[WS] 错误:', e);
    };
  }

  function scheduleReconnect(): void {
    const delay = Math.min(
      initialDelay * Math.pow(2, reconnectAttempt),
      maxDelay,
    );
    reconnectAttempt++;
    console.log('[WS] 将在 ' + delay + 'ms 后重连 (第' + reconnectAttempt + '次)');
    setTimeout(connect, delay);
  }

  // 立即连接
  connect();

  return ws;
}

/**
 * 断开 WebSocket 连接 (不触发重连)
 */
export function disconnectWs(ws: WebSocket | null): void {
  if (ws) {
    // 移除事件处理器, 防止 onclose 触发重连
    ws.onclose = null;
    ws.onerror = null;
    ws.onmessage = null;
    ws.onopen = null;
    ws.close();
    console.log('[WS] 已断开 (主动)');
  }
}

/**
 * 创建自动管理的 WebSocket 连接
 *
 * 返回 { dispose, reconnect } 控制函数,
 * dispose 适合在 Vue 组件的 onUnmounted 中调用。
 */
export function useWsConnection(
  options?: WSOptions,
): { dispose: () => void; reconnect: () => void } {
  let ws: WebSocket | null = null;
  let currentToken = getToken();

  function connect(): void {
    if (ws) {
      disconnectWs(ws);
    }
    ws = createWsConnection(currentToken, options);
  }

  function dispose(): void {
    disconnectWs(ws);
    ws = null;
  }

  function reconnect(): void {
    currentToken = getToken();
    connect();
  }

  connect();

  return { dispose, reconnect };
}
