/**
 * 子智能体 Composable -- 管理子智能体列表获取和子会话切换
 *
 * 三层数据源:
 *   1. API: GET /api/screen/session/{sessionId}/children
 *   2. 消息扫描: 从 tool=task 的 parts 中提取 session_id
 *   3. Mock: USE_MOCK_DATA 时使用预设的子智能体
 *
 * 使用方式:
 *   const sa = useSubAgentsSingleton()
 *   // 加载子智能体
 *   await sa.loadSubAgents(currentSessionId, messages)
 *   // 进入子会话
 *   await sa.enterSubAgent(childSessionId)
 *   // 返回父会话
 *   await sa.returnToParent()
 */

import { ref, computed, type Ref, type ComputedRef } from 'vue'
import { useChatSingleton } from '@/composables/useChat'
import { useStreamingMessageSingleton } from '@/composables/useStreamingMessage'
import { apiGet } from '@/api/client'
import { USE_MOCK_DATA } from '@/composables/useMockData'
import type { ChatMessage } from '@/types'

// ==================== 类型 ====================

/** 子智能体信息 */
export interface SubAgentInfo {
  /** 唯一标识 */
  id: string
  /** 智能体名称 */
  name: string
  /** 智能体类型 (explore/build/oracle 等) */
  type: string
  /** 子会话 ID */
  childSessionId: string | null
  /** 状态 */
  status: string
  /** 在消息列表中的位置 (用于排序) */
  messageIndex: number
}

/** 父级层级节点 */
export interface ParentLevel {
  /** 会话 ID */
  sessionId: string
  /** 会话标题 */
  title: string
}

/** useSubAgents 返回值 */
export interface UseSubAgentsReturn {
  /** 子智能体列表 */
  subAgents: Ref<SubAgentInfo[]>
  /** 是否处于子会话模式 (任意层级) */
  isChildMode: ComputedRef<boolean>
  /** 父级层级栈 (索引0=根父级, 索引last=直接父级) */
  parentChain: Ref<ParentLevel[]>
  /** 当前层级的直接父会话标题 (用于返回按钮文本) */
  parentSessionTitle: ComputedRef<string>
  /** 子智能体列表弹窗可见性 (HeaderBar 和 ChatView 共享) */
  showList: Ref<boolean>
  /** 正在加载子智能体列表 */
  loading: Ref<boolean>
  /**
   * 加载子智能体列表 (每次调用都重新请求)
   * 真实模式: API + 消息扫描双重获取后合并
   * Mock 模式: 直接返回预设数据
   * @param sessionId 会话 ID
   * @param messages 当前会话的消息列表 (用于消息扫描)
   */
  loadSubAgents: (sessionId: string, messages: ChatMessage[]) => Promise<void>
  /**
   * 从消息列表中扫描 task 工具调用
   * @param messages 消息列表
   * @returns 扫描到的子智能体列表
   */
  scanFromMessages: (messages: ChatMessage[]) => SubAgentInfo[]
  /**
   * 进入子智能体会话
   * @param childSessionId 子会话 ID
   */
  enterSubAgent: (childSessionId: string) => Promise<void>
  /**
   * 返回父会话
   */
  returnToParent: () => Promise<void>
}

// ==================== 单例 ====================

let _singleton: UseSubAgentsReturn | null = null

export function useSubAgentsSingleton(): UseSubAgentsReturn {
  if (_singleton) return _singleton
  _singleton = useSubAgents()
  return _singleton
}

// ==================== Composable ====================

export function useSubAgents(): UseSubAgentsReturn {
  const chat = useChatSingleton()
  const subAgents = ref<SubAgentInfo[]>([])
  const parentChain = ref<ParentLevel[]>([])
  const showList = ref(false)
  const loading = ref(false)

  const isChildMode = computed(() => parentChain.value.length > 0)

  /** 当前层级的直接父会话标题 (栈顶) */
  const parentSessionTitle = computed(() => {
    if (parentChain.value.length === 0) return '主会话'
    return parentChain.value[parentChain.value.length - 1].title
  })

  // ==================== Mock 数据 ====================

  function getMockSubAgents(): SubAgentInfo[] {
    return [
      {
        id: 'mock_agent_1',
        name: '审查当前前端代码结构',
        type: 'explore',
        childSessionId: 'mock_child_ses_1',
        status: 'completed',
        messageIndex: 2,
      },
      {
        id: 'mock_agent_2',
        name: '查找认证实现方案',
        type: 'librarian',
        childSessionId: 'mock_child_ses_2',
        status: 'completed',
        messageIndex: 3,
      },
      {
        id: 'mock_agent_3',
        name: '重构用户认证中间件',
        type: 'build',
        childSessionId: 'mock_child_ses_3',
        status: 'completed',
        messageIndex: 5,
      },
    ]
  }

  // ==================== API 获取 ====================

  async function fetchFromApi(sessionId: string): Promise<SubAgentInfo[]> {
    try {
      const payload = await apiGet<{ children?: Array<Record<string, unknown>> }>(
        '/api/screen/session/' + encodeURIComponent(sessionId) + '/children'
      )
      if (payload && Array.isArray(payload.children)) {
        return payload.children.map((c, idx) => ({
          id: String(c.id || 'api_child_' + idx),
          name: String(c.title || c.name || '子智能体'),
          type: String(c.type || c.agent || 'unknown'),
          childSessionId: String(c.id || ''),
          status: String(c.status || 'completed'),
          messageIndex: 1000 + idx, // API 回来的排在后面
        }))
      }
    } catch (e) {
      console.warn('[useSubAgents] API 获取子智能体失败:', e)
    }
    return []
  }

  // ==================== 消息扫描 ====================

  function scanFromMessages(messages: ChatMessage[]): SubAgentInfo[] {
    const result: SubAgentInfo[] = []

    messages.forEach((msg, msgIdx) => {
      const parts = msg.parts || []
      parts.forEach((part) => {
        if (part.type !== 'tool' || part.tool !== 'task') return

        const state = part.state
        if (!state) return

        const raw = part as unknown as Record<string, unknown>
        const callId = (raw.callID as string) || (raw.id as string) || 'agent_' + msgIdx
        const input = (state.input || {}) as Record<string, unknown>
        const name = (input.description as string) || (input.agent as string) || '子智能体'
        const type = (input.subagent_type as string) || (input.agent as string) || 'unknown'

        // 从 output 中提取 session_id
        let childSessionId: string | null = null
        const output = state.output
        if (output && typeof output === 'string') {
          const match = output.match(/<task_metadata>[\s\S]*?session_id:\s*([a-zA-Z0-9_]+)[\s\S]*?<\/task_metadata>/)
          if (match) childSessionId = match[1]
        }

        result.push({
          id: callId,
          name,
          type,
          childSessionId,
          status: state.status || 'unknown',
          messageIndex: msgIdx,
        })
      })
    })

    return result
  }

  // ==================== 去重合并 ====================

  /** 合并两个列表，按 childSessionId 去重 */
  function mergeLists(api: SubAgentInfo[], scanned: SubAgentInfo[]): SubAgentInfo[] {
    const seen = new Set<string>()
    const result: SubAgentInfo[] = []

    // API 优先（更可靠），消息扫描补充
    for (const agent of [...api, ...scanned]) {
      const key = agent.childSessionId || agent.id
      if (!seen.has(key)) {
        seen.add(key)
        result.push(agent)
      }
    }

    // 按 messageIndex 倒序 (最新的在最上面)
    result.sort((a, b) => b.messageIndex - a.messageIndex)
    return result
  }

  // ==================== 主加载函数 ====================

  async function loadSubAgents(sessionId: string, messages: ChatMessage[]): Promise<void> {
    loading.value = true

    try {
      if (USE_MOCK_DATA) {
        subAgents.value = getMockSubAgents()
        return
      }

      if (!sessionId) {
        subAgents.value = []
        return
      }

      // 并行获取 API 和扫描消息
      const [apiAgents, scannedAgents] = await Promise.all([
        fetchFromApi(sessionId),
        Promise.resolve(scanFromMessages(messages)),
      ])

      subAgents.value = mergeLists(apiAgents, scannedAgents)
    } finally {
      loading.value = false
    }
  }

  // ==================== 会话切换 ====================

  async function enterSubAgent(childSessionId: string): Promise<void> {
    // 将当前会话压入父级栈 (保存会话ID和标题)
    parentChain.value = [...parentChain.value, {
      sessionId: chat.currentSessionId.value,
      title: chat.currentSessionTitle.value,
    }]

    // 标记现有流式消息完成并切换到子会话
    const sm = useStreamingMessageSingleton()
    const streamingMsg = chat.messages.value.find(m => m.isStreaming === true)
    if (streamingMsg) streamingMsg.isStreaming = false
    sm.setActiveSessionId(childSessionId)

    // 更新当前会话 ID（仅本地）
    chat.currentSessionId.value = childSessionId

    // 清理并加载子会话历史
    chat.clearMessages()
    await chat.loadChatHistory(childSessionId)
  }

  async function returnToParent(): Promise<void> {
    if (parentChain.value.length === 0) return

    // 弹出栈顶 (当前层级的直接父级)
    const chain = [...parentChain.value]
    const parent = chain.pop()!
    parentChain.value = chain
    subAgents.value = []

    await chat.switchSession(parent.sessionId)
  }

  return {
    subAgents,
    isChildMode,
    parentChain,
    parentSessionTitle,
    showList,
    loading,
    loadSubAgents,
    scanFromMessages,
    enterSubAgent,
    returnToParent,
  }
}
