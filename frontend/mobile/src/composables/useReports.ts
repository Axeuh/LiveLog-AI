/**
 * 报告 Composable — 报告列表、标签筛选、日期排序
 *
 * 管理报告列表加载、标签筛选、日期排序。
 * 对应 index.original.html 中的 loadReportList, onReportFilterChange。
 *
 * 使用方式:
 *   const { reports, reportTagFilter, loadReportList, onReportFilterChange } = useReports()
 *   await loadReportList()
 *   onReportFilterChange('日常报告')
 */

import { ref, computed, readonly, type InjectionKey, type Ref, type ComputedRef } from 'vue';
import type { ReportItem } from '@/types';
import { apiGet } from '@/api/client';

// ==================== 类型定义 ====================

/** 报告列表 API 响应 (内部) */
interface ReportListApiResponse {
  reports: ReportItem[];
}

/** useReports 返回值 */
export interface UseReportsReturn {
  /** 报告列表 */
  reports: Ref<ReportItem[]>;
  /** 当前标签筛选 */
  reportTagFilter: Ref<string>;
  /** 筛选后的报告列表 (computed) */
  filteredReports: ComputedRef<ReportItem[]>;
  /** 报告总数 (筛选后) */
  reportCount: ComputedRef<number>;
  /** 加载中 */
  loading: Readonly<Ref<boolean>>;
  /**
   * 加载报告列表
   * 从 /api/mobile/reports 获取
   * @param filter 可选: 标签筛选 (覆盖 reportTagFilter)
   */
  loadReportList: (filter?: string) => Promise<void>;
  /**
   * 标签筛选变化处理
   * @param tag 标签值 (空字符串表示全部)
   */
  onReportFilterChange: (tag: string) => void;
}

/** useReports 注入 key */
export const USE_REPORTS_KEY: InjectionKey<UseReportsReturn> =
  Symbol('useReports');

// ==================== Composable ====================

/**
 * 报告 Composable — 报告列表、标签筛选、日期排序
 *
 * 管理报告列表的加载和筛选。
 * 支持通过 API 加载报告, 标签筛选, 日期降序排序。
 */
export function useReports(): UseReportsReturn {
  const reports = ref<ReportItem[]>([]);
  const reportTagFilter = ref<string>('');
  const loading = ref(false);

  /**
   * 筛选后的报告列表
   *
   * 按标签筛选, 并按日期降序排序。
   */
  const filteredReports = computed<ReportItem[]>(() => {
    let list = reports.value;

    // 标签筛选
    if (reportTagFilter.value) {
      list = list.filter((r) => {
        return (
          r.tags &&
          r.tags.some((tag) => tag === reportTagFilter.value)
        );
      });
    }

    // 按日期降序排序
    return [...list].sort((a, b) => {
      return b.date.localeCompare(a.date);
    });
  });

  /** 报告总数 (筛选后) */
  const reportCount = computed<number>(() => {
    return filteredReports.value.length;
  });

  // ==================== 数据加载 ====================

  /**
   * 加载报告列表
   *
   * 调用 /api/mobile/reports 获取报告数据。
   * 如果指定 filter, 同时更新 reportTagFilter。
   *
   * @param filter 可选: 标签筛选值
   */
  async function loadReportList(filter?: string): Promise<void> {
    loading.value = true;

    if (filter !== undefined) {
      reportTagFilter.value = filter;
    }

    try {
      let url = '/api/mobile/reports';
      if (reportTagFilter.value) {
        url +=
          '?tag=' + encodeURIComponent(reportTagFilter.value);
      }

      const result = await apiGet<ReportListApiResponse>(url);

      if (result && result.reports && result.reports.length > 0) {
        reports.value = result.reports;
      } else {
        reports.value = [];
      }
    } catch (e) {
      console.error('[useReports] 加载失败:', e);
      reports.value = [];
    } finally {
      loading.value = false;
    }
  }

  /**
   * 标签筛选变化处理
   *
   * 更新筛选条件并重新加载列表。
   *
   * @param tag 标签值 (空字符串表示全部)
   */
  function onReportFilterChange(tag: string): void {
    reportTagFilter.value = tag;
    loadReportList(tag);
  }

  return {
    reports,
    reportTagFilter,
    filteredReports,
    reportCount,
    loading: readonly(loading),
    loadReportList,
    onReportFilterChange,
  };
}

// ==================== 单例 ====================

let _singleton: UseReportsReturn | null = null;

/**
 * 全局单例 useReports (跨组件共享同一个报告状态)
 */
export function useReportsSingleton(): UseReportsReturn {
  if (!_singleton) {
    _singleton = useReports();
  }
  return _singleton;
}
