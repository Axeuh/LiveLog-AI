/**
 * 聊天会话 API
 *
 * 对应 /api/screen/session/* 接口:
 *   - list     GET  /api/screen/session/list
 *   - messages GET  /api/screen/session/{id}/messages
 *   - message  POST /api/screen/session/message
 *   - create   POST /api/screen/session/create
 *   - switch   POST /api/screen/session/switch
 *
 * 使用方式:
 *   import { listSessions, sendMessage, ... } from '@/api/session'
 */

import { apiGet, apiPost } from '@/api/client';
import type { SessionInfo, ChatMessage } from '@/types';

// ==================== 类型 (内部使用, 不暴露给 types 层) ====================

interface SessionListApiResponse {
  local_sessions: SessionInfo[];
  current_session?: string;
}

interface MessagesApiResponse {
  messages: ChatMessage[];
}

interface CreateSessionApiResponse {
  session_id: string;
  title?: string;
}

interface SendMessageApiResponse {
  status: string;
  [key: string]: unknown;
}

// ==================== API 函数 ====================

/**
 * 获取会话列表
 * GET /api/screen/session/list
 */
export async function listSessions(): Promise<SessionInfo[] | null> {
  const result = await apiGet<SessionListApiResponse>(
    '/api/screen/session/list',
  );
  if (result && result.local_sessions) {
    return result.local_sessions.map((s) => ({
      id: s.id || s.session_id || '',
      title: s.title || '新会话',
      date: s.date || '',
      preview: s.preview || '',
      active: s.active || false,
      session_id: s.session_id,
      created_at: s.created_at,
    }));
  }
  return null;
}

/**
 * 获取当前会话 ID (来自列表 API 的 current_session 字段)
 * GET /api/screen/session/list (复用同一个请求)
 */
export async function fetchCurrentSessionId(): Promise<string | null> {
  const result = await apiGet<SessionListApiResponse>(
    '/api/screen/session/list',
  );
  if (result && result.current_session) {
    return result.current_session;
  }
  return null;
}

/**
 * 获取会话历史消息
 * GET /api/screen/session/{sessionId}/messages
 */
export async function getSessionMessages(
  sessionId: string,
): Promise<ChatMessage[] | null> {
  const result = await apiGet<MessagesApiResponse>(
    '/api/screen/session/' + encodeURIComponent(sessionId) + '/messages',
  );
  if (result && result.messages) {
    return result.messages;
  }
  return null;
}

/**
 * 发送消息
 * POST /api/screen/session/message
 * body: { session_id, content }
 *
 * 注意: 原版使用 { message, session_id }, 这里统一为 content
 */
export async function sendMessage(body: {
  session_id: string;
  content: string;
  prefix_data?: Record<string, string>;
}): Promise<SendMessageApiResponse | null> {
  return apiPost<SendMessageApiResponse>(
    '/api/screen/session/message',
    {
      message: body.content,
      session_id: body.session_id,
      ...(body.prefix_data ? { prefix_data: body.prefix_data } : {}),
    },
  );
}

/**
 * 创建新会话
 * POST /api/screen/session/create
 * body: { title }
 *
 * @returns 新会话 ID, 失败返回 null
 */
export async function createSession(
  title: string,
): Promise<string | null> {
  const result = await apiPost<CreateSessionApiResponse>(
    '/api/screen/session/create',
    { title },
  );
  if (result && result.session_id) {
    return result.session_id;
  }
  return null;
}

/**
 * 切换会话
 * POST /api/screen/session/switch
 * body: { session_id }
 *
 * @returns 是否成功
 */
export async function switchSession(
  sessionId: string,
): Promise<boolean> {
  const result = await apiPost<Record<string, unknown>>(
    '/api/screen/session/switch',
    { session_id: sessionId },
  );
  return result !== null;
}

/**
 * 重命名会话
 * POST /api/screen/session/update-title
 * body: { session_id, title }
 *
 * @returns 是否成功
 */
export async function renameSession(
  sessionId: string,
  title: string,
): Promise<boolean> {
  const result = await apiPost<{ status: string }>(
    '/api/screen/session/update-title',
    { session_id: sessionId, title },
  );
  return result !== null && result.status === 'updated';
}
