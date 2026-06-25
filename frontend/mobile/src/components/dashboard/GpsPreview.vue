<template>
  <div class="gps-preview" :class="{ expanded: isExpanded }">
    <canvas ref="canvasRef" class="gps-preview-canvas"></canvas>
    <div v-if="!isExpanded" class="gps-preview-info">
      <span>{{ pointCount }} 个点</span>
      <span v-if="gpsPoints.length > 0">
        {{ formatTimeRange(gpsPoints[0]?.t, gpsPoints[gpsPoints.length - 1]?.t) }}
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * GPS Canvas 预览组件
 *
 * 在 Dashboard 卡片中展示 GPS 轨迹的 Canvas 预览
 * - 折叠状态: 100px 高度 + 点数信息
 * - 展开状态: 260px 高度 (更大预览)
 * - DPR 自适应
 * - 自动计算边界并绘制轨迹
 */

import { ref, watch, computed, onMounted, onUnmounted, nextTick } from 'vue';
import type { MergedGpsPoint } from '@/types/gps';

// ==================== Props ====================

const props = defineProps<{
  /** 合并后的 GPS 点数据 */
  gpsPoints: MergedGpsPoint[];
  /** 是否展开状态 */
  isExpanded: boolean;
}>();

// ==================== Refs ====================

const canvasRef = ref<HTMLCanvasElement | null>(null);
let resizeObserver: ResizeObserver | null = null;

// ==================== 计算属性 ====================

/** 点数量 */
const pointCount = computed(() => props.gpsPoints.length);

// ==================== 工具函数 ====================

/** 格式化时间范围 */
function formatTimeRange(start?: string, end?: string): string {
  if (!start || !end) return '';
  if (start === end) return start;
  return `${start} ~ ${end}`;
}

// ==================== Canvas 绘制 ====================

/** 绘制 GPS 预览 */
function drawPreview(): void {
  const canvas = canvasRef.value;
  if (!canvas) return;

  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  const pts = props.gpsPoints;
  const dpr = window.devicePixelRatio || 1;

  // 获取父容器尺寸
  const parent = canvas.parentElement;
  if (!parent) return;

  const rect = parent.getBoundingClientRect();
  const w = rect.width;
  const h = props.isExpanded ? 260 : 100;

  // 设置 canvas 实际尺寸 (考虑 DPR)
  canvas.width = w * dpr;
  canvas.height = h * dpr;
  canvas.style.width = `${w}px`;
  canvas.style.height = `${h}px`;

  // 缩放上下文以匹配 DPR
  ctx.scale(dpr, dpr);

  // 清除画布
  ctx.clearRect(0, 0, w, h);

  // 无数据时显示提示
  if (!pts || pts.length === 0) {
    ctx.fillStyle = 'rgba(255,255,255,0.15)';
    ctx.font = '12px "Plus Jakarta Sans", sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('暂无 GPS 数据', w / 2, h / 2);
    return;
  }

  // 计算边界
  let minLat = Infinity, maxLat = -Infinity;
  let minLng = Infinity, maxLng = -Infinity;

  pts.forEach(p => {
    if (p.lat < minLat) minLat = p.lat;
    if (p.lat > maxLat) maxLat = p.lat;
    if (p.lng < minLng) minLng = p.lng;
    if (p.lng > maxLng) maxLng = p.lng;
  });

  // 边界保护 (防止单点时除零)
  const latRange = maxLat - minLat || 0.01;
  const lngRange = maxLng - minLng || 0.01;

  // 内边距
  const pad = 20;
  const drawW = w - pad * 2;
  const drawH = h - pad * 2;

  // 坐标转换函数
  const toX = (lng: number) => pad + ((lng - minLng) / lngRange) * drawW;
  const toY = (lat: number) => pad + drawH - ((lat - minLat) / latRange) * drawH;

  // 绘制轨迹线
  ctx.beginPath();
  ctx.strokeStyle = 'rgba(162, 155, 254, 0.6)';
  ctx.lineWidth = 1.5;
  ctx.lineJoin = 'round';

  pts.forEach((p, i) => {
    const x = toX(p.lng);
    const y = toY(p.lat);
    if (i === 0) {
      ctx.moveTo(x, y);
    } else {
      ctx.lineTo(x, y);
    }
  });
  ctx.stroke();

  // 绘制点
  const dotColors = ['#6c5ce7', '#00cec9', '#fdcb6e', '#fd79a8', '#74b9ff', '#ff6b6b', '#a29bfe', '#55efc4'];

  pts.forEach((p, i) => {
    const x = toX(p.lng);
    const y = toY(p.lat);
    const isStart = i === 0;
    const isEnd = i === pts.length - 1;

    // 点大小根据 count 调整
    const size = (p.count ?? 1) > 5 ? 5 : (p.count ?? 1) > 2 ? 4 : 3;

    ctx.beginPath();
    ctx.arc(x, y, size, 0, Math.PI * 2);

    // 起点绿色, 终点红色, 其他点使用调色板
    if (isStart) {
      ctx.fillStyle = '#00cec9';
    } else if (isEnd) {
      ctx.fillStyle = '#ff6b6b';
    } else {
      ctx.fillStyle = dotColors[i % dotColors.length];
    }

    ctx.fill();

    // 起终点加白色描边
    if (isStart || isEnd) {
      ctx.strokeStyle = 'rgba(255,255,255,0.8)';
      ctx.lineWidth = 1;
      ctx.stroke();
    }
  });

  // 绘制方向指示 N/S
  ctx.fillStyle = 'rgba(255,255,255,0.12)';
  ctx.font = '9px "Plus Jakarta Sans", sans-serif';
  ctx.textAlign = 'left';
  ctx.fillText('N', 6, 12);
  ctx.fillText('S', 6, h - 4);
}

// ==================== 生命周期 ====================

/** 初始化 ResizeObserver */
function initResizeObserver(): void {
  const canvas = canvasRef.value;
  if (!canvas || !canvas.parentElement) return;

  resizeObserver = new ResizeObserver(() => {
    nextTick(drawPreview);
  });

  resizeObserver.observe(canvas.parentElement);
}

onMounted(() => {
  initResizeObserver();
  drawPreview();
});

onUnmounted(() => {
  if (resizeObserver) {
    resizeObserver.disconnect();
    resizeObserver = null;
  }
});

// ==================== 监听变化 ====================

watch(
  () => [props.gpsPoints, props.isExpanded],
  () => {
    nextTick(drawPreview);
  },
  { deep: true },
);
</script>

<style scoped>
.gps-preview {
  width: 100%;
  height: 100px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  transition: height 0.3s ease;
}

.gps-preview.expanded {
  height: 260px;
}

.gps-preview-canvas {
  width: 100%;
  height: 100%;
  border-radius: 8px;
  background: #0d0d1a;
}

.gps-preview-info {
  font-size: 10px;
  color: var(--text3);
  display: flex;
  justify-content: space-between;
  padding: 0 4px;
}
</style>
