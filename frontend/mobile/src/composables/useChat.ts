/**
 * 聊天会话 Composable — 会话列表、当前会话、消息管理
 *
 * 管理会话列表 (sessions)、当前会话 ID、消息历史。
 * 与 useStreamingMessage 配合处理 SSE 流式回复。
 *
 * 使用方式:
 *   const { sessions, currentSessionId, messages, sendMessage, switchSession } = useChat()
 *   await loadSessions()
 *   await switchSession('session-id')
 *   await sendMessage('你好')
 */

import { ref, computed, readonly, type InjectionKey, type Ref, type ComputedRef } from 'vue';
import type { SessionInfo, ChatMessage, TokenUsage } from '@/types';
import {
  getSessionMessages as apiGetSessionMessages,
  sendMessage as apiSendMessage,
  createSession as apiCreateSession,
  switchSession as apiSwitchSession,
  renameSession as apiRenameSession,
} from '@/api/session';
import { apiGet, apiUpload } from '@/api/client';
import { useStreamingMessageSingleton } from '@/composables/useStreamingMessage';

// ==================== 类型定义 ====================

/** useChat 返回值 */
export interface UseChatReturn {
  /** 会话列表 */
  sessions: Ref<SessionInfo[]>;
  /** 当前会话 ID */
  currentSessionId: Ref<string>;
  /** 当前会话标题 (computed) */
  currentSessionTitle: ComputedRef<string>;
  /** 当前会话消息列表 */
  messages: Ref<ChatMessage[]>;
  /** 正在加载消息历史 */
  loadingMessages: Readonly<Ref<boolean>>;
  /** 正在发送消息 */
  sendingMessage: Readonly<Ref<boolean>>;
  /**
   * 加载会话列表
   * 自动设置 currentSessionId 为 API 返回的当前会话
   */
  loadSessions: () => Promise<void>;
  /**
   * 切换会话
   * 清理流式状态, 加载会话历史
   * @param sessionId 目标会话 ID
   */
  switchSession: (sessionId: string) => Promise<void>;
  /**
   * 创建新会话
   * @param title 会话标题 (默认 '新会话')
   * @returns 新会话 ID, 失败返回 null
   */
  createNewSession: (title?: string) => Promise<string | null>;
  /**
   * 加载会话历史消息
   * @param sessionId 会话 ID
   */
  loadChatHistory: (sessionId: string) => Promise<void>;
  /**
   * 发送消息（可选附带多个文件）
   * 发送后等待 SSE 流式回复, 完成后重新加载历史
   * @param text 消息文本
   * @param files 可选的文件数组
   * @returns 是否发送成功
   */
  sendMessage: (text: string, files?: File[]) => Promise<boolean>;
  /**
   * 清除聊天消息 (本地)
   */
  clearMessages: () => void;
  /**
   * 重命名当前会话
   * @param sessionId 会话 ID
   * @param newTitle 新标题
   * @returns 是否成功
   */
  renameSession: (sessionId: string, newTitle: string) => Promise<boolean>;
  /**
   * 初始化流式消息系统 (注入 messages/activeSessionId refs)
   * 在 ChatView onMounted 中调用
   */
  initStreaming: () => void;
}

/** useChat 注入 key */
export const USE_CHAT_KEY: InjectionKey<UseChatReturn> =
  Symbol('useChat');

// ==================== Composable ====================

/**
 * 聊天会话 Composable — 会话列表、当前会话、消息管理
 *
 * 封装会话 CRUD 和消息发送, 与 useStreamingMessage 配合处理流式回复。
 */
export function useChat(): UseChatReturn {
  const sessions = ref<SessionInfo[]>([]);
  const currentSessionId = ref<string>('');
  const messages = ref<ChatMessage[]>([]);
  const loadingMessages = ref(false);
  const sendingMessage = ref(false);

  /** 当前会话标题 */
  const currentSessionTitle = computed<string>(() => {
    const cur = sessions.value.find((s) => s.id === currentSessionId.value);
    return cur?.title || '';
  });

  // ==================== 会话管理 ====================

  /**
   * 加载会话列表
   *
   * 调用 /api/screen/session/list
   * 自动设置当前会话 ID
   */
  async function loadSessions(): Promise<void> {
    try {
      const payload = await apiGet<{
        local_sessions: SessionInfo[]
        current_session?: string
      }>('/api/screen/session/list')
      if (payload && payload.local_sessions && payload.local_sessions.length > 0) {
        // 映射 raw API 数据到 SessionInfo 格式 (后端返回 session_id 而非 id)
        sessions.value = (payload.local_sessions as unknown as Record<string, unknown>[]).map((s) => ({
          id: String(s.id || s.session_id || ''),
          title: String(s.title || '新会话'),
          date: String(s.date || s.created_at || ''),
          preview: String(s.preview || ''),
          session_id: String(s.session_id || s.id || ''),
          created_at: String(s.created_at || ''),
        })) as SessionInfo[]
        // 优先使用后端返回的 current_session
        const curId = payload.current_session
        if (curId && sessions.value.some((s: SessionInfo) => s.id === curId || s.session_id === curId)) {
          currentSessionId.value = curId
        } else if (!currentSessionId.value && sessions.value.length > 0) {
          currentSessionId.value = sessions.value[0].id || sessions.value[0].session_id || ''
        }
        // 同步 SSE 活跃会话过滤
        if (currentSessionId.value) {
          const sm = useStreamingMessageSingleton()
          sm.setActiveSessionId(currentSessionId.value)
        }
      }
    } catch (e) {
      console.error('[useChat] 加载会话列表失败:', e)
    }
  }

  /**
   * 切换会话
   *
   * 1. 清理流式状态 (useStreamingMessage)
   * 2. 发送 API switch
   * 3. 加载会话历史
   *
   * @param sessionId 目标会话 ID
   */
  async function switchSession(sessionId: string): Promise<void> {
    if (!sessionId) return

    // 标记现有流式消息完成并设置活跃会话
    const streamingMsg = messages.value.find(m => m.isStreaming === true)
    if (streamingMsg) streamingMsg.isStreaming = false
    const sm = useStreamingMessageSingleton();
    sm.setActiveSessionId(sessionId);

    // 更新本地状态
    currentSessionId.value = sessionId;
    sessions.value = sessions.value.map((s) => ({
      ...s,
      active: s.id === sessionId,
    }));

    // API 切换
    try {
      await apiSwitchSession(sessionId);
    } catch (e) {
      console.error('[useChat] API 切换会话失败:', e);
    }

    // 加载历史消息
    await loadChatHistory(sessionId);
  }

  /**
   * 创建新会话
   *
   * 1. 清理流式状态
   * 2. 调用 API 创建
   * 3. 添加到会话列表头部
   * 4. 切换为新会话
   *
   * @param title 会话标题 (默认 '新会话')
   * @returns 新会话 ID, 失败返回 null
   */
  async function createNewSession(title = '新会话'): Promise<string | null> {
    // 标记现有流式消息完成
    const streamingMsg = messages.value.find(m => m.isStreaming === true)
    if (streamingMsg) streamingMsg.isStreaming = false
    const sm = useStreamingMessageSingleton();

    try {
      const sessionId = await apiCreateSession(title);
      if (sessionId) {
        // 添加到列表头部
        sessions.value.unshift({
          id: sessionId,
          title,
          date: '今日',
          preview: '',
          active: true,
        });
        // 其他标记为非活跃
        sessions.value = sessions.value.map((s) => ({
          ...s,
          active: s.id === sessionId,
        }));
        currentSessionId.value = sessionId;
        sm.setActiveSessionId(sessionId);
        messages.value = [];
        return sessionId;
      }
    } catch (e) {
      console.error('[useChat] 创建会话失败:', e);
    }

    return null;
  }

  // ==================== 消息管理 ====================

  /**
   * 加载会话历史消息
   *
   * @param sessionId 会话 ID
   */
  async function loadChatHistory(sessionId: string): Promise<void> {
    if (!sessionId) return;

    loadingMessages.value = true;
    const sm = useStreamingMessageSingleton();
    try {
      const result = await apiGetSessionMessages(sessionId);
      if (result) {
        messages.value = result;

        // 路径2: 从消息历史中提取最新 assistant 消息的 tokens
        for (let i = result.length - 1; i >= 0; i--) {
          const msg = result[i] as Record<string, unknown>;
          const info = msg.info as Record<string, unknown> | undefined;
          const tokens = info?.tokens as TokenUsage | undefined;
          if (tokens && tokens.total > 0) {
            sm.updateTokens(tokens);
            break;
          }
        }
      } else {
        messages.value = [];
        sm.updateTokens(null);
      }
    } catch (e) {
      console.error('[useChat] 加载消息历史失败:', e);
      messages.value = [];
      sm.updateTokens(null);
    } finally {
      loadingMessages.value = false;
    }
  }

  /**
   * 发送消息（可选附带多个文件）
   *
   * 1. 如果有文件，先逐个上传获取路径
   * 2. 将所有文件路径拼入消息文本开头
   * 3. 调用 API 发送消息
   * 4. 等待 SSE 流式回复
   * 5. 完成后构建流式消息并追加到列表
   *
   * @param text 消息文本
   * @param files 可选的文件数组
   * @returns 是否发送成功
   */
  async function sendMessage(text: string, files?: File[]): Promise<boolean> {
    // 既没有文本也没有文件，不允许发送
    if (!text.trim() && (!files || files.length === 0)) return false;
    if (!currentSessionId.value) return false;

    const sm = useStreamingMessageSingleton();

    // 标记旧的流式消息完成
    const oldStreaming = messages.value.find(m => m.isStreaming === true)
    if (oldStreaming) oldStreaming.isStreaming = false

    sendingMessage.value = true;

    try {
      // 构建最终消息文本
      let finalText = text.trim();

      // 如果有文件，逐个上传
      if (files && files.length > 0) {
        const fileInfos: string[] = []
        for (const f of files) {
          const uploadResult = await apiUpload(f)
          if (uploadResult && uploadResult.status === 'ok') {
            fileInfos.push(uploadResult.file_path.replace(/\\/g, '/'))
          } else {
            sendingMessage.value = false
            return false
          }
        }
        const fileLines = fileInfos.map((p) => `- ${p}`).join('\n')
        finalText = `[用户上传了 ${files.length} 个文件:]\n${fileLines}\n` + (finalText || '(无文字)')
      }

      // 先将用户消息加入列表 (显示为 user 气泡)
      messages.value = [...messages.value, {
        role: 'user' as const,
        content: finalText,
        timestamp: new Date().toISOString(),
      }]

      // 创建 AI 占位符消息 (插入 messages，SSE 事件直接在 messages.value 中更新其 parts)
      const placeholder: ChatMessage = {
        role: 'assistant',
        parts: [],
        isStreaming: true,
        timestamp: new Date().toISOString(),
      }
      messages.value = [...messages.value, placeholder]

      // 创建 pending promise (SSE 完成时 resolve)
      const pending = sm.createPendingPromise();

      // 发送消息
      const result = await apiSendMessage({
        session_id: currentSessionId.value,
        content: finalText,
      });

      if (!result) {
        placeholder.isStreaming = false
        sendingMessage.value = false;
        return false;
      }

      // 等待 SSE 流式回复完成 (SSE handler 直接在 messages.value 中更新 parts)
      await pending;

      // placeholder 已在 messages.value 中，finalizeStreaming 已标记 isStreaming=false
      return true;
    } catch (e) {
      console.error('[useChat] 发送消息失败:', e);
      // 标记流式消息完成
      const failMsg = messages.value.find(m => m.isStreaming === true)
      if (failMsg) failMsg.isStreaming = false
      return false;
    } finally {
      sendingMessage.value = false;
    }
  }

  /**
   * 清除聊天消息 (本地)
   */
  function clearMessages(): void {
    messages.value = [];
  }

  /**
   * 重命名会话
   */
  async function renameSession(sessionId: string, newTitle: string): Promise<boolean> {
    if (!sessionId || !newTitle.trim()) return false;
    try {
      const ok = await apiRenameSession(sessionId, newTitle.trim());
      if (ok) {
        sessions.value = sessions.value.map((s) =>
          s.id === sessionId ? { ...s, title: newTitle.trim() } : s,
        );
      }
      return ok;
    } catch (e) {
      console.error('[useChat] 重命名会话失败:', e);
      return false;
    }
  }

  // ==================== 流式消息系统初始化 ====================

  /**
   * 初始化流式消息系统
   * 注入 messages ref 和 currentSessionId ref，
   * 使 SSE 事件能直接在 messages.value 中找到并更新流式消息。
   */
  function initStreaming(): void {
    const sm = useStreamingMessageSingleton();
    sm.configure({
      messages,
      activeSessionId: currentSessionId,
    });
  }

  return {
    sessions,
    currentSessionId,
    currentSessionTitle,
    messages,
    loadingMessages: readonly(loadingMessages),
    sendingMessage: readonly(sendingMessage),
    loadSessions,
    switchSession,
    createNewSession,
    loadChatHistory,
    sendMessage,
    clearMessages,
    renameSession,
    initStreaming,
  };
}

// ==================== 单例 ====================

let _singleton: UseChatReturn | null = null;

/**
 * 全局单例 useChat (跨组件共享同一个会话状态)
 *
 * 使用方式:
 *   const chat = useChatSingleton()
 *   await chat.loadSessions()
 */
export function useChatSingleton(): UseChatReturn {
  if (!_singleton) {
    _singleton = useChat();
  }
  return _singleton;
}
