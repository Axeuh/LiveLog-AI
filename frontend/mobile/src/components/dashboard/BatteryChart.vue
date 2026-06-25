<template>
  <div class="battery-chart" :class="{ expanded: isExpanded }">
    <canvas ref="canvasRef"></canvas>
  </div>
</template>

<script setup lang="ts">
/**
 * 电池电量折线图组件
 *
 * 展示电池电量数据的时间序列折线图 (带填充)
 * - 颜色: #00cec9 (accent), 填充: rgba(0,206,201,0.1)
 * - Y轴范围: 0-100%
 * - 降采样: 最多 80 个数据点
 * - 响应式布局
 */

import { ref, watch, computed } from 'vue';
import type { HealthSample } from '@/types';
import { useChart, downsample, generateTimeLabels } from '@/composables/useChart';
import type { ChartConfiguration } from 'chart.js';

// ==================== Props ====================

const props = defineProps<{
  /** 健康数据样本 */
  samples: HealthSample[];
  /** 是否展开状态 */
  isExpanded: boolean;
}>();

// ==================== Refs ====================

const canvasRef = ref<HTMLCanvasElement | null>(null);

// ==================== 数据处理 ====================

/** 提取电池电量数据 */
const batteryData = computed(() =>
  props.samples
    .map((s) => s.battery)
    .filter((v): v is number => v != null),
);

/** 生成时间标签 */
const timeLabels = computed(() =>
  generateTimeLabels(props.samples.filter((s) => s.battery != null)),
);

/** 降采样后的数据 */
const chartData = computed(() =>
  downsample(batteryData.value, timeLabels.value, 80),
);

// ==================== Chart.js 配置 ====================

function createConfig(): ChartConfiguration<'line'> {
  return {
    type: 'line',
    data: {
      labels: chartData.value.labels,
      datasets: [
        {
          label: '电量',
          data: chartData.value.data,
          borderColor: '#00cec9',
          backgroundColor: 'rgba(0,206,201,0.1)',
          fill: true,
          tension: 0.3,
          pointRadius: 0,
          borderWidth: 1.5,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
      },
      scales: {
        x: {
          ticks: {
            color: '#9898b0',
            font: { size: 10 },
            maxTicksLimit: 8,
            maxRotation: 0,
          },
          grid: { color: 'rgba(255,255,255,0.03)' },
        },
        y: {
          min: 0,
          max: 100,
          ticks: {
            color: '#9898b0',
            font: { size: 10 },
            maxTicksLimit: 8,
          },
          grid: { color: 'rgba(255,255,255,0.03)' },
        },
      },
    },
  };
}

// ==================== Chart 生命周期 ====================

const { update, destroy } = useChart(canvasRef, () => createConfig());

// ==================== 监听变化 ====================

watch(
  () => [props.samples, props.isExpanded],
  () => {
    if (batteryData.value.length > 1) {
      update();
    } else {
      destroy();
    }
  },
  { deep: true },
);
</script>

<style scoped>
.battery-chart {
  width: 100%;
  height: 120px;
  transition: height 0.3s ease;
}

.battery-chart.expanded {
  height: 200px;
}

canvas {
  width: 100% !important;
  height: 100% !important;
}
</style>
