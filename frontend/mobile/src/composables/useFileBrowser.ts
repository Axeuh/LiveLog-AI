/**
 * 文件浏览器 Composable — 文件树加载、JSONL 分页与搜索过滤
 *
 * 管理文件树浏览 (展开/收起)、文件内容加载、JSONL 分页渲染和搜索过滤。
 * 对应 index.original.html 中的 loadDirectory, _jsonlState, renderJsonlPage 等。
 *
 * 使用方式:
 *   const { fileEntries, loadDirectory, loadFileContent, jsonlState } = useFileBrowser()
 *   await loadDirectory('/')
 *   const content = await loadFileContent('/path/file.jsonl')
 *   // JSONL 分页
 *   jsonlState.value = { objects, page: 1, pageSize: 50, ... }
 *   renderJsonlPage()
 */

import { ref, readonly, type InjectionKey, type Ref } from 'vue';
import type { FileEntry, FileContentJsonResponse } from '@/types';
import { fetchDirectory, fetchFileContent as apiFetchFileContent } from '@/api/files';

// ==================== 类型定义 ====================

/** JSONL 分页状态 */
export interface JsonlState {
  /** 全部对象数组 */
  objects: Record<string, unknown>[];
  /** 全部对象的原始备份 (用于重置) */
  _allObjects: Record<string, unknown>[];
  /** 当前页码 (1-based) */
  page: number;
  /** 每页条数 */
  pageSize: number;
  /** 是否是 perception.jsonl (显示工具栏) */
  isPerception: boolean;
  /** 搜索文本 */
  searchText: string;
  /** 时间筛选起始 */
  timeFrom: string;
  /** 时间筛选结束 */
  timeTo: string;
}

/** useFileBrowser 返回值 */
export interface UseFileBrowserReturn {
  /** 文件浏览范围 */
  fileScope: Ref<string>;
  /** 当前目录文件列表 */
  fileEntries: Ref<FileEntry[]>;
  /** JSONL 分页状态 */
  jsonlState: Ref<JsonlState | null>;
  /** 加载中 */
  loading: Readonly<Ref<boolean>>;
  /**
   * 加载目录列表
   * @param path 目录路径
   */
  loadDirectory: (path: string) => Promise<void>;
  /**
   * 加载文件内容
   * @param path 文件路径
   * @returns 文件内容 (JSON 或文本)
   */
  loadFileContent: (path: string) => Promise<FileContentJsonResponse | string | null>;
  /**
   * 渲染 JSONL 分页 (由组件在更新 DOM 时调用)
   * 纯数据处理, 返回渲染需要的信息
   */
  renderJsonlPage: () => JsonlRenderInfo | null;
  /**
   * 加载更多 JSONL 条目 (翻页)
   */
  loadMoreJsonl: () => void;
  /**
   * JSONL 搜索
   * @param text 搜索文本
   */
  doJsonlSearch: (text: string) => void;
  /**
   * JSONL 时间筛选
   * @param from 起始时间 (HH:MM)
   * @param to 结束时间 (HH:MM)
   */
  doJsonlTimeFilter: (from: string, to: string) => void;
  /**
   * 重置 JSONL 筛选
   */
  doJsonlReset: () => void;
  /**
   * 跳转到 JSONL 底部 (加载所有)
   */
  doJsonlScrollBottom: () => void;
  /**
   * 解析 JSONL 时间为秒数
   * @param t 时间值 (支持 "HH:MM:SS" 字符串或 Unix 秒数)
   * @returns 秒数, 失败返回 null
   */
  parseJsonlTime: (t: unknown) => number | null;
  /**
   * 格式化秒数为 HH:MM
   * @param seconds 秒数
   * @returns 格式化时间字符串
   */
  fmtJsonlTime: (seconds: number | null | undefined) => string;
}

/** JSONL 分页渲染信息 */
export interface JsonlRenderInfo {
  /** 当前显示的对象切片 */
  visibleObjects: Record<string, unknown>[];
  /** 总对象数 */
  total: number;
  /** 已显示数 */
  displayed: number;
  /** 是否还有更多 */
  hasMore: boolean;
}

/** useFileBrowser 注入 key */
export const USE_FILE_BROWSER_KEY: InjectionKey<UseFileBrowserReturn> =
  Symbol('useFileBrowser');

// ==================== 工具函数 (纯) ====================

/**
 * 解析 JSONL 时间为秒数
 *
 * 支持格式:
 *   - "HH:MM:SS" 字符串
 *   - "HH:MM" 字符串
 *   - Unix 时间戳 (number)
 *
 * @param t 时间值
 * @returns 秒数, 无法解析返回 null
 */
function parseJsonlTime(t: unknown): number | null {
  if (t == null) return null;

  if (typeof t === 'string') {
    const parts = t.split(':');
    if (parts.length >= 2) {
      const h = parseInt(parts[0], 10) || 0;
      const m = parseInt(parts[1], 10) || 0;
      const sec = parseInt(parts[2], 10) || 0;
      return h * 3600 + m * 60 + sec;
    }
  }

  if (typeof t === 'number') return t;

  return null;
}

/**
 * 格式化秒数为 HH:MM
 *
 * @param seconds 秒数
 * @returns 格式化字符串, 如 "14:32"
 */
function fmtJsonlTime(seconds: number | null | undefined): string {
  if (seconds == null) return '';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return (
    h.toString().padStart(2, '0') +
    ':' +
    m.toString().padStart(2, '0')
  );
}

// ==================== 默认常量 ====================

/** 文件浏览范围 (默认为 root) */
const DEFAULT_SCOPE = 'root';

// ==================== Composable ====================

/**
 * 文件浏览器 Composable — 文件树加载、JSONL 分页与搜索过滤
 *
 * 管理文件浏览器的所有状态和操作:
 * - 文件树: 加载目录、展开/收起 (由组件控制 DOM)
 * - 文件预览: 加载文件文本内容
 * - JSONL: 分页渲染、搜索、时间筛选、重置
 */
export function useFileBrowser(): UseFileBrowserReturn {
  const fileScope = ref<string>(DEFAULT_SCOPE);
  const fileEntries = ref<FileEntry[]>([]);
  const jsonlState = ref<JsonlState | null>(null);
  const loading = ref(false);

  // ==================== 文件树 ====================

  /**
   * 加载目录列表
   *
   * @param path 目录路径 (如 '/', '/ai/data/2026-06-22')
   */
  async function loadDirectory(path: string): Promise<void> {
    loading.value = true;
    try {
      const result = await fetchDirectory(path);
      if (result && result.entries) {
        fileEntries.value = result.entries;
      } else {
        fileEntries.value = [];
      }
    } catch (e) {
      console.error('[useFileBrowser] 加载目录失败:', e);
      fileEntries.value = [];
    } finally {
      loading.value = false;
    }
  }

  /**
   * 加载文件内容
   *
   * 支持 JSON/JSONL (返回 { objects }) 和文本文件。
   *
   * @param path 文件路径
   * @returns 文件内容
   */
  async function loadFileContent(
    path: string,
  ): Promise<FileContentJsonResponse | string | null> {
    try {
      return await apiFetchFileContent(path);
    } catch (e) {
      console.error('[useFileBrowser] 加载文件失败:', e);
      return null;
    }
  }

  // ==================== JSONL 分页 ====================

  /**
   * 渲染 JSONL 分页 — 返回当前页的数据切片信息
   *
   * 组件根据返回的 JsonlRenderInfo 渲染 DOM。
   *
   * @returns 渲染信息, 无状态时返回 null
   */
  function renderJsonlPage(): JsonlRenderInfo | null {
    const s = jsonlState.value;
    if (!s) return null;

    const end = Math.min(s.page * s.pageSize, s.objects.length);
    const visibleObjects = s.objects.slice(0, end);

    return {
      visibleObjects,
      total: s.objects.length,
      displayed: end,
      hasMore: end < s.objects.length,
    };
  }

  /**
   * 加载更多 JSONL 条目 (翻页)
   */
  function loadMoreJsonl(): void {
    const s = jsonlState.value;
    if (s) {
      s.page += 1;
    }
  }

  /**
   * JSONL 搜索
   *
   * @param text 搜索文本 (空字符串清除搜索)
   */
  function doJsonlSearch(text: string): void {
    const s = jsonlState.value;
    if (!s) return;

    s.searchText = text;
    s.page = 1;

    if (!text) {
      // 清除搜索: 恢复所有对象
      s.objects = [...s._allObjects];
      s.searchText = '';
    }
    // 注意: 实际过滤由组件在渲染时根据 searchText 和 _allObjects 执行
    // 这里只更新状态, 组件调用 renderJsonlPage() 后自行过滤
  }

  /**
   * JSONL 时间筛选
   *
   * @param from 起始时间 (HH:MM, 空字符串表示 00:00)
   * @param to 结束时间 (HH:MM, 空字符串表示 23:59)
   */
  function doJsonlTimeFilter(from: string, to: string): void {
    const s = jsonlState.value;
    if (!s) return;

    s.searchText = ''; // 清除文本搜索

    if (!from && !to) {
      // 清除筛选
      s.objects = [...s._allObjects];
      s.page = 1;
      return;
    }

    const fromSec = from ? parseJsonlTime(from) ?? 0 : 0;
    const toSec = to ? parseJsonlTime(to) ?? 24 * 3600 - 1 : 24 * 3600 - 1;

    const all = s._allObjects;
    const filtered = all.filter((obj) => {
      const t = parseJsonlTime(obj.t);
      return t !== null && t >= fromSec && t <= toSec;
    });

    s.objects = filtered;
    s.page = 1;
    s.timeFrom = from;
    s.timeTo = to;
  }

  /**
   * 重置 JSONL 筛选
   */
  function doJsonlReset(): void {
    const s = jsonlState.value;
    if (!s) return;

    s.objects = [...s._allObjects];
    s.searchText = '';
    s.timeFrom = '';
    s.timeTo = '';
    s.page = 1;
  }

  /**
   * 跳转到 JSONL 底部 (加载所有条目)
   */
  function doJsonlScrollBottom(): void {
    const s = jsonlState.value;
    if (!s) {
      return;
    }
    s.page = Math.ceil(s.objects.length / s.pageSize);
  }

  return {
    fileScope,
    fileEntries,
    jsonlState,
    loading: readonly(loading),
    loadDirectory,
    loadFileContent,
    renderJsonlPage,
    loadMoreJsonl,
    doJsonlSearch,
    doJsonlTimeFilter,
    doJsonlReset,
    doJsonlScrollBottom,
    parseJsonlTime,
    fmtJsonlTime,
  };
}

// ==================== 单例 ====================

let _singleton: UseFileBrowserReturn | null = null;

/**
 * 全局单例 useFileBrowser (跨组件共享同一个文件浏览状态)
 */
export function useFileBrowserSingleton(): UseFileBrowserReturn {
  if (!_singleton) {
    _singleton = useFileBrowser();
  }
  return _singleton;
}
