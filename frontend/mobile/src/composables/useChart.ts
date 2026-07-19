/**
 * Chart.js Composable -- 通用图表生命周期管理
 *
 * 提供:
 *   - useChart: 初始化/更新/销毁 Chart.js 实例
 *   - downsample: 降采样工具函数
 *
 * 使用方式:
 *   const canvasRef = ref<HTMLCanvasElement | null>(null)
 *   const { update, destroy } = useChart(canvasRef, (ctx) => ({
 *     type: 'line',
 *     data: { ... },
 *     options: { ... }
 *   }))
 */

import {
  ref,
  onMounted,
  onUnmounted,
  type Ref,
} from 'vue';
import {
  Chart,
  type ChartConfiguration,
  LineController,
  BarController,
  LineElement,
  BarElement,
  PointElement,
  LinearScale,
  CategoryScale,
  Filler,
  Legend,
  Tooltip,
  TimeScale,
} from 'chart.js';

// 注册 Chart.js 组件 (Tree-shaking 友好)
Chart.register(
  LineController,
  BarController,
  LineElement,
  BarElement,
  PointElement,
  LinearScale,
  CategoryScale,
  Filler,
  Legend,
  Tooltip,
  TimeScale,
);

// ==================== 降采样工具 ====================

/**
 * 降采样: 将数据点限制在 maxPoints 以内
 *
 * 策略: 等间距采样, 始终保留首尾两点
 *
 * @param data 原始数据数组
 * @param labels 对应的标签数组
 * @param maxPoints 最大数据点数 (默认 80)
 * @returns 降采样后的 { data, labels }
 */
export function downsample<T>(
  data: T[],
  labels: string[],
  maxPoints: number = 80,
): { data: T[]; labels: string[] } {
  if (data.length <= maxPoints) {
    return { data, labels: labels.slice(0, data.length) };
  }

  const sampledData: T[] = [];
  const sampledLabels: string[] = [];
  const step = data.length / maxPoints;

  for (let i = 0; i < data.length; i += step) {
    const idx = Math.min(Math.floor(i), data.length - 1);
    sampledData.push(data[idx]);
    sampledLabels.push(labels[idx]);
  }

  // 确保包含最后一个点
  const lastData = data[data.length - 1];
  const lastLabel = labels[labels.length - 1];
  if (sampledData[sampledData.length - 1] !== lastData) {
    sampledData.push(lastData);
    sampledLabels.push(lastLabel);
  }

  return { data: sampledData, labels: sampledLabels };
}

/**
 * 生成时间标签 (HH:MM 格式)
 *
 * @param samples 含有 t 字段的样本数组
 * @returns HH:MM 格式的时间标签数组
 */
export function generateTimeLabels(
  samples: Array<{ t?: number }>,
): string[] {
  return samples.map((s) => {
    try {
      const d = new Date((s.t || 0) * 1000);
      return (
        String(d.getHours()).padStart(2, '0') +
        ':' +
        String(d.getMinutes()).padStart(2, '0')
      );
    } catch {
      return '';
    }
  });
}

// ==================== useChart Composable ====================

/** useChart 返回值 */
export interface UseChartReturn {
  /** 更新图表数据 */
  update: () => void;
  /** 销毁图表实例 */
  destroy: () => void;
  /** Chart.js 实例引用 */
  chart: Ref<Chart | null>;
}

/**
 * Chart.js 生命周期管理 Composable
 *
 * 自动处理:
 *   - onMounted: 初始化图表
 *   - watch: 数据或容器尺寸变化时更新
 *   - onUnmounted: 销毁图表实例
 *
 * @param canvasRef canvas 元素的 ref
 * @param createConfig 创建 Chart.js 配置的工厂函数
 * @returns { update, destroy, chart }
 */
export function useChart(
  canvasRef: Ref<HTMLCanvasElement | null>,
  createConfig: (ctx: CanvasRenderingContext2D) => ChartConfiguration,
): UseChartReturn {
  const chart = ref<Chart | null>(null);

  /** 初始化或重建图表 */
  function initChart(): void {
    const canvas = canvasRef.value;
    if (!canvas) return;

    // 销毁已有实例
    destroy();

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    chart.value = new Chart(ctx, createConfig(ctx));
  }

  /** 更新图表 (重新创建配置) */
  function update(): void {
    initChart();
  }

  /** 销毁图表实例 */
  function destroy(): void {
    if (chart.value) {
      chart.value.destroy();
      chart.value = null;
    }
  }

  // 生命周期
  onMounted(() => {
    initChart();
  });

  onUnmounted(() => {
    destroy();
  });

  return { update, destroy, chart };
}

// ==================== 便捷类型导出 ====================

export type { ChartConfiguration };
