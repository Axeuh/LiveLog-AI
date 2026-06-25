/**
 * API 响应包装类型与通用接口
 *
 * 后端 API 基本响应格式: { status: 'ok', data?: T }
 * 部分接口直接返回数据对象 (如 /api/mobile/dashboard)
 * 文件内容接口可能返回纯文本
 */

/** 通用 API 成功响应 */
export interface ApiResponse<T = unknown> {
  status: 'ok' | 'error';
  data?: T;
  message?: string;
}

/** 登录请求体 */
export interface LoginRequest {
  username: string;
  password: string;
}

/** 登录响应 */
export interface LoginResponse {
  success: boolean;
  token: string;
  message?: string;
}

/**
 * SSE 事件数据结构
 * 来自 /api/screen/events/stream
 * 外层可能直接是 { type, payload } 或通过 proxy 包装
 */
export interface SSEEvent {
  /** 事件类型 (proxy 场景下在 payload.type 中) */
  type?: string;
  /** 事件负载 */
  payload?: SSEPayload;
}

/** SSE 事件负载 */
export interface SSEPayload {
  type: string;
  properties?: SSEProperties;
}

/** SSE 事件属性 */
export interface SSEProperties {
  /** 关联的会话 ID */
  sessionID?: string;
  /** 关联的消息 ID */
  messageID?: string;
  /** 消息部分 (part) 数据 */
  part?: SSEMessagePart;
}

/**
 * SSE 消息部分 (part) 数据
 * 用于 message.part.updated / message.part.delta 等事件
 */
export interface SSEMessagePart {
  id: string;
  type?: string;
  text?: string;
  /** tool / tool_call 类型的工具名称 */
  tool?: string;
  /** 工具执行状态 */
  state?: {
    status?: string;
    input?: Record<string, unknown>;
    output?: string;
  };
  /** 消息 ID (部分场景下) */
  messageID?: string;
}
