<template>
  <div class="sleep-chart" :class="{ expanded: isExpanded }">
    <div v-if="!isExpanded" class="sleep-bars">
      <div
        v-for="item in stageTotals"
        :key="item.type"
        class="sleep-bar-row"
      >
        <span class="sleep-bar-label" :style="{ color: item.color }">
          {{ item.label }}
        </span>
        <div class="sleep-bar-track">
          <div
            class="sleep-bar-fill"
            :style="{
              width: totalMinutes > 0 ? (item.minutes / totalMinutes) * 100 + '%' : '0%',
              background: item.color,
            }"
          ></div>
        </div>
        <span class="sleep-bar-value">{{ item.minutes }}分</span>
      </div>
    </div>
    <div v-else class="sleep-canvas-wrap">
      <canvas ref="canvasRef"></canvas>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue';
import type { SleepData, SleepStageType, SleepStage } from '@/types';
import { SLEEP_STAGE_COLORS, SLEEP_STAGE_LABELS, SLEEP_STAGE_ORDER } from '@/types';

const props = defineProps<{
  sleepData: SleepData;
  isExpanded: boolean;
}>();

const canvasRef = ref<HTMLCanvasElement | null>(null);

function parseTime(t: string): number {
  const [h, m] = t.split(':').map(Number);
  return h * 60 + m;
}

function formatTime(totalMin: number): string {
  const mins = ((totalMin % 1440) + 1440) % 1440;
  const hh = Math.floor(mins / 60).toString().padStart(2, '0');
  const mm = Math.floor(mins % 60).toString().padStart(2, '0');
  return `${hh}:${mm}`;
}

interface StageTotal {
  type: SleepStageType;
  label: string;
  color: string;
  minutes: number;
}

const stageMinutesMap = computed(() => {
  const map: Record<SleepStageType, number> = {
    deep: 0, light: 0, rem: 0, awake: 0,
  };
  const { stages, deep_min, light_min, rem_min, awake_min } = props.sleepData;
  if (stages && stages.length > 0) {
    for (let i = 0; i < stages.length; i++) {
      const stage = stages[i];
      let duration = 30;
      if (i < stages.length - 1) {
        const t1 = parseTime(stage.t);
        const t2 = parseTime(stages[i + 1].t);
        duration = t2 >= t1 ? t2 - t1 : 1440 - t1 + t2;
      }
      map[stage.type] += duration;
    }
  } else {
    if (deep_min != null) map.deep = deep_min;
    if (light_min != null) map.light = light_min;
    if (rem_min != null) map.rem = rem_min;
    if (awake_min != null) map.awake = awake_min;
  }
  return map;
});

const stageTotals = computed<StageTotal[]>(() =>
  SLEEP_STAGE_ORDER.map(type => ({
    type,
    label: SLEEP_STAGE_LABELS[type],
    color: SLEEP_STAGE_COLORS[type],
    minutes: stageMinutesMap.value[type],
  }))
);

const totalMinutes = computed(() =>
  stageTotals.value.reduce((s, t) => s + t.minutes, 0)
);

interface ComputedStage extends SleepStage {
  duration_min: number;
}

const displayStages = computed<ComputedStage[]>(() => {
  const stages = props.sleepData.stages;
  if (!stages || stages.length === 0) return [];
  return stages.map((stage, i) => {
    let duration = 30;
    if (i < stages.length - 1) {
      const t1 = parseTime(stage.t);
      const t2 = parseTime(stages[i + 1].t);
      duration = t2 >= t1 ? t2 - t1 : 1440 - t1 + t2;
    }
    return { ...stage, duration_min: duration };
  });
});

function drawRoundedRect(
  ctx: CanvasRenderingContext2D,
  x: number, y: number, w: number, h: number, r: number,
): void {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + r);
  ctx.lineTo(x + w, y + h - r);
  ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  ctx.lineTo(x + r, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
}

function renderCanvas(): void {
  const canvas = canvasRef.value;
  const parent = canvas?.parentElement;
  if (!canvas || !parent) return;

  const rect = parent.getBoundingClientRect();
  const w = rect.width;
  const h = rect.height;
  const dpr = window.devicePixelRatio || 1;

  canvas.width = w * dpr;
  canvas.height = h * dpr;
  canvas.style.width = `${w}px`;
  canvas.style.height = `${h}px`;

  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  ctx.scale(dpr, dpr);

  const stages = displayStages.value;
  if (stages.length === 0) return;

  const padTop = 8;
  const padBottom = 44;
  const bandY = padTop;
  const bandH = h - padTop - padBottom;
  const bandW = w;
  const totalDur = stages.reduce((s, st) => s + st.duration_min, 0);
  if (totalDur <= 0) return;

  ctx.clearRect(0, 0, w, h);

  ctx.save();
  drawRoundedRect(ctx, 0, bandY, bandW, bandH, 8);
  ctx.clip();

  let offsetX = 0;
  for (const stage of stages) {
    const bw = (stage.duration_min / totalDur) * bandW;
    ctx.fillStyle = SLEEP_STAGE_COLORS[stage.type];
    ctx.fillRect(offsetX, bandY, bw, bandH);

    if (bw > 36) {
      const midX = offsetX + bw / 2;
      const midY = bandY + bandH / 2;
      ctx.fillStyle = '#ffffff';
      ctx.font = 'bold 10px sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(stage.t, midX, midY - 7);
      ctx.fillText(SLEEP_STAGE_LABELS[stage.type], midX, midY + 7);
    }

    offsetX += bw;
  }

  ctx.restore();

  const startMin = parseTime(stages[0].t);
  const endMin = startMin + totalDur;

  ctx.fillStyle = '#9898b0';
  ctx.font = '9px sans-serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'top';

  for (let i = 0; i < 5; i++) {
    const t = startMin + (endMin - startMin) * (i / 4);
    ctx.fillText(formatTime(t), (bandW * i) / 4, bandY + bandH + 4);
  }

  const legendY = bandY + bandH + 22;
  const legendItems = SLEEP_STAGE_ORDER.filter(t => stageMinutesMap.value[t] > 0);
  const gap = 8;
  const dotR = 4;
  let totalLegendW = 0;

  for (const type of legendItems) {
    const text = `${SLEEP_STAGE_LABELS[type]} ${Math.round(stageMinutesMap.value[type])}分`;
    totalLegendW += dotR * 2 + 3 + ctx.measureText(text).width + gap;
  }
  totalLegendW = Math.max(0, totalLegendW - gap);

  let legendX = (w - totalLegendW) / 2;
  for (const type of legendItems) {
    const text = `${SLEEP_STAGE_LABELS[type]} ${Math.round(stageMinutesMap.value[type])}分`;
    ctx.fillStyle = SLEEP_STAGE_COLORS[type];
    ctx.beginPath();
    ctx.arc(legendX + dotR, legendY, dotR, 0, Math.PI * 2);
    ctx.fill();
    legendX += dotR * 2 + 3;
    ctx.fillStyle = '#9898b0';
    ctx.font = '9px sans-serif';
    ctx.textBaseline = 'middle';
    ctx.fillText(text, legendX, legendY);
    legendX += ctx.measureText(text).width + gap;
  }
}

let resizeObserver: ResizeObserver | null = null;

function setupCanvas(): void {
  const parent = canvasRef.value?.parentElement;
  if (!parent) return;
  renderCanvas();
  resizeObserver?.disconnect();
  resizeObserver = new ResizeObserver(() => renderCanvas());
  resizeObserver.observe(parent);
}

function teardownCanvas(): void {
  resizeObserver?.disconnect();
  resizeObserver = null;
}

watch(
  () => props.sleepData,
  () => {
    if (props.isExpanded && canvasRef.value) {
      renderCanvas();
    }
  },
  { deep: true },
);

watch(
  () => props.isExpanded,
  (expanded) => {
    teardownCanvas();
    if (expanded) {
      nextTick(() => setupCanvas());
    }
  },
);

onMounted(() => {
  if (props.isExpanded) {
    nextTick(() => setupCanvas());
  }
});

onUnmounted(() => {
  teardownCanvas();
});
</script>

<style scoped>
.sleep-chart {
  width: 100%;
  height: 150px;
  transition: height 0.3s ease;
}

.sleep-chart.expanded {
  height: 250px;
}

.sleep-bars {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 4px 14px;
}

.sleep-bar-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.sleep-bar-label {
  font-size: 11px;
  font-weight: 600;
  width: 28px;
  flex-shrink: 0;
}

.sleep-bar-track {
  flex: 1;
  height: 8px;
  border-radius: 4px;
  background: var(--surface2, rgba(255, 255, 255, 0.06));
  overflow: hidden;
}

.sleep-bar-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.4s ease;
}

.sleep-bar-value {
  font-size: 11px;
  font-weight: 600;
  color: var(--text2);
  width: 32px;
  text-align: right;
  flex-shrink: 0;
}

.sleep-canvas-wrap {
  width: 100%;
  height: 100%;
}

canvas {
  display: block;
  width: 100% !important;
  height: 100% !important;
}
</style>
