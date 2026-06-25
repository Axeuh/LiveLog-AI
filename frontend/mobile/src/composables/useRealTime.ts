/**
 * 实时连接 Composable — SSE + WebSocket 连接生命周期管理
 *
 * 统一管理 SSE (/api/screen/events/stream) 和 WebSocket (/ws) 连接,
 * 支持自动重连 (指数退避)。
 *
 * 使用方式:
 *   const { connectionState, connect, disconnect, onSSEMessage } = useRealTime()
 *   connect()  // 同时建立 SSE + WS
 *   // 监听 SSE 消息
 *   onSSEMessage((data) => console.log('SSE:', data))
 *   disconnect()  // 断开所有
 */

import { ref, readonly, type InjectionKey, type Ref } from 'vue';
import { createSSEConnection, disconnectSSE } from '@/api/sse';
import { createWsConnection, disconnectWs } from '@/api/ws';
import type { WSMessageHandler } from '@/api/ws';
import type { SSEMessageHandler } from '@/api/sse';

// ==================== 类型定义 ====================

/** 连接状态 */
export type ConnectionState = 'disconnected' | 'connecting' | 'connected';

/** useRealTime 返回值 */
export interface UseRealTimeReturn {
  /** 当前连接状态 */
  connectionState: Readonly<Ref<ConnectionState>>;
  /** SSE 是否已连接 */
  sseConnected: Readonly<Ref<boolean>>;
  /** WebSocket 是否已连接 */
  wsConnected: Readonly<Ref<boolean>>;
  /** 建立 SSE + WS 连接 (幂等) */
  connect: () => void;
  /** 断开 SSE + WS 连接 (同时停止重连) */
  disconnect: () => void;
  /** 仅断开并重连 SSE */
  reconnectSSE: () => void;
  /** 仅断开并重连 WS */
  reconnectWS: () => void;
  /** 注册 SSE 消息监听 */
  onSSEMessage: (handler: SSEMessageHandler) => void;
  /** 移除 SSE 消息监听 */
  offSSEMessage: (handler: SSEMessageHandler) => void;
  /** 注册 WS 消息监听 */
  onWSMessage: (handler: WSMessageHandler) => void;
  /** 移除 WS 消息监听 */
  offWSMessage: (handler: WSMessageHandler) => void;
}

/** useRealTime 注入 key */
export const USE_REAL_TIME_KEY: InjectionKey<UseRealTimeReturn> =
  Symbol('useRealTime');

// ==================== 内部状态 ====================

/** SSE EventSource 实例引用 */
let _sse: EventSource | null = null;
/** WebSocket 实例引用 */
let _ws: WebSocket | null = null;
/** SSE 重连尝试次数 */
let _sseReconnectAttempt = 0;
/** SSE 重连定时器 ID */
let _sseReconnectTimer: ReturnType<typeof setTimeout> | null = null;
/** 是否已明确断开 (不再重连) */
let _disconnectedByUser = false;

/** SSE 重连延迟 [s] */
const SSE_RECONNECT_DELAYS = [3, 5, 10];
/** WS 重连参数 (秒) */
const WS_INITIAL_DELAY = 3;
/** WS 最大重连间隔 (ms) */
const WS_MAX_DELAY_MS = 30000;

// ==================== Composable ====================

/**
 * 实时连接 Composable — SSE + WebSocket 连接生命周期管理
 *
 * 管理连接建立、断开、自动重连 (指数退避)。
 * SSE 最多重连 3 次，WS 无限重连 (指数退避 3s, 6s, 12s, ... 最大 30s)。
 */
export function useRealTime(): UseRealTimeReturn {
  const connectionState = ref<ConnectionState>('disconnected');
  const sseConnected = ref(false);
  const wsConnected = ref(false);

  /** SSE 消息处理器列表 */
  const _sseHandlers: SSEMessageHandler[] = [];
  /** WS 消息处理器列表 */
  const _wsHandlers: WSMessageHandler[] = [];

  // ==================== SSE 连接 ====================

  /**
   * 建立 SSE 连接
   * 使用 api/sse.ts 的 createSSEConnection, 传入自定义消息处理
   */
  function connectSSE(): void {
    if (_sse) {
      disconnectSSE(_sse);
      _sse = null;
    }

    connectionState.value = 'connecting';

    _sse = createSSEConnection(undefined, handleSSEMessage, handleSSEStatus);

    // createSSEConnection 内部已处理重连, 但这里我们还需要控制
    // 因为用户主动断开时不应重连
    if (!_sse) {
      // 创建失败, 自行调度重连
      scheduleSSEReconnect();
    }
  }

  /**
   * 处理 SSE 消息 — 分发给所有注册的处理器
   */
  function handleSSEMessage(event: MessageEvent): void {
    for (const handler of _sseHandlers) {
      try {
        handler(event);
      } catch (e) {
        console.error('[useRealTime] SSE handler error:', e);
      }
    }
  }

  /**
   * 处理 SSE 连接状态变化
   */
  function handleSSEStatus(connected: boolean): void {
    sseConnected.value = connected;
    if (connected) {
      _sseReconnectAttempt = 0;
      if (wsConnected.value) {
        connectionState.value = 'connected';
      }
    } else {
      if (!_disconnectedByUser) {
        scheduleSSEReconnect();
      }
      connectionState.value = 'disconnected';
    }
  }

  /**
   * SSE 重连调度 (指数退避: 3s, 5s, 10s, 最多 3 次)
   */
  function scheduleSSEReconnect(): void {
    if (_disconnectedByUser) return;
    if (_sseReconnectAttempt >= 3) {
      console.log('[useRealTime] SSE 已达最大重连次数, 停止重连');
      return;
    }
    const idx = Math.min(_sseReconnectAttempt, SSE_RECONNECT_DELAYS.length - 1);
    const delayMs = SSE_RECONNECT_DELAYS[idx] * 1000;
    _sseReconnectAttempt++;
    console.log(
      '[useRealTime] SSE 将在 ' + delayMs + 'ms 后重连 (第' +
      _sseReconnectAttempt + '次)',
    );
    _sseReconnectTimer = setTimeout(() => {
      connectSSE();
    }, delayMs);
  }

  /**
   * 断开 SSE (不触发重连)
   */
  function destroySSE(): void {
    if (_sseReconnectTimer) {
      clearTimeout(_sseReconnectTimer);
      _sseReconnectTimer = null;
    }
    if (_sse) {
      disconnectSSE(_sse);
      _sse = null;
    }
    sseConnected.value = false;
    _sseReconnectAttempt = 0;
  }

  // ==================== WS 连接 ====================

  /**
   * 建立 WebSocket 连接
   * 使用 api/ws.ts 的 createWsConnection
   */
  function connectWS(): void {
    if (_ws) {
      destroyWSInternal();
    }

    connectionState.value = 'connecting';

    _ws = createWsConnection(undefined, {
      onMessage: handleWSMessage,
      onStatusChange: handleWSStatus,
      initialDelay: WS_INITIAL_DELAY * 1000,
      maxDelay: WS_MAX_DELAY_MS,
    });
  }

  /**
   * 处理 WS 消息 — 分发给所有注册的处理器
   */
  function handleWSMessage(data: unknown): void {
    for (const handler of _wsHandlers) {
      try {
        handler(data);
      } catch (e) {
        console.error('[useRealTime] WS handler error:', e);
      }
    }
  }

  /**
   * 处理 WS 连接状态变化
   */
  function handleWSStatus(connected: boolean): void {
    wsConnected.value = connected;
    if (connected) {
      if (sseConnected.value) {
        connectionState.value = 'connected';
      }
    } else {
      connectionState.value = 'disconnected';
    }
  }

  /**
   * 内部断开 WS (不触发外部重连逻辑,
   * createWsConnection 内部已有重连)
   *
   * 注意: createWsConnection 返回的 ws 对象在内部管理重连,
   * 所以我们不在这里调用 ws.onclose = null (内部已处理),
   * 而是直接使用 disconnectWs
   */
  function destroyWSInternal(): void {
    if (_ws) {
      disconnectWs(_ws);
      _ws = null;
    }
    wsConnected.value = false;
  }

  // ==================== 公共 API ====================

  /**
   * 建立连接 (SSE + WS)
   * 如果已连接会先断开重连
   */
  function connect(): void {
    _disconnectedByUser = false;
    connectSSE();
    connectWS();
  }

  /**
   * 断开所有连接 (停止重连)
   */
  function disconnect(): void {
    _disconnectedByUser = true;
    destroySSE();
    destroyWSInternal();
    connectionState.value = 'disconnected';
  }

  /**
   * 仅重连 SSE
   */
  function reconnectSSE(): void {
    _disconnectedByUser = false;
    destroySSE();
    connectSSE();
  }

  /**
   * 仅重连 WS
   */
  function reconnectWS(): void {
    _disconnectedByUser = false;
    destroyWSInternal();
    connectWS();
  }

  /**
   * 注册 SSE 消息监听
   */
  function onSSEMessage(handler: SSEMessageHandler): void {
    if (!_sseHandlers.includes(handler)) {
      _sseHandlers.push(handler);
    }
  }

  /**
   * 移除 SSE 消息监听
   */
  function offSSEMessage(handler: SSEMessageHandler): void {
    const idx = _sseHandlers.indexOf(handler);
    if (idx >= 0) {
      _sseHandlers.splice(idx, 1);
    }
  }

  /**
   * 注册 WS 消息监听
   */
  function onWSMessage(handler: WSMessageHandler): void {
    if (!_wsHandlers.includes(handler)) {
      _wsHandlers.push(handler);
    }
  }

  /**
   * 移除 WS 消息监听
   */
  function offWSMessage(handler: WSMessageHandler): void {
    const idx = _wsHandlers.indexOf(handler);
    if (idx >= 0) {
      _wsHandlers.splice(idx, 1);
    }
  }

  return {
    connectionState: readonly(connectionState),
    sseConnected: readonly(sseConnected),
    wsConnected: readonly(wsConnected),
    connect,
    disconnect,
    reconnectSSE,
    reconnectWS,
    onSSEMessage,
    offSSEMessage,
    onWSMessage,
    offWSMessage,
  };
}

// ==================== 单例 ====================

let _singleton: UseRealTimeReturn | null = null;

/**
 * 全局单例 useRealTime (跨组件共享同一个连接)
 *
 * 使用方式:
 *   // App.vue setup 中调用一次
 *   const rt = useRealTimeSingleton()
 *   rt.connect()
 *
 *   // 任意子组件
 *   const rt = useRealTimeSingleton()
 *   rt.onSSEMessage(handleSSEEvent)
 */
export function useRealTimeSingleton(): UseRealTimeReturn {
  if (!_singleton) {
    _singleton = useRealTime();
  }
  return _singleton;
}
