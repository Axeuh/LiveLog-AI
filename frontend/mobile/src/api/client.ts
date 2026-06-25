/**
 * 核心 API 客户端
 *
 * 提供 apiGet / apiPost 封装，自动注入 Authorization header，
 * 401 时触发 onAuthFail 回调。
 *
 * 使用方式:
 *   import { apiGet, apiPost, setToken, onAuthFail } from '@/api/client'
 *   setToken('xxx')
 *   const data = await apiGet<DashboardResponse>('/api/mobile/dashboard?date=2026-06-22')
 *
 * 与原版一致:
 *   - 401 → 触发 auth fail 回调 (LoginOverlay 监听)
 *   - 非 200 → 抛出 Error 后 catch 打印 + 返回 null
 *   - asText=true 强制返回文本, 或 content-type 含 text/ 时自动文本
 */

// ==================== 类型定义 ====================

/** Auth fail 监听函数类型 */
export type AuthFailHandler = () => void;

// ==================== 内部状态 ====================

/** 当前认证 token */
let _token = '';

/** 注册的 auth fail 回调列表 */
const _authFailHandlers: AuthFailHandler[] = [];

// ==================== Token 管理 ====================

/** 获取当前 token */
export function getToken(): string {
  return _token;
}

/** 设置 token (登录成功或初始化时调用) */
export function setToken(token: string): void {
  _token = token;
}

/** 清除 token (登出时调用) */
export function clearToken(): void {
  _token = '';
}

// ==================== Auth fail 事件 ====================

/** 注册 auth fail 监听 (LoginOverlay 通过此函数挂载) */
export function onAuthFail(handler: AuthFailHandler): void {
  if (!_authFailHandlers.includes(handler)) {
    _authFailHandlers.push(handler);
  }
}

/** 移除 auth fail 监听 */
export function offAuthFail(handler: AuthFailHandler): void {
  const idx = _authFailHandlers.indexOf(handler);
  if (idx >= 0) {
    _authFailHandlers.splice(idx, 1);
  }
}

/** 触发所有 auth fail 回调 */
function emitAuthFail(): void {
  for (const handler of _authFailHandlers) {
    try {
      handler();
    } catch (e) {
      console.error('[API] Auth fail handler error:', e);
    }
  }
}

// ==================== 请求方法 ====================

/**
 * GET 请求
 * @param path API 路径 (如 '/api/mobile/dashboard?date=2026-06-22')
 * @param asText 是否强制返回文本 (默认自动判断)
 * @returns 解析后的数据，失败返回 null
 */
export async function apiGet<T = unknown>(
  path: string,
  asText?: boolean,
): Promise<T | null> {
  try {
    const headers: Record<string, string> = {};
    if (_token) {
      headers['Authorization'] = 'Bearer ' + _token;
    }

    const r = await fetch(path, { headers });

    if (r.status === 401) {
      emitAuthFail();
      return null;
    }
    if (!r.ok) {
      throw new Error('HTTP ' + r.status);
    }

    if (asText) {
      return (await r.text()) as unknown as T;
    }

    const ct = r.headers.get('content-type') || '';
    if (ct.indexOf('text/') >= 0) {
      return (await r.text()) as unknown as T;
    }

    return (await r.json()) as T;
  } catch (e) {
    console.warn('[API] GET', path, e);
    return null;
  }
}

/**
 * POST 请求
 * @param path API 路径
 * @param body 请求体 (自动 JSON.stringify)
 * @returns 解析后的 JSON，失败返回 null
 */
export async function apiPost<T = unknown>(
  path: string,
  body: unknown,
): Promise<T | null> {
  try {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };
    if (_token) {
      headers['Authorization'] = 'Bearer ' + _token;
    }

    const r = await fetch(path, {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
    });

    if (r.status === 401) {
      emitAuthFail();
      return null;
    }
    if (!r.ok) {
      throw new Error('HTTP ' + r.status);
    }

    return (await r.json()) as T;
  } catch (e) {
    console.warn('[API] POST', path, e);
    return null;
  }
}

// ==================== 文件上传 ====================

/** 上传文件响应 */
export interface UploadResponse {
  status: string;
  file_name: string;
  file_path: string;
  file_rel_path: string;
  file_size: number;
  user_id: string;
}

/**
 * 上传文件 (multipart/form-data)
 * @param file 要上传的文件
 * @returns 上传结果，失败返回 null
 */
export async function apiUpload(file: File): Promise<UploadResponse | null> {
  try {
    const formData = new FormData();
    formData.append('file', file);

    const headers: Record<string, string> = {};
    if (_token) {
      headers['Authorization'] = 'Bearer ' + _token;
    }

    const r = await fetch('/api/mobile/upload', {
      method: 'POST',
      headers,
      body: formData,
    });

    if (r.status === 401) {
      emitAuthFail();
      return null;
    }
    if (!r.ok) {
      throw new Error('HTTP ' + r.status);
    }

    return (await r.json()) as UploadResponse;
  } catch (e) {
    console.warn('[API] UPLOAD 失败:', e);
    return null;
  }
}
