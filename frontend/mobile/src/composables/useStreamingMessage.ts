/**
 * 流式消息 Composable — SSE 流式渲染状态管理（集中式 Store 模式）
 *
 * 设计模式：messages.value 作为中央 Store，SSE 事件直接在 messages.value 中
 * 找到 isStreaming=true 的消息并修改其 parts，不需要占位符注册/注销。
 * Vue 的响应式系统自动处理 UI 渲染。
 *
 * 使用方式:
 *   const sm = useStreamingMessage()
 *   sm.configure({ messages, activeSessionId }) // 注入 messages ref
 *   sm.connectToSSE()  // App 初始化时调用一次
 *   sm.handleSSEEvent(data)  // SSE onmessage 中调用
 *   await sm.createPendingPromise()  // 等待流结束
 */

import { ref, computed, readonly, type InjectionKey, type Ref, type ComputedRef } from 'vue'
import { useRealTimeSingleton } from '@/composables/useRealTime'
import type { SSEProperties, SSEPayload, SSEMessagePart, ChatMessage, MessagePart, TokenUsage } from '@/types'

// ==================== 类型定义 ====================

/** 会话状态 */
type SessionStatus = 'busy' | 'idle' | 'error'

/** 带 partId 的消息 Part (用于 SSE partId 查找，不修改原类型) */
interface PartWithId extends MessagePart {
  _partId?: string
}

/** 调试用：SSE 事件计数器 */
let _sseLogCount = 0

/** useStreamingMessage 返回值 */
export interface UseStreamingMessageReturn {
  /** 是否正在流式渲染 */
  isStreaming: ComputedRef<boolean>
  /** 当前会话 Token 用量统计 (SSE 实时更新) */
  currentTokens: Readonly<Ref<TokenUsage | null>>
  /** 会话状态映射 (sessionId -> busy/idle/error) */
  sessionStatus: Readonly<Ref<Record<string, SessionStatus>>>
  /** 是否因空闲超时自动结束流式 */
  isIdleTimedOut: Readonly<Ref<boolean>>
  /** 处理 SSE 事件 (在 SSE onmessage 中调用) */
  handleSSEEvent: (data: unknown) => void
  /** 完成流式渲染 (解析 pending promise, 标记消息完成) */
  finalizeStreaming: () => void
  /** 创建待回复 Promise (发送消息后等待 SSE) */
  createPendingPromise: () => Promise<void>
  /** 是否有待回复的 Promise */
  hasPendingReply: ComputedRef<boolean>
  /** 注入 messages ref 和 activeSessionId ref (由 useChat 初始化时调用) */
  configure: (options: { messages: Ref<ChatMessage[]>; activeSessionId: Ref<string> }) => void
  /** 更新当前会话 Token 用量 (供 useChat 从消息历史提取 tokens 时调用) */
  updateTokens: (tokens: TokenUsage | null) => void
  /** 将当前 streaming 注册到 useRealTime (幂等) */
  connectToSSE: () => void
  /** 断开 SSE 连接注册 */
  disconnectFromSSE: () => void
  /** 设置活跃会话 ID (用于 SSE 事件过滤) */
  setActiveSessionId: (sessionId: string | null) => void
}

/** useStreamingMessage 注入 key */
export const USE_STREAMING_MESSAGE_KEY: InjectionKey<UseStreamingMessageReturn> =
  Symbol('useStreamingMessage')

// ==================== 内部状态 ====================

/** assistant 回复的 pending promise resolve 回调 */
let _resolveAssistantReply: (() => void) | null = null

/** 流式空闲超时定时器 (30s 无 delta 自动结束) */
let _streamingIdleTimer: ReturnType<typeof setTimeout> | null = null

/** SSE 连接路由注册标志 (确保只注册一次) */
let _sseWired = false

/** 当前活跃会话 ID */
let _activeSessionId: string | null = null

/** 外部注入的 messages ref (指向 useChat 的 messages) */
let _messagesRef: Ref<ChatMessage[]> | null = null

/** 外部注入的 activeSessionId ref (指向 useChat 的 currentSessionId) */
let _activeSessionIdRef: Ref<string> | null = null

/** 标记 configure 已调用 (用于 isStreaming computed 依赖追踪) */
const _streamingConfigured = ref(false)

// ==================== 工具函数 ====================

/**
 * 在 parts 数组中按 _partId 查找索引 (线性查找，parts 通常 < 20 个)
 */
function _findPartIndex(parts: MessagePart[], partId: string): number {
  for (let i = 0; i < parts.length; i++) {
    if ((parts[i] as PartWithId)._partId === partId) return i
  }
  return -1
}

// ==================== Composable ====================

/**
 * 流式消息 Composable — SSE 流式渲染状态管理（集中式 Store 模式）
 */
export function useStreamingMessage(): UseStreamingMessageReturn {
  // ==================== 状态 ====================

  /** 会话状态映射 (sessionId -> busy/idle/error) */
  const sessionStatus = ref<Record<string, SessionStatus>>({})

  /** 是否因空闲超时自动结束流式 */
  const isIdleTimedOut = ref(false)

  /** 当前会话 Token 用量 (SSE 实时更新) */
  const _currentTokens = ref<TokenUsage | null>(null)

  /** 是否有活跃的流式输出 (在 messages.value 中查找 isStreaming=true) */
  const isStreaming = computed<boolean>(() => {
    // 依赖 configure 调用标记，确保配置后重新计算
    void _streamingConfigured.value
    return _messagesRef?.value?.some(m => m.isStreaming === true) ?? false
  })

  /** 是否有待回复的 Promise */
  const hasPendingReply = computed<boolean>(() => {
    return _resolveAssistantReply !== null
  })

  // ==================== 注入 (集中式 Store 配置) ====================

  /**
   * 注入 messages ref 和 activeSessionId ref
   * 必须在 SSE 事件处理之前调用 (由 useChat 初始化时调用)
   */
  function configure(options: {
    messages: Ref<ChatMessage[]>
    activeSessionId: Ref<string>
  }): void {
    _messagesRef = options.messages
    _activeSessionIdRef = options.activeSessionId
    _streamingConfigured.value = true
  }

  // ==================== SSE 事件处理 ====================

  /**
   * 处理 SSE 事件 (入口)
   *
   * 事件格式兼容:
   *   - 原生: { type: 'xxx', payload: { type: 'xxx', properties: {...} } }
   *   - Proxy: { payload: { type: 'xxx', properties: {...} } }
   */
  function handleSSEEvent(data: unknown): void {
    if (!data || typeof data !== 'object') return

    const d = data as Record<string, unknown>

    // 提取事件类型
    const payload = d.payload as SSEPayload | undefined
    const eventType: string =
      (payload?.type as string) ||
      (d.type as string) ||
      ''

    if (!eventType) return

    // 忽略连接状态事件
    if (
      eventType === 'proxy.connected' ||
      eventType === 'server.connected'
    ) {
      if (eventType === 'proxy.connected') {
        console.warn('[SSE-DEBUG] SSE 连接已建立')
      }
      return
    }

    // 必须含有 payload 才继续
    if (!payload) return
    const props = payload.properties

    if (!props) return

    // 提取事件所属会话 ID
    const eventSessionId = (props.sessionID || props.session_id) as string | undefined
    const isActiveSession = !_activeSessionId || (eventSessionId || '_default') === _activeSessionId

    // DEBUG: 前20个事件打印类型
    _sseLogCount++
    const dbgCnt = _sseLogCount
    if (dbgCnt <= 20 || eventType === 'message.part.updated' || eventType === 'message.updated' || eventType === 'session.idle' || eventType === 'session.status') {
      console.warn('[SSE-DBG] #' + dbgCnt, eventType, 'sid:', eventSessionId || '-', 'isAct:', isActiveSession, 'aId:', _activeSessionId || '-')
    }

    // 首次收到事件时自动设定活跃会话
    if (!_activeSessionId && eventSessionId) {
      _activeSessionId = eventSessionId
    }

    // ============ message.part.updated ============
    if (eventType === 'message.part.updated') {
      console.warn('[SSE-DEBUG] part.updated 到达! eventSessionId:', eventSessionId)
      handlePartUpdated(props, eventSessionId)
      return
    }

    // ============ message.part.delta ============
    if (eventType === 'message.part.delta') {
      handlePartDelta(props, eventSessionId)
      return
    }

    // ============ message.updated ============
    if (eventType === 'message.updated') {
      if (isActiveSession) {
        handleMessageUpdated(props)
      }
      return
    }

    // ============ session.status ============
    if (eventType === 'session.status') {
      const sid = (props.sessionID || '') as string
      const status = (props.status || 'idle') as string
      if (sid) {
        sessionStatus.value = { ...sessionStatus.value, [sid]: status as SessionStatus }
      }
      return
    }

    // ============ session.idle ============
    if (eventType === 'session.idle') {
      const sid = (props.sessionID || props.session_id || '') as string
      if (sid) {
        sessionStatus.value = { ...sessionStatus.value, [sid]: 'idle' }
        if (isActiveSession && isStreaming.value) {
          finalizeStreaming()
        }
      }
      return
    }

    // ============ session.updated ============
    if (eventType === 'session.updated') {
      const sid = (props.sessionID || '') as string
      const status = (props.status || '') as string
      if (sid && status) {
        sessionStatus.value = { ...sessionStatus.value, [sid]: status as SessionStatus }
      }
      return
    }

    // ============ session.diff ============
    if (eventType === 'session.diff') {
      return
    }
  }

  /**
   * 处理 message.part.updated 事件 — 在 messages.value 中找到流式消息并写入 parts
   */
  function handlePartUpdated(props: SSEProperties, eventSessionId: string | undefined): void {
    const msgs = _messagesRef?.value
    if (!msgs) {
      console.warn('[SSE-DEBUG] handlePartUpdated: _messagesRef 未配置')
      return
    }

    // 检查会话匹配
    if (eventSessionId && _activeSessionIdRef?.value && eventSessionId !== _activeSessionIdRef.value) {
      console.warn('[SSE-DEBUG] handlePartUpdated: sessionId 不匹配! event:', eventSessionId, 'active:', _activeSessionIdRef.value)
      return
    }

    // 在 messages.value 中查找流式消息
    const streamingMsg = msgs.find(m => m.isStreaming === true && m.role === 'assistant')
    if (!streamingMsg) {
      console.warn('[SSE-DEBUG] handlePartUpdated: 未找到流式消息 (isStreaming=true)')
      return
    }

    const part = props.part as SSEMessagePart | undefined
    if (!part) return

    const partId = part.id
    if (!partId) return

    const partType = (part.type || '') as string

    // 忽略 step 事件
    if (partType === 'step-start' || partType === 'step-finish') return

    // 确保 parts 数组存在
    if (!streamingMsg.parts) {
      streamingMsg.parts = []
    }

    const idx = _findPartIndex(streamingMsg.parts, partId)
    let msgPart: PartWithId

    // reasoning / thought
    if (partType === 'reasoning' || partType === 'thought') {
      msgPart = {
        type: partType as MessagePart['type'],
        text: part.text || '',
      }
    } else if (partType === 'text') {
      // text
      msgPart = {
        type: 'text',
        text: part.text || '',
      }
    } else if (partType === 'tool' || partType === 'tool_call') {
      // tool / tool_call
      const existing = idx >= 0 ? (streamingMsg.parts[idx] as PartWithId) : null
      const toolName = (part.tool || (existing?.tool || 'tool')) as string
      const toolState = part.state || {}
      const toolStatus = (toolState.status || (existing?.state?.status || 'running')) as string
      const newInput = toolState.input as Record<string, unknown> | undefined
      const toolInput = (newInput && Object.keys(newInput).length > 0
        ? newInput
        : (existing?.state?.input as Record<string, unknown> || {}))
      const toolOutput = (toolState.output || (existing?.state?.output as string || '')) as string

      msgPart = {
        type: 'tool',
        text: (existing?.text as string) || '',
        tool: toolName,
        state: { status: toolStatus, input: toolInput, output: toolOutput },
      }
    } else if (partType === 'tool_result') {
      // tool_result: 合并到已有 tool part
      const existing = idx >= 0 ? streamingMsg.parts[idx] : null
      if (existing && (existing.type === 'tool' || existing.type === 'tool_result')) {
        existing.text = part.text || ''
        console.warn('[SSE-DBG] part 写入成功! partId:', partId, 'parts数量:', streamingMsg.parts.length)
      }
      msgPart = {
        type: 'tool_result',
        text: part.text || '',
      }
    } else {
      return // 未知类型，忽略
    }

    // 写入 partId 用于后续 delta 查找
    msgPart._partId = partId

    // 写入或替换
    if (idx >= 0) {
      streamingMsg.parts.splice(idx, 1, msgPart)
    } else {
      streamingMsg.parts.push(msgPart)
    }
  }

  /**
   * 处理 message.part.delta 事件 — 在 messages.value 中找到流式消息并追加文本
   */
  function handlePartDelta(props: SSEProperties, eventSessionId: string | undefined): void {
    const msgs = _messagesRef?.value
    if (!msgs) return

    if (eventSessionId && _activeSessionIdRef?.value && eventSessionId !== _activeSessionIdRef.value) return

    const streamingMsg = msgs.find(m => m.isStreaming === true && m.role === 'assistant')
    if (!streamingMsg) return

    const p = props as unknown as Record<string, unknown>
    const partId = p.partID as string | undefined
    const field = p.field as string | undefined
    const delta = (p.delta as string) || ''

    if (!partId || field !== 'text' || !delta) return

    // 确保 parts 数组存在
    if (!streamingMsg.parts) {
      streamingMsg.parts = []
    }

    let idx = _findPartIndex(streamingMsg.parts, partId)

    // delta 可能先于 part.updated 到达，自动创建 part
    if (idx < 0) {
      const newPart: PartWithId = { type: 'text', text: '' }
      newPart._partId = partId
      streamingMsg.parts.push(newPart)
      idx = streamingMsg.parts.length - 1
    }

    const msgPart = streamingMsg.parts[idx]
    msgPart.text = (msgPart.text || '') + delta

    // 如果是 tool 类型，同时累积 toolOutput
    if (msgPart.type === 'tool' && msgPart.state) {
      msgPart.state.output = ((msgPart.state.output as string) || '') + delta
    }
  }

  /**
   * 处理 message.updated 事件
   *
   * 注意：不在此处触发 finalizeStreaming！初始加载时后端会重放所有历史消息的
   * message.updated 事件，过早调用 finalizeStreaming 会将新创建的流式占位符
   * (isStreaming=true) 标记为完成。流式完成统一由 session.idle 事件触发。
   *
   * Token 更新：从 info.tokens 提取 AI 模型用量统计并实时更新。
   */
  function handleMessageUpdated(props: SSEProperties): void {
    // 仅用于接收事件，不触发任何副作用
    // 流式完成由 session.idle 事件统一处理

    // 解析 token 用量信息 (路径1: SSE 实时推送)
    const info = props.info as Record<string, unknown> | undefined
    if (info?.tokens) {
      const t = info.tokens as Record<string, unknown>
      // 只更新有实际值的 tokens (排除全0的情况)
      const hasTokens = (Number(t.total) || 0) > 0 || (Number(t.input) || 0) > 0 || (Number(t.output) || 0) > 0
      if (hasTokens) {
        _currentTokens.value = {
          total: Number(t.total) || 0,
          input: Number(t.input) || 0,
          output: Number(t.output) || 0,
          reasoning: t.reasoning !== undefined ? Number(t.reasoning) : undefined,
          cache: t.cache as TokenUsage['cache'] | undefined,
        }
      }
    }
  }

  // ==================== 流式状态管理 ====================

  /**
   * 创建待回复 Promise
   *
   * 发送消息后调用此函数创建一个 Promise，
   * 当 finalizeStreaming() 被调用时（SSE message.updated 或 session.idle）该 Promise resolve。
   * 120 秒超时自动 resolve。
   */
  function createPendingPromise(): Promise<void> {
    return new Promise<void>((resolve) => {
      _resolveAssistantReply = null
      _resolveAssistantReply = resolve

      // 120 秒超时
      setTimeout(() => {
        _clearIdleTimer()
        if (_resolveAssistantReply) {
          const r = _resolveAssistantReply
          _resolveAssistantReply = null
          r()
        }
      }, 120000)
    })
  }

  /**
   * 完成流式渲染
   *
   * 在收到 assistant 角色的 message.updated 时调用。
   * 标记流式消息完成，解析 pending promise。
   */
  function finalizeStreaming(): void {
    // 在 messages.value 中找到流式消息并标记完成
    const msgs = _messagesRef?.value
    if (msgs) {
      const streamingMsg = msgs.find(m => m.isStreaming === true)
      if (streamingMsg) {
        streamingMsg.isStreaming = false
      }
    }

    // 清除空闲超时定时器
    _clearIdleTimer()

    // 解决 pending promise
    if (_resolveAssistantReply) {
      const r = _resolveAssistantReply
      _resolveAssistantReply = null
      r()
    }
  }

  // ==================== 空闲超时管理 ====================

  /**
   * 清除空闲超时定时器 (流式正常结束时调用)
   */
  function _clearIdleTimer(): void {
    if (_streamingIdleTimer !== null) {
      clearTimeout(_streamingIdleTimer)
      _streamingIdleTimer = null
    }
  }

  // ==================== SSE 连接注册 (路由简化) ====================

  /**
   * 将当前 streaming 注册到 useRealTime SSE 消息路由
   * 幂等，只会注册一次。
   */
  function connectToSSE(): void {
    if (_sseWired) return
    _sseWired = true

    const rt = useRealTimeSingleton()
    rt.onSSEMessage((event: MessageEvent) => {
      try {
        const raw = event.data
        if (!raw || typeof raw !== 'string') return
        const data = JSON.parse(raw)
        handleSSEEvent(data)
      } catch (e) {
        console.error('[useStreamingMessage] SSE 事件解析失败:', e)
      }
    })
  }

  function disconnectFromSSE(): void {
    // 生命周期由 useRealTime 管理，无需额外操作
  }

  /** 设置活跃会话 ID (用于 SSE 事件过滤，同步更新外部 ref) */
  function setActiveSessionId(sessionId: string | null): void {
    _activeSessionId = sessionId
    if (_activeSessionIdRef) {
      _activeSessionIdRef.value = sessionId || ''
    }
  }

  /** 更新当前会话 Token 用量 (供 useChat 从消息历史提取 tokens 时调用) */
  function updateTokens(tokens: TokenUsage | null): void {
    _currentTokens.value = tokens
  }

  return {
    isStreaming,
    currentTokens: readonly(_currentTokens),
    sessionStatus: readonly(sessionStatus),
    isIdleTimedOut: readonly(isIdleTimedOut),
    handleSSEEvent,
    finalizeStreaming,
    createPendingPromise,
    hasPendingReply,
    configure,
    connectToSSE,
    disconnectFromSSE,
    setActiveSessionId,
    updateTokens,
  }
}

// ==================== 单例 ====================

let _singleton: UseStreamingMessageReturn | null = null

/**
 * 全局单例 useStreamingMessage (跨组件共享同一个流式状态)
 */
export function useStreamingMessageSingleton(): UseStreamingMessageReturn {
  if (!_singleton) {
    _singleton = useStreamingMessage()
  }
  return _singleton
}
