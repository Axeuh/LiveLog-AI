/**
 * 聊天会话/消息/SSE 流式类型
 *
 * 对应 /api/screen/session/* API 及 SSE /api/screen/events/stream
 */

// ==================== 会话类型 ====================

/** 单个会话信息 */
export interface SessionInfo {
  /** 会话 ID */
  id: string;
  /** 会话标题 */
  title: string;
  /** 日期文本 (已格式化) */
  date: string;
  /** 预览文本 */
  preview: string;
  /** 当前是否激活 */
  active?: boolean;
  /** 服务端 session_id (API 返回时可能用) */
  session_id?: string;
  /** 创建时间 (ISO 字符串) */
  created_at?: string;
}

/** /api/screen/session/list 响应 */
export interface SessionListResponse {
  local_sessions: SessionInfo[];
  current_session?: string;
}

/** 创建会话请求体 */
export interface CreateSessionRequest {
  title: string;
}

/** 创建会话响应 */
export interface CreateSessionResponse {
  session_id: string;
  title?: string;
}

/** 切换会话请求体 */
export interface SwitchSessionRequest {
  session_id: string;
}

// ==================== 消息类型 ====================

/** 消息角色 */
export type MessageRole = 'user' | 'assistant';

/** 消息 part 类型 */
export type MessagePartType =
  | 'text'
  | 'reasoning'
  | 'thought'
  | 'tool'
  | 'tool_call'
  | 'tool_result';

/** 消息中的单个 part (用于结构化消息) */
export interface MessagePart {
  type: MessagePartType;
  text?: string;
  /** 工具名称 (tool/tool_call 类型) */
  tool?: string;
  /** 工具调用状态 */
  state?: {
    status?: string;
    input?: Record<string, unknown>;
    output?: string;
  };
}

/** 单条聊天消息 */
export interface ChatMessage {
  /** 消息元信息 */
  info?: {
    role: MessageRole;
  };
  /** 角色 (无 info 时使用此字段) */
  role?: MessageRole;
  /** 时间戳 (ISO 字符串) */
  timestamp?: string;
  /** 创建时间 (ISO 字符串) */
  created_at?: string;
  /** 纯文本内容 (无 parts 时使用) */
  content?: string;
  /** 纯文本内容 (备选字段) */
  text?: string;
  /** 结构化消息部分 */
  parts?: MessagePart[];
}

/** /api/screen/session/{id}/messages 响应 */
export interface MessagesResponse {
  messages: ChatMessage[];
}

// ==================== 流式 Part 类型 ====================

/**
 * 流式渲染中的 Part 状态
 * 用于 SSE message.part.updated 事件处理
 */
export interface StreamPart {
  type: MessagePartType;
  text: string;
  /** 工具名称 (tool/tool_call 类型) */
  toolName?: string;
  /** 工具状态 (running / completed / error) */
  toolStatus?: string;
  /** 工具输入 */
  toolInput?: Record<string, unknown>;
  /** 工具输出 */
  toolOutput?: string;
}

/** 流式 Part 映射 (partId -> StreamPart) */
export type StreamPartsMap = Record<string, StreamPart>;

/** 流式折叠状态映射 (partId -> boolean) */
export type StreamCollapsedMap = Record<string, boolean>;
