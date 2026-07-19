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
import { USE_MOCK_DATA } from '@/composables/useMockData';

/** 模拟报告数据 */
const MOCK_REPORTS: ReportItem[] = [
  {
    title: '7月16日行为报告',
    date: '2026-07-16',
    tags: ['行为', '日常'],
    type: 'daily',
    md: '# 7月16日行为报告\n\n今日行为数据总结：在教室上课、在家学习、短暂外出活动。\n\n## 主要活动\n- 上午 8:00-12:00 教室上课\n- 下午 14:00-17:30 图书馆学习\n- 晚间 19:00-21:00 在家休息',
  },
  {
    title: '第28周健康复盘',
    date: '2026-07-14',
    tags: ['健康', '运动'],
    type: 'weekly',
    md: '# 第28周健康复盘\n\n本周心率平均71bpm，步数日均7,240步，睡眠质量良好。\n\n## 健康指标\n- 平均心率: 71 bpm\n- 日均步数: 7,240 步\n- 平均睡眠: 7小时22分钟',
  },
  {
    title: '7月上旬行为模式分析',
    date: '2026-07-10',
    tags: ['行为', '分析'],
    type: 'biweekly',
    md: '# 7月上旬行为模式分析\n\n本月前10天行为模式：学习时间集中在下午和晚上。\n\n## 行为规律\n- 学习高峰: 14:00-18:00\n- 运动时间: 早晨为主\n- 社交活动: 周末增多',
  },
  {
    title: '本周学习总结',
    date: '2026-07-15',
    tags: ['学习', '进步'],
    type: 'study',
    md: '# 本周学习总结\n\n本周学习时长25小时，完成英语语法专项练习12套。\n\n## 学习成果\n- 总学习时长: 25 小时\n- 英语练习: 12 套\n- 数学复习: 8 章节',
  },
  {
    title: '社交活动记录',
    date: '2026-07-13',
    tags: ['社交'],
    type: 'social',
    md: '# 社交活动记录\n\n本周与朋友互动频繁，QQ消息量增加30%。\n\n## 社交统计\n- QQ消息量: +30%\n- 线下聚会: 2 次\n- 电话通话: 5 次',
  },
  {
    title: '睡眠质量周报',
    date: '2026-07-12',
    tags: ['健康', '睡眠'],
    type: 'health',
    md: '# 睡眠质量周报\n\n本周平均睡眠7小时22分钟，深睡占比28%。\n\n## 睡眠数据\n- 平均睡眠: 7小时22分钟\n- 深睡占比: 28%\n- 入睡时间: 23:15 平均',
  },
];

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
   * 如果 USE_MOCK_DATA 为 true 或 API 失败, 返回模拟数据。
   *
   * @param filter 可选: 标签筛选值
   */
  async function loadReportList(filter?: string): Promise<void> {
    loading.value = true;

    if (filter !== undefined) {
      reportTagFilter.value = filter;
    }

    // 模拟数据模式: 直接返回模拟数据
    if (USE_MOCK_DATA) {
      await new Promise((resolve) => setTimeout(resolve, 300)); // 模拟加载延迟
      reports.value = [...MOCK_REPORTS];
      loading.value = false;
      return;
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
      console.error('[useReports] 加载失败, 使用模拟数据:', e);
      // API 失败时回退到模拟数据
      reports.value = [...MOCK_REPORTS];
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
