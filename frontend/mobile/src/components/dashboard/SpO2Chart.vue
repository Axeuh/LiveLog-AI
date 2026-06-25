<template>
  <div class="spo2-chart" :class="{ expanded: isExpanded }">
    <canvas ref="canvasRef"></canvas>
  </div>
</template>

<script setup lang="ts">
/**
 * 血氧折线图组件
 *
 * 展示血氧饱和度数据的时间序列折线图
 * - 颜色: #a29bfe (primary-light), 填充: rgba(162,155,254,0.08)
 * - Y轴范围: 自动
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

/** 提取血氧数据 */
const spo2Data = computed(() =>
  props.samples
    .map((s) => s.spo2)
    .filter((v): v is number => v != null),
);

/** 生成时间标签 */
const timeLabels = computed(() =>
  generateTimeLabels(props.samples.filter((s) => s.spo2 != null)),
);

/** 降采样后的数据 */
const chartData = computed(() =>
  downsample(spo2Data.value, timeLabels.value, 80),
);

// ==================== Chart.js 配置 ====================

function createConfig(): ChartConfiguration<'line'> {
  return {
    type: 'line',
    data: {
      labels: chartData.value.labels,
      datasets: [
        {
          label: '血氧',
          data: chartData.value.data,
          borderColor: '#a29bfe',
          backgroundColor: 'rgba(162,155,254,0.08)',
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
    if (spo2Data.value.length > 1) {
      update();
    } else {
      destroy();
    }
  },
  { deep: true },
);
</script>

<style scoped>
.spo2-chart {
  width: 100%;
  height: 120px;
  transition: height 0.3s ease;
}

.spo2-chart.expanded {
  height: 200px;
}

canvas {
  width: 100% !important;
  height: 100% !important;
}
</style>
