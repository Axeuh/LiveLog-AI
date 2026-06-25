/**
 * 流式消息 Composable — SSE 流式渲染状态管理
 *
 * 管理 AI 回复的流式渲染状态: stream parts 合并、折叠状态、tool call 状态。
 * 对应 index.original.html 中的 _streamParts, _streamCollapsed, handleSSEEvent 等。
 *
 * 使用方式:
 *   const { streamParts, streamCollapsed, isStreaming, handleSSEEvent, finalizeStreaming } =
 *     useStreamingMessage()
 *
 *   // 在 SSE onmessage 中:
 *   handleSSEEvent(data)
 *
 *   // 检查是否有活跃流:
 *   if (isStreaming.value) { ... }
 *
 *   // 渲染完成后清理:
 *   finalizeStreaming()
 */

import { ref, reactive, computed, readonly, type InjectionKey, type Ref, type ComputedRef } from 'vue';
import type { StreamPart, StreamPartsMap, StreamCollapsedMap, SSEProperties, SSEPayload, SSEMessagePart, ChatMessage, MessagePart } from '@/types';

// ==================== 类型定义 ====================

/** useStreamingMessage 返回值 */
export interface UseStreamingMessageReturn {
  /** 流式 Part 映射 (partId -> StreamPart) */
  streamParts: StreamPartsMap;
  /** 流式折叠状态映射 (partId -> boolean, true=折叠) */
  streamCollapsed: StreamCollapsedMap;
  /** 当前流式消息 ID */
  streamMessageId: Readonly<Ref<string | null>>;
  /** 是否正在流式渲染 */
  isStreaming: ComputedRef<boolean>;
  /**
   * 处理 SSE 事件 (在 SSE onmessage 中调用)
   * @param data 解析后的 SSE 事件数据
   */
  handleSSEEvent: (data: unknown) => void;
  /**
   * 完成流式渲染 (重置状态, 解决 pending promise)
   */
  finalizeStreaming: () => void;
  /**
   * 清理所有流式状态 (不触发 resolve)
   */
  clearStreaming: () => void;
  /**
   * 创建待回复 Promise (发送消息后等待 SSE)
   * @returns Promise, 在 finalizeStreaming 时 resolve
   */
  createPendingPromise: () => Promise<void>;
  /** 是否有待回复的 Promise */
  hasPendingReply: ComputedRef<boolean>;
  /**
   * 将当前 streamParts 构建为 ChatMessage 对象
   * 用于流完成时将流式内容追加到消息列表
   */
  buildStreamMessage: () => ChatMessage;
}

/** useStreamingMessage 注入 key */
export const USE_STREAMING_MESSAGE_KEY: InjectionKey<UseStreamingMessageReturn> =
  Symbol('useStreamingMessage');

// ==================== 内部状态 ====================

/** assistant 回复的 pending promise resolve 回调 */
let _resolveAssistantReply: (() => void) | null = null;

// ==================== Composable ====================

/**
 * 流式消息 Composable — SSE 流式渲染状态管理
 *
 * 处理来自 SSE 的 message.part.updated, message.part.delta, message.updated 事件,
 * 管理 _streamParts 和 _streamCollapsed 状态。
 */
export function useStreamingMessage(): UseStreamingMessageReturn {
  /** partId -> StreamPart 映射 */
  const streamParts = reactive<StreamPartsMap>({});
  /** partId -> boolean (true=折叠) */
  const streamCollapsed = reactive<StreamCollapsedMap>({});
  /** 当前流式消息 ID */
  const streamMessageId = ref<string | null>(null);

  /** 是否有活跃的流式输出 */
  const isStreaming = computed<boolean>(() => {
    return Object.keys(streamParts).length > 0;
  });

  /** 是否有待回复的 Promise */
  const hasPendingReply = computed<boolean>(() => {
    return _resolveAssistantReply !== null;
  });

  // ==================== SSE 事件处理 ====================

  /**
   * 处理 SSE 事件 (入口)
   *
   * 事件格式兼容:
   *   - 原生: { type: 'xxx', payload: { type: 'xxx', properties: {...} } }
   *   - Proxy: { payload: { type: 'xxx', properties: {...} } }
   *
   * @param data 解析后的 SSE 事件数据
   */
  function handleSSEEvent(data: unknown): void {
    if (!data || typeof data !== 'object') return;

    const d = data as Record<string, unknown>;

    // 提取事件类型
    const payload = d.payload as SSEPayload | undefined;
    const eventType: string =
      (payload?.type as string) ||
      (d.type as string) ||
      '';

    if (!eventType) return;

    // 忽略连接状态事件
    if (
      eventType === 'proxy.connected' ||
      eventType === 'server.connected'
    ) {
      return;
    }

    // 必须含有 payload 才继续
    if (!payload) return;
    const props = payload.properties;

    if (!props) return;

    // ============ message.part.updated ============
    if (eventType === 'message.part.updated') {
      handlePartUpdated(props);
      return;
    }

    // ============ message.part.delta ============
    if (eventType === 'message.part.delta') {
      handlePartDelta(props);
      return;
    }

    // ============ message.updated ============
    if (eventType === 'message.updated') {
      handleMessageUpdated(props);
      return;
    }
  }

  /**
   * 处理 message.part.updated 事件
   * part 初始化/类型更新
   */
  function handlePartUpdated(props: SSEProperties): void {
    const part = props.part as SSEMessagePart | undefined;
    if (!part) return;

    const partId = part.id;
    if (!partId) return;

    const partType = (part.type || '') as string;

    // 忽略 step 事件
    if (partType === 'step-start' || partType === 'step-finish') return;

    // 记录 message ID
    const msgId = (part.messageID || props.messageID || '') as string;
    if (msgId) {
      streamMessageId.value = msgId;
    }

    // reasoning / thought
    if (partType === 'reasoning' || partType === 'thought') {
      streamParts[partId] = {
        type: partType as StreamPart['type'],
        text: part.text || '',
      };
      return;
    }

    // text
    if (partType === 'text') {
      streamParts[partId] = {
        type: 'text',
        text: part.text || '',
      };
      return;
    }

    // tool / tool_call (合并更新)
    if (partType === 'tool' || partType === 'tool_call') {
      const existing = streamParts[partId];
      const toolName = (part.tool || (existing ? existing.toolName : 'tool')) as string;
      const toolState = part.state || {};
      const toolStatus = (toolState.status || (existing ? existing.toolStatus : 'running')) as string;
      const toolInput = (toolState.input || (existing ? existing.toolInput : {})) as Record<string, unknown>;
      const toolOutput = (toolState.output || (existing ? existing.toolOutput : '')) as string;

      streamParts[partId] = {
        type: 'tool',
        text: existing ? existing.text : '',
        toolName,
        toolStatus,
        toolInput,
        toolOutput,
      };
      return;
    }

    // tool_result (合并到已有的 tool part, 或创建新 part)
    if (partType === 'tool_result') {
      const resText = part.text || '';
      const existing = streamParts[partId];
      if (existing && (existing.type === 'tool' || existing.type === 'tool_result')) {
        existing.type = 'tool_result';
        existing.text = resText;
      } else {
        streamParts[partId] = {
          type: 'tool_result',
          text: resText,
        };
      }
      return;
    }
  }

  /**
   * 处理 message.part.delta 事件
   * 增量文本追加
   *
   * 注意: SSEProperties 类型不包含 partID/field/delta 字段,
   * 使用 unknown 类型转换以支持实际 SSE 数据结构。
   */
  function handlePartDelta(props: SSEProperties): void {
    const p = props as unknown as Record<string, unknown>;
    const partId = p.partID as string | undefined;
    const field = p.field as string | undefined;
    const delta = (p.delta as string) || '';

    if (!partId || field !== 'text' || !delta) return;

    const part = streamParts[partId];
    if (!part) return; // 来自未知 part, 忽略

    part.text += delta;

    // 如果是 tool 类型, 同时累积 toolOutput
    if (part.type === 'tool') {
      part.toolOutput = (part.toolOutput || '') + delta;
    }
  }

  /**
   * 处理 message.updated 事件
   * 消息完成时触发 finalize
   *
   * 注意: SSEProperties 类型不包含 info 字段,
   * 使用 unknown 类型转换以支持实际 SSE 数据结构。
   */
  function handleMessageUpdated(props: SSEProperties): void {
    const p = props as unknown as Record<string, unknown>;
    const info = p.info as Record<string, unknown> | undefined;
    if (info && info.role === 'assistant') {
      finalizeStreaming();
    }
  }

  // ==================== 流式状态管理 ====================

  /**
   * 创建待回复 Promise
   *
   * 发送消息后调用此函数创建一个 Promise,
   * 当 finalizeStreaming() 被调用时 (SSE message.updated) 该 Promise resolve。
   * 120 秒超时自动 resolve。
   */
  function createPendingPromise(): Promise<void> {
    return new Promise<void>((resolve) => {
      // 清理旧的 resolve
      _resolveAssistantReply = null;
      _resolveAssistantReply = resolve;

      // 120 秒超时
      setTimeout(() => {
        if (_resolveAssistantReply) {
          const r = _resolveAssistantReply;
          _resolveAssistantReply = null;
          r();
        }
      }, 120000);
    });
  }

  /**
   * 完成流式渲染
   *
   * 在收到 assistant 角色的 message.updated 时调用。
   * 会 resolve pending promise, 让发送方继续执行。
   */
  function finalizeStreaming(): void {
    // 解决 pending promise
    if (_resolveAssistantReply) {
      const r = _resolveAssistantReply;
      _resolveAssistantReply = null;
      r();
    }

    // 注意: 不清除 streamParts, 让外部组件在需要时调用 clearStreaming
    // 这样渲染层可以显示最终内容
  }

  /**
   * 清理所有流式状态 (切换会话、新会话时调用)
   */
  function clearStreaming(): void {
    // 清除所有 part
    const partKeys = Object.keys(streamParts);
    for (const key of partKeys) {
      delete streamParts[key];
    }

    // 清除所有折叠状态
    const collKeys = Object.keys(streamCollapsed);
    for (const key of collKeys) {
      delete streamCollapsed[key];
    }

    streamMessageId.value = null;

    // 清理 pending resolve (如果有)
    if (_resolveAssistantReply) {
      _resolveAssistantReply = null;
    }
  }

  // ==================== 构建消息对象 ====================

  /**
   * 将当前 streamParts 构建为 ChatMessage 对象
   *
   * 将 streamParts 中的每个 StreamPart 转为 MessagePart,
   * 用于流完成时把流式内容追加到消息列表, 避免 reload 历史带来的闪烁。
   */
  function buildStreamMessage(): ChatMessage {
    const parts: MessagePart[] = Object.values(streamParts).map((sp) => ({
      type: sp.type,
      text: sp.text,
      tool: sp.type === 'tool' ? sp.toolName : undefined,
      state: sp.toolStatus
        ? {
            status: sp.toolStatus,
            input: sp.toolInput,
            output: sp.toolOutput,
          }
        : undefined,
    }))

    return {
      parts,
      role: 'assistant',
      timestamp: new Date().toISOString(),
    }
  }

  return {
    streamParts,
    streamCollapsed,
    streamMessageId: readonly(streamMessageId),
    isStreaming,
    handleSSEEvent,
    finalizeStreaming,
    clearStreaming,
    createPendingPromise,
    hasPendingReply,
    buildStreamMessage,
  };
}

// ==================== 单例 ====================

let _singleton: UseStreamingMessageReturn | null = null;

/**
 * 全局单例 useStreamingMessage (跨组件共享同一个流式状态)
 *
 * 使用方式:
 *   const sm = useStreamingMessageSingleton()
 *   sm.handleSSEEvent(data)
 *   sm.clearStreaming()
 */
export function useStreamingMessageSingleton(): UseStreamingMessageReturn {
  if (!_singleton) {
    _singleton = useStreamingMessage();
  }
  return _singleton;
}
