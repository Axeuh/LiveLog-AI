/**
 * Dashboard Composable — 日期导航、健康数据缓存、双源加载降级
 *
 * 管理仪表盘日期导航、健康数据双源加载 (dashboard API 优先, health API 降级)、
 * 传感器可见性切换。
 *
 * 使用方式:
 *   const { dashDate, cachedDashData, loadDashboardData, navigateDate } = useDashboard()
 *   await loadDashboardData('2026-06-22')
 *   navigateDate(1)  // 下一天
 *   navigateDate(-1) // 上一天
 */

import { ref, reactive, readonly, type InjectionKey, type Ref } from 'vue';
import type { DashboardResponse, HealthQueryResponse, HealthSample } from '@/types';
import { fetchDashboard, fetchHealthQuery } from '@/api/health';

// ==================== 类型定义 ====================

/** useDashboard 返回值 */
export interface UseDashboardReturn {
  /** 当前查看的日期 (YYYY-MM-DD) */
  dashDate: Ref<string>;
  /** Dashboard API 缓存 */
  cachedDashData: Ref<DashboardResponse | null>;
  /** Health API 缓存 (用于图表) */
  cachedHealthData: Ref<HealthQueryResponse | null>;
  /** 传感器可见性状态 */
  sensorStates: Record<string, boolean>;
  /** 数据加载中 */
  loading: Readonly<Ref<boolean>>;
  /** 数据加载错误 */
  loadError: Readonly<Ref<string>>;
  /**
   * 切换日期 (正向/反向一天)
   * @param dir 1 或 -1
   */
  navigateDate: (dir: 1 | -1) => void;
  /**
   * 加载指定日期的 Dashboard 数据 (双源加载)
   *
   * 优先级:
   *   1. /api/mobile/dashboard (聚合数据)
   *   2. /api/health/query (降级, 原始健康数据)
   *
   * @param date YYYY-MM-DD 格式日期
   */
  loadDashboardData: (date: string) => Promise<void>;
  /**
   * 切换传感器可见性
   * @param name 传感器名称
   */
  toggleSensor: (name: string) => void;
  /**
   * 获取最新样本
   * @param samples 健康样本数组
   * @returns 最新样本 (时间戳最大的)
   */
  latestSample: (samples: HealthSample[] | undefined | null) => Partial<HealthSample>;
  /**
   * 格式化分钟数为 "XhYm"
   * @param min 分钟数
   * @returns 格式化字符串
   */
  fmtDuration: (min: number | null | undefined) => string;
}

/** useDashboard 注入 key */
export const USE_DASHBOARD_KEY: InjectionKey<UseDashboardReturn> =
  Symbol('useDashboard');

// ==================== 工具函数 (纯) ====================

/**
 * 格式化分钟数为 "XhYm"
 *
 * 示例:
 *   fmtDuration(458) -> "7h38m"
 *   fmtDuration(45)  -> "45m"
 *   fmtDuration(null) -> ""
 */
function fmtDuration(min: number | null | undefined): string {
  if (min == null || isNaN(min)) return '';
  const h = Math.floor(min / 60);
  const m = Math.round(min % 60);
  return h > 0 ? h + 'h' + m + 'm' : m + 'm';
}

/**
 * 获取最新样本 (时间戳最大)
 *
 * @param samples 健康样本数组
 * @returns 最新样本, 无数据时返回空对象
 */
function latestSample(
  samples: HealthSample[] | undefined | null,
): Partial<HealthSample> {
  if (!samples || samples.length === 0) return {};
  return samples.reduce((a, b) => ((a.t || 0) > (b.t || 0) ? a : b));
}

// ==================== Composable ====================

/**
 * Dashboard Composable — 日期导航、健康数据缓存、双源加载降级
 *
 * 管理仪表盘的数据加载和状态。采用双源加载:
 *   1. 优先调用 /api/mobile/dashboard 获取聚合数据
 *   2. 失败时降级到 /api/health/query 获取原始样本数据
 *   3. 始终从 health API 补充图表数据
 */
export function useDashboard(): UseDashboardReturn {
  /** 当前日期 (YYYY-MM-DD) */
  const dashDate = ref<string>(
    new Date().toISOString().slice(0, 10),
  );
  /** Dashboard API 聚合数据缓存 */
  const cachedDashData = ref<DashboardResponse | null>(null);
  /** Health API 原始数据缓存 (供图表使用) */
  const cachedHealthData = ref<HealthQueryResponse | null>(null);
  /** 加载中 */
  const loading = ref(false);
  /** 加载错误 */
  const loadError = ref('');

  /** 传感器可见性状态 */
  const sensorStates = reactive<Record<string, boolean>>({
    audio: true,
    app: true,
    notify: true,
    health: true,
    usage: true,
    gps: true,
    battery: true,
  });

  // ==================== 日期导航 ====================

  /**
   * 切换日期
   *
   * @param dir 1: 下一天, -1: 上一天
   */
  function navigateDate(dir: 1 | -1): void {
    const d = new Date(dashDate.value + 'T12:00:00');
    d.setDate(d.getDate() + dir);
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    dashDate.value = y + '-' + m + '-' + day;
    loadDashboardData(dashDate.value);
  }

  // ==================== 数据加载 ====================

  /**
   * 加载指定日期的 Dashboard 数据
   *
   * 双源加载策略:
   *   1. 先尝试 /api/mobile/dashboard (聚合)
   *   2. 如果失败, 降级到 /api/health/query (原始样本)
   *   3. 始终再从 health API 获取图表数据
   *
   * @param date YYYY-MM-DD 格式日期
   */
  async function loadDashboardData(date: string): Promise<void> {
    loading.value = true;
    loadError.value = '';

    try {
      // 尝试 Dashboard API (聚合数据)
      const dashResult = await fetchDashboard(date);
      if (dashResult && (dashResult.health || dashResult.perception)) {
        cachedDashData.value = dashResult;
      } else {
        // 降级: 使用 Health API
        const healthResult = await fetchHealthQuery(date);
        if (healthResult && (healthResult.status === 'ok' || healthResult.samples || healthResult.daily_summary)) {
          cachedHealthData.value = healthResult;
          cachedDashData.value = null;
        } else {
          loadError.value = date + ' 无可用数据';
          cachedDashData.value = null;
          cachedHealthData.value = null;
        }
      }

      // 始终从 Health API 补充图表数据
      try {
        const healthResult = await fetchHealthQuery(date);
        if (healthResult && healthResult.samples && healthResult.samples.length > 0) {
          cachedHealthData.value = healthResult;
        }
      } catch {
        // 图表数据获取失败, 使用已有数据
      }
    } catch (e) {
      console.error('[useDashboard] 加载失败:', e);
      loadError.value = '网络请求失败: ' + String(e);
    } finally {
      loading.value = false;
    }
  }

  // ==================== 传感器控制 ====================

  /**
   * 切换传感器可见性
   *
   * @param name 传感器名称 (audio/app/notify/health/usage/gps/battery)
   */
  function toggleSensor(name: string): void {
    if (name in sensorStates) {
      sensorStates[name] = !sensorStates[name];
    }
  }

  return {
    dashDate,
    cachedDashData,
    cachedHealthData,
    sensorStates,
    loading: readonly(loading),
    loadError: readonly(loadError),
    navigateDate,
    loadDashboardData,
    toggleSensor,
    latestSample,
    fmtDuration,
  };
}

// ==================== 单例 ====================

let _singleton: UseDashboardReturn | null = null;

/**
 * 全局单例 useDashboard (跨组件共享同一个数据状态)
 */
export function useDashboardSingleton(): UseDashboardReturn {
  if (!_singleton) {
    _singleton = useDashboard();
  }
  return _singleton;
}
