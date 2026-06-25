<template>
  <div class="steps-chart" :class="{ expanded: isExpanded }">
    <canvas ref="canvasRef"></canvas>
  </div>
</template>

<script setup lang="ts">
/**
 * 步数柱状图组件
 *
 * 展示步数数据的柱状图
 * - 颜色: rgba(0,206,201,0.5), 圆角: 4px
 * - 响应式布局
 */

import { ref, watch, computed } from 'vue';
import type { HealthSample } from '@/types';
import { useChart, generateTimeLabels } from '@/composables/useChart';
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

/** 提取步数数据 */
const stepsData = computed(() =>
  props.samples
    .map((s) => s.steps)
    .filter((v): v is number => v != null),
);

/** 生成时间标签 */
const timeLabels = computed(() =>
  generateTimeLabels(props.samples.filter((s) => s.steps != null)),
);

// ==================== Chart.js 配置 ====================

function createConfig(): ChartConfiguration<'bar'> {
  return {
    type: 'bar',
    data: {
      labels: timeLabels.value,
      datasets: [
        {
          data: stepsData.value,
          backgroundColor: 'rgba(0,206,201,0.5)',
          borderRadius: 4,
          borderSkipped: false,
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
            color: '#5a5a78',
            font: { size: 8 },
          },
          grid: { display: false },
        },
        y: {
          ticks: {
            color: '#5a5a78',
            font: { size: 8 },
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
    if (stepsData.value.length > 1) {
      update();
    } else {
      destroy();
    }
  },
  { deep: true },
);
</script>

<style scoped>
.steps-chart {
  width: 100%;
  height: 150px;
  transition: height 0.3s ease;
}

.steps-chart.expanded {
  height: 250px;
}

canvas {
  width: 100% !important;
  height: 100% !important;
}
</style>
