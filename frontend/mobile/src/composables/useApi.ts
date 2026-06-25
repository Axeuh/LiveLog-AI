/**
 * API Composable
 *
 * 提供 token 管理、登录/登出、以及所有 API 函数的统一入口。
 *
 * Token 优先级 (与原版一致):
 *   1. URL 参数 ?token=xxx
 *   2. localStorage 'mobile_token'
 *
 * 使用方式:
 *   // 在 App.vue 或 LoginOverlay 中使用:
 *   const { login, logout, isLoggedIn, onAuthFail } = useApi()
 *
 *   // 在任何组件中获取 API 函数:
 *   const { fetchDashboard, fetchHealthQuery } = useApi()
 *   const dash = await fetchDashboard('2026-06-22')
 */

import { ref, onMounted } from 'vue';
import {
  setToken,
  clearToken,
  getToken,
  onAuthFail as clientOnAuthFail,
  offAuthFail as clientOffAuthFail,
  apiGet,
  apiPost,
} from '@/api/client';
import type { AuthFailHandler } from '@/api/client';

// 重新导出 API 函数供 composable 用户直接使用
export {
  apiGet,
  apiPost,
};

// 重新导出 health API
export {
  fetchDashboard,
  fetchHealthQuery,
} from '@/api/health';

// 重新导出 session API
export {
  listSessions,
  fetchCurrentSessionId,
  getSessionMessages,
  sendMessage,
  createSession,
  switchSession,
} from '@/api/session';

// 重新导出 files API
export {
  fetchDirectory,
  fetchFileContent,
  getFileRawUrl,
} from '@/api/files';

// 重新导出 SSE/WS (非 composable 版本)
export {
  createSSEConnection,
  disconnectSSE,
} from '@/api/sse';
export {
  createWsConnection,
  disconnectWs,
} from '@/api/ws';

// ==================== 登录状态管理 ====================

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

/** useApi 返回值 */
export interface UseApiReturn {
  /** 当前登录状态 */
  isLoggedIn: import('vue').Ref<boolean>;
  /** 当前 token (getter) */
  token: string;
  /** 登录 (POST /login, 成功后保存 token 到 localStorage) */
  login: (username: string, password: string) => Promise<LoginResponse | null>;
  /** 登出 (清除 token 和 localStorage) */
  logout: () => void;
  /** 注册 auth fail 回调 (LoginOverlay 通过此函数打开登录弹窗) */
  onAuthFail: (handler: AuthFailHandler) => void;
  /** 移除 auth fail 回调 */
  offAuthFail: (handler: AuthFailHandler) => void;
}

/**
 * 初始化 token: URL 参数 > localStorage
 * 与原版 index.original.html 的 token 初始化逻辑一致
 */
function initToken(): void {
  try {
    const urlToken = new URLSearchParams(window.location.search).get('token');
    const localToken = localStorage.getItem('mobile_token') || '';

    if (urlToken) {
      setToken(urlToken);
      // URL token 存在时也写入 localStorage
      localStorage.setItem('mobile_token', urlToken);
    } else if (localToken) {
      setToken(localToken);
    } else {
      setToken('');
    }
  } catch (e) {
    console.warn('[useApi] Token 初始化失败:', e);
    // localStorage 不可用时只从 URL 获取
    try {
      const urlToken = new URLSearchParams(window.location.search).get('token');
      setToken(urlToken || '');
    } catch (e2) {
      setToken('');
    }
  }
}

/**
 * API Composable — 主入口
 *
 * 每个组件都可独立调用 useApi(), 它们共享同一个底层 token
 * (因为 client.ts 中的 _token 是模块级单例)
 */
export function useApi(): UseApiReturn {
  const isLoggedIn = ref<boolean>(!!getToken());

  // 初始化 token (仅首次)
  if (!getToken()) {
    initToken();
    isLoggedIn.value = !!getToken();
  }

  /**
   * 登录
   * POST /login { username, password }
   * 成功后保存 token 到 client 和 localStorage
   */
  async function login(
    username: string,
    password: string,
  ): Promise<LoginResponse | null> {
    try {
      const r = await fetch('/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password } satisfies LoginRequest),
      });
      const data: LoginResponse = await r.json();

      if (data.success && data.token) {
        setToken(data.token);
        localStorage.setItem('mobile_token', data.token);
        isLoggedIn.value = true;
      }

      return data;
    } catch (e) {
      console.error('[useApi] 登录失败:', e);
      return null;
    }
  }

  /**
   * 登出
   * 清除 token 和 localStorage
   */
  function logout(): void {
    clearToken();
    localStorage.removeItem('mobile_token');
    isLoggedIn.value = false;
  }

  return {
    isLoggedIn,
    get token(): string {
      return getToken();
    },
    login,
    logout,
    onAuthFail: clientOnAuthFail,
    offAuthFail: clientOffAuthFail,
  };
}

/**
 * 提供全局 auth fail 监听 (供 App.vue / LoginOverlay 使用)
 *
 * 使用方式:
 *   // 在 App.vue setup 中:
 *   const { useGlobalAuthListener } = useApi()
 *   useGlobalAuthListener(() => { showLoginOverlay() })
 *
 * @deprecated 直接使用 useApi().onAuthFail 即可
 */
export function useGlobalAuthListener(handler: AuthFailHandler): {
  register: () => void;
  unregister: () => void;
} {
  function register(): void {
    clientOnAuthFail(handler);
  }

  function unregister(): void {
    clientOffAuthFail(handler);
  }

  return { register, unregister };
}

/**
 * 自动初始化 token (适合在 App.vue 的 setup 中调用一次)
 *
 * 使用方式:
 *   // App.vue <script setup>
 *   useApiInit()
 *   const { isLoggedIn } = useApi()
 */
export function useApiInit(): { isLoggedIn: ReturnType<typeof ref<boolean>> } {
  const isLoggedIn = ref<boolean>(!!getToken());

  onMounted(() => {
    initToken();
    isLoggedIn.value = !!getToken();
  });

  return { isLoggedIn };
}
