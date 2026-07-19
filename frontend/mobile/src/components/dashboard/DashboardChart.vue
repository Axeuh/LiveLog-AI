<template>
  <div ref="chartWrapperRef" class="dashboard-chart-wrapper" :class="{ 'sleep-mode': blockId === 'sleep' && sleepStages?.length }">
    <!-- Sleep Gantt view (per-stage rows) -->
    <div v-if="blockId === 'sleep' && sleepStages?.length" class="sleep-timeline-new">
      <!-- Legend -->
      <div class="sleep-legend">
        <span
          v-for="st in stageTypesWithData"
          :key="st"
          class="sleep-legend__item"
        >
          <span class="sleep-legend__dot" :style="{ background: STAGE_COLORS[st] }"></span>
          {{ STAGE_LABELS[st] }}
        </span>
      </div>
      <!-- Gantt rows -->
      <div class="sleep-timeline-new__chart">
        <div v-for="st in stageTypesWithData" :key="st" class="sleep-timeline-new__row">
          <div class="sleep-timeline-new__label">{{ STAGE_LABELS[st] }}</div>
          <div class="sleep-timeline-new__track">
            <div
              v-for="(seg, i) in getStageSegments(st)"
              :key="i"
              class="sleep-timeline-new__seg"
              :style="{
                left: seg.leftPct + '%',
                width: seg.widthPct + '%',
                background: STAGE_COLORS[st],
              }"
            ></div>
          </div>
        </div>
      </div>
      <!-- Time labels -->
      <div class="sleep-timeline-new__time">
        <span>{{ firstTimeLabel }}</span>
        <span>{{ lastTimeLabel }}</span>
      </div>
      <!-- Sleep structure stats -->
      <div v-if="stageStats.length > 0 || fallbackStats.length > 0" class="sleep-stats">
        <div class="sleep-stats__title">睡眠结构</div>
        <template v-if="stageStats.length > 0">
          <div
            v-for="stat in stageStats"
            :key="stat.type"
            class="sleep-stats__row"
          >
            <span class="sleep-stats__dot" :style="{ background: STAGE_COLORS[stat.type] }"></span>
            <span class="sleep-stats__label">{{ stat.label }}</span>
            <span class="sleep-stats__duration">{{ stat.durationText }}</span>
            <div class="sleep-stats__bar-wrap">
              <div
                class="sleep-stats__bar"
                :style="{ width: Math.max(stat.pct, 2) + '%', background: STAGE_COLORS[stat.type] }"
              ></div>
            </div>
            <span class="sleep-stats__pct">{{ stat.pct }}%</span>
          </div>
        </template>
        <template v-else>
          <div
            v-for="stat in fallbackStats"
            :key="stat.label"
            class="sleep-stats__row"
          >
            <span class="sleep-stats__dot" :style="{ background: stat.color }"></span>
            <span class="sleep-stats__label">{{ stat.label }}</span>
            <span class="sleep-stats__duration">{{ stat.durationText }}</span>
            <div class="sleep-stats__bar-wrap">
              <div
                class="sleep-stats__bar"
                :style="{ width: Math.max(stat.pct, 2) + '%', background: stat.color }"
              ></div>
            </div>
            <span class="sleep-stats__pct">{{ stat.pct }}%</span>
          </div>
        </template>
      </div>
    </div>

    <!-- GPS preview canvas -->
    <div v-else-if="blockId === 'gps' && gpsPoints?.length" class="gps-preview">
      <canvas ref="gpsCanvasRef" class="gps-preview-canvas"></canvas>
    </div>

    <!-- Other chart types (including HR with normal width) -->
    <canvas v-else v-show="showCanvas" ref="canvasRef"></canvas>

    <!-- No data fallback text -->
    <span v-if="noData" class="no-data">{{ textFallback }}</span>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useChart } from '@/composables/useChart'
import type { ChartConfiguration } from 'chart.js'

// ==================== Types ====================

interface Sample {
  ts: string
  hr?: number
  steps?: number
  spo2?: number
  stress?: number
  battery?: number
}

interface BatteryPoint {
  t: string
  level: number
}

interface SleepBreakdown {
  duration_min?: number
  deep_min?: number
  light_min?: number
  rem_min?: number
  awake_min?: number
}

interface SleepStage {
  t: string
  type: string
}

// ==================== Constants ====================

const STAGE_TYPES = ['awake', 'rem', 'deep', 'light'] as const

const STAGE_COLORS: Record<string, string> = {
  deep: '#3366CC',
  light: '#5B9BD5',
  rem: '#7EC8E3',
  awake: '#fd79a8',
}

const STAGE_LABELS: Record<string, string> = {
  deep: '深睡',
  light: '浅睡',
  rem: '快速眼动',
  awake: '清醒',
}

// ==================== Props ====================

const props = defineProps<{
  blockId: string
  samples: Sample[]
  batteryTimeline?: BatteryPoint[]
  sleepData?: SleepBreakdown
  sleepStages?: SleepStage[]
  gpsPoints?: { lat: number; lng: number }[]
}>()

const canvasRef = ref<HTMLCanvasElement | null>(null)
const gpsCanvasRef = ref<HTMLCanvasElement | null>(null)
const chartWrapperRef = ref<HTMLDivElement | null>(null)

// ResizeObserver 用于 Canvas 自适应容器尺寸变化
let resizeObserver: ResizeObserver | null = null
let isResizing = false

// ==================== Helpers ====================

function parseTime(ts: string): string {
  if (!ts) return '00:00'
  try {
    const d = new Date(ts)
    if (isNaN(d.getTime())) return '00:00'
    const hh = String(d.getHours()).padStart(2, '0')
    const mm = String(d.getMinutes()).padStart(2, '0')
    return `${hh}:${mm}`
  } catch {
    return '00:00'
  }
}

function fmtMin(min: number): string {
  if (min >= 60) {
    const h = Math.floor(min / 60)
    const m = min % 60
    return `${h}小时${m > 0 ? m + '分钟' : ''}`
  }
  return `${min}分钟`
}

interface DataPoint {
  label: string
  value: number
}

function extractData(): DataPoint[] {
  const { blockId } = props
  if (blockId === 'hr') {
    return props.samples
      .filter((s): s is Sample & { hr: number } => s.hr != null)
      .map(s => ({ label: parseTime(s.ts), value: s.hr }))
  }
  if (blockId === 'steps') {
    return props.samples
      .filter((s): s is Sample & { steps: number } => s.steps != null)
      .map(s => ({ label: parseTime(s.ts), value: s.steps }))
  }
  if (blockId === 'spo2') {
    return props.samples
      .filter((s): s is Sample & { spo2: number } => s.spo2 != null)
      .map(s => ({ label: parseTime(s.ts), value: s.spo2 }))
  }
  if (blockId === 'stress') {
    return props.samples
      .filter((s): s is Sample & { stress: number } => s.stress != null)
      .map(s => ({ label: parseTime(s.ts), value: s.stress }))
  }
  if (blockId === 'battery') {
    return (props.batteryTimeline || []).map(s => ({
      label: parseTime(s.t),
      value: s.level,
    }))
  }
  return []
}

const dataPoints = computed(() => extractData())

// ==================== Sleep Gantt (per-stage rows) ====================

/** Convert HH:MM string to total minutes from midnight */
function hhmmToMin(t: string): number {
  const parts = t.split(':')
  return parseInt(parts[0], 10) * 60 + parseInt(parts[1], 10)
}

/** Stage types that have at least one data point */
const stageTypesWithData = computed(() =>
  STAGE_TYPES.filter(st => props.sleepStages?.some(s => s.type === st)),
)

/**
 * 获取指定睡眠阶段的连续色块段。
 * 每个条目的色块从自己的时间点开始，延伸到下一个条目的时间点（填满间隙）。
 */
function getStageSegments(type: string): { leftPct: number; widthPct: number }[] {
  const stages = props.sleepStages
  if (!stages || stages.length === 0) return []
  const first = hhmmToMin(stages[0].t)
  const last = hhmmToMin(stages[stages.length - 1].t)
  const total = last - first || 1
  const segments: { leftPct: number; widthPct: number }[] = []
  for (let i = 0; i < stages.length; i++) {
    if (stages[i].type !== type) continue
    const start = hhmmToMin(stages[i].t)
    const endTime = i < stages.length - 1 ? hhmmToMin(stages[i + 1].t) : last + 1
    const dur = endTime - start
    if (dur <= 0) continue
    segments.push({
      leftPct: ((start - first) / total) * 100,
      widthPct: Math.max(1, (dur / total) * 100),
    })
  }
  return segments
}

const firstTimeLabel = computed(() => {
  if (!props.sleepStages?.length) return ''
  return props.sleepStages[0].t
})

const lastTimeLabel = computed(() => {
  if (!props.sleepStages?.length) return ''
  return props.sleepStages[props.sleepStages.length - 1].t
})

interface StageStat {
  type: string
  label: string
  durationMin: number
  durationText: string
  pct: number
}

const totalSleepMin = computed(() => {
  const sd = props.sleepData
  if (!sd) return 0
  return (sd.deep_min || 0) + (sd.light_min || 0) + (sd.rem_min || 0) + (sd.awake_min || 0)
})

const stageStats = computed<StageStat[]>(() => {
  const total = totalSleepMin.value
  if (!total) return []
  const sd = props.sleepData || {}
  const items: StageStat[] = []
  for (const st of STAGE_TYPES) {
    let val = 0
    if (st === 'deep') val = sd.deep_min || 0
    else if (st === 'light') val = sd.light_min || 0
    else if (st === 'rem') val = sd.rem_min || 0
    else if (st === 'awake') val = sd.awake_min || 0
    if (val > 0) {
      items.push({
        type: st,
        label: STAGE_LABELS[st],
        durationMin: val,
        durationText: fmtMin(val),
        pct: Math.round((val / total) * 100),
      })
    }
  }
  return items
})

const fallbackStats = computed(() => {
  const sd = props.sleepData
  if (!sd || stageStats.value.length > 0) return []
  const total = (sd.deep_min || 0) + (sd.light_min || 0) + (sd.rem_min || 0) + (sd.awake_min || 0)
  if (!total) return []
  const items: { label: string; color: string; durationText: string; pct: number }[] = []
  const defs: { key: keyof SleepBreakdown; label: string; color: string }[] = [
    { key: 'deep_min', label: '深睡', color: '#3366CC' },
    { key: 'light_min', label: '浅睡', color: '#5B9BD5' },
    { key: 'rem_min', label: '快速眼动', color: '#7EC8E3' },
    { key: 'awake_min', label: '清醒', color: '#fd79a8' },
  ]
  for (const d of defs) {
    const v = sd[d.key] || 0
    if (v > 0) {
      items.push({
        label: d.label,
        color: d.color,
        durationText: fmtMin(v),
        pct: Math.round((v / total) * 100),
      })
    }
  }
  return items
})

// ==================== GPS preview drawing ====================

function drawGpsPreview(canvas: HTMLCanvasElement, points: { lat: number; lng: number }[]) {
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  const rect = canvas.getBoundingClientRect()
  const dpr = window.devicePixelRatio || 1
  canvas.width = rect.width * dpr
  canvas.height = rect.height * dpr
  ctx.scale(dpr, dpr)
  const w = rect.width
  const h = rect.height

  // Dark background
  ctx.fillStyle = '#0d0d1a'
  ctx.fillRect(0, 0, w, h)

  ctx.save()
  ctx.beginPath()
  ctx.rect(0, 0, w, h)
  ctx.clip()

  if (points.length < 2) {
    if (points.length === 1) {
      ctx.fillStyle = '#7c6ff7'
      ctx.beginPath()
      ctx.arc(w / 2, h / 2, 4, 0, Math.PI * 2)
      ctx.fill()
    }
    ctx.restore()
    return
  }

  // Find bounds
  let minLat = Infinity, maxLat = -Infinity
  let minLng = Infinity, maxLng = -Infinity
  for (const p of points) {
    if (p.lat < minLat) minLat = p.lat
    if (p.lat > maxLat) maxLat = p.lat
    if (p.lng < minLng) minLng = p.lng
    if (p.lng > maxLng) maxLng = p.lng
  }

  const pad = 20
  // 最小坐标跨度, 防止静止时缩放因子过大导致线条溢出画布
  const MIN_SPREAD = 0.001
  const latR = Math.max(maxLat - minLat, MIN_SPREAD) || MIN_SPREAD
  const lngR = Math.max(maxLng - minLng, MIN_SPREAD) || MIN_SPREAD
  const scX = (w - pad * 2) / lngR
  const scY = (h - pad * 2) / latR

  // 计算像素坐标
  const pts = points.map(p => ({
    x: pad + (p.lng - minLng) * scX,
    y: h - pad - (p.lat - minLat) * scY
  }))

  // 如果所有点挤在一起 (< 60px 区域), 居中并放大到至少 60px, 保持相对位置
  const xs = pts.map(p => p.x)
  const ys = pts.map(p => p.y)
  const xR = Math.max(...xs) - Math.min(...xs)
  const yR = Math.max(...ys) - Math.min(...ys)
  const MIN_PX = 60
  if (xR < MIN_PX && yR < MIN_PX) {
    const cx = (Math.max(...xs) + Math.min(...xs)) / 2
    const cy = (Math.max(...ys) + Math.min(...ys)) / 2
    const sc = Math.max(MIN_PX / Math.max(xR, 1), MIN_PX / Math.max(yR, 1))
    for (const p of pts) {
      p.x = w / 2 + (p.x - cx) * sc
      p.y = h / 2 + (p.y - cy) * sc
    }
  }

  // Draw GPS path connecting points in time order
  ctx.strokeStyle = '#7c6ff7'
  ctx.lineWidth = 1.5
  ctx.beginPath()
  for (let i = 0; i < pts.length; i++) {
    if (i === 0) ctx.moveTo(pts[i].x, pts[i].y)
    else ctx.lineTo(pts[i].x, pts[i].y)
  }
  ctx.stroke()

  // Draw start point (green) and end point (red)
  ctx.fillStyle = '#2ecc71'
  ctx.beginPath()
  ctx.arc(pts[0].x, pts[0].y, 3, 0, Math.PI * 2)
  ctx.fill()

  ctx.fillStyle = '#e74c3c'
  ctx.beginPath()
  ctx.arc(pts[pts.length - 1].x, pts[pts.length - 1].y, 3, 0, Math.PI * 2)
  ctx.fill()
  ctx.restore()
}

function drawGps() {
  if (gpsCanvasRef.value && props.gpsPoints?.length) {
    drawGpsPreview(gpsCanvasRef.value, props.gpsPoints)
  }
}

/** 根据当前容器尺寸重新渲染 Canvas */
function redrawChart(): void {
  if (isResizing) return
  isResizing = true
  try {
    if (props.blockId === 'gps' && gpsCanvasRef.value) {
      drawGps()
    } else if (showCanvas.value) {
      update()
    }
  } finally {
    isResizing = false
  }
}

onMounted(() => {
  nextTick(drawGps)

  // 监听容器尺寸变化，自动重绘 Canvas
  if (chartWrapperRef.value) {
    resizeObserver = new ResizeObserver(() => {
      redrawChart()
    })
    resizeObserver.observe(chartWrapperRef.value)
  }
})

// 组件卸载时断开 ResizeObserver
onUnmounted(() => {
  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  }
})

watch(
  () => props.gpsPoints,
  () => nextTick(drawGps),
  { deep: true },
)

// ==================== No data / fallback text ====================

const noData = computed(() => {
  if (props.blockId === 'usage') return true
  if (props.blockId === 'gps') {
    return !props.gpsPoints || props.gpsPoints.length === 0
  }
  if (props.blockId === 'sleep' && props.sleepStages?.length) return false
  if (props.blockId === 'sleep') {
    const sd = props.sleepData
    if (!sd) return true
    return !sd.deep_min && !sd.light_min && !sd.awake_min
  }
  return dataPoints.value.length === 0
})

const textFallback = computed(() =>
  props.blockId === 'gps' ? '查看 GPS 地图' : '暂无数据',
)

// ==================== Chart.js rendering (non-sleep, non-GPS blocks) ====================

const showCanvas = computed(() => {
  if (props.blockId === 'sleep' && props.sleepStages?.length) return false
  if (props.blockId === 'usage' || props.blockId === 'gps') return false
  return !noData.value
})

function createConfig(): ChartConfiguration {
  const { blockId } = props

  // Sleep aggregate fallback (no stages data)
  if (blockId === 'sleep') {
    const sd = props.sleepData || {}
    const deep = sd.deep_min || 0
    const light = sd.light_min || 0
    const awake = sd.awake_min || 0

    return {
      type: 'bar',
      data: {
        labels: [''],
        datasets: [
          {
            label: '深睡',
            data: [deep],
            backgroundColor: '#3366CC',
            borderSkipped: false,
            borderRadius: 0,
          },
          {
            label: '浅睡',
            data: [light],
            backgroundColor: '#5B9BD5',
            borderSkipped: false,
            borderRadius: 0,
          },
          {
            label: '清醒',
            data: [awake],
            backgroundColor: '#fd79a8',
            borderSkipped: false,
            borderRadius: 0,
          },
        ],
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { stacked: true, display: false },
          y: { stacked: true, display: false },
        },
      },
    }
  }

  if (blockId === 'steps') {
    return {
      type: 'bar',
      data: {
        labels: dataPoints.value.map(p => p.label),
        datasets: [
          {
            data: dataPoints.value.map(p => p.value),
            backgroundColor: '#7c6ff7',
            borderRadius: 4,
            borderSkipped: false,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: {
            ticks: {
              color: 'rgba(255,255,255,0.4)',
              font: { size: 10 },
              maxTicksLimit: 5,
              maxRotation: 0,
            },
            grid: { color: 'rgba(255,255,255,0.05)' },
          },
          y: {
            ticks: {
              color: 'rgba(255,255,255,0.4)',
              font: { size: 10 },
              maxTicksLimit: 5,
            },
            grid: { color: 'rgba(255,255,255,0.05)' },
          },
        },
      },
    }
  }

  return {
    type: 'line',
    data: {
      labels: dataPoints.value.map(p => p.label),
      datasets: [
        {
          data: dataPoints.value.map(p => p.value),
          borderColor: '#7c6ff7',
          backgroundColor: 'rgba(124, 111, 247, 0.1)',
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
      plugins: { legend: { display: false } },
      scales: {
        x: {
          ticks: {
            color: 'rgba(255,255,255,0.4)',
            font: { size: 10 },
            maxTicksLimit: 5,
            maxRotation: 0,
          },
          grid: { color: 'rgba(255,255,255,0.05)' },
        },
        y: {
          ticks: {
            color: 'rgba(255,255,255,0.4)',
            font: { size: 10 },
            maxTicksLimit: 5,
          },
          grid: { color: 'rgba(255,255,255,0.05)' },
        },
      },
    },
  }
}

const { update, destroy } = useChart(canvasRef, () => createConfig())

watch(
  () => [props.samples, props.batteryTimeline, props.sleepData, props.sleepStages],
  () => {
    if (noData.value) {
      destroy()
    } else if (showCanvas.value) {
      update()
    }
  },
  { deep: true },
)
</script>

<style scoped>
.dashboard-chart-wrapper {
  position: relative;
  height: 120px;
  width: 100%;
}

.dashboard-chart-wrapper.sleep-mode {
  height: auto;
  min-height: 100px;
}

canvas {
  width: 100% !important;
  height: 100% !important;
}

.no-data {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: rgba(255, 255, 255, 0.4);
  font-size: 12px;
}

/* ==================== Sleep Legend (shared) ==================== */

.sleep-legend {
  display: flex;
  gap: 14px;
  margin-bottom: 10px;
  flex-wrap: wrap;
}

.sleep-legend__item {
  font-size: 11px;
  color: var(--text2);
  display: flex;
  align-items: center;
  gap: 4px;
}

.sleep-legend__dot {
  width: 8px;
  height: 8px;
  border-radius: 2px;
  flex-shrink: 0;
}

/* ==================== Sleep Gantt (per-stage rows) ==================== */

.sleep-timeline-new {
  padding: 8px 0;
}

.sleep-timeline-new__chart {
  display: flex;
  flex-direction: column;
  gap: 0;
  margin-bottom: 6px;
}

.sleep-timeline-new__row {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 20px;
}

.sleep-timeline-new__label {
  font-size: 10px;
  color: var(--text3);
  width: 36px;
  flex-shrink: 0;
  text-align: right;
}

.sleep-timeline-new__track {
  flex: 1;
  position: relative;
  height: 100%;
  background: var(--surface2);
  border-radius: 4px;
  overflow: hidden;
}

.sleep-timeline-new__seg {
  position: absolute;
  top: 2px;
  bottom: 2px;
  border-radius: 3px;
}

.sleep-timeline-new__time {
  display: flex;
  justify-content: space-between;
  font-size: 10px;
  color: var(--text3);
  padding: 0 44px;
  margin-bottom: 10px;
}

/* ==================== Sleep structure stats ==================== */

.sleep-stats {
  padding: 4px 0;
}

.sleep-stats__title {
  font-size: 12px;
  font-weight: 600;
  color: var(--text);
  margin-bottom: 8px;
}

.sleep-stats__row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.sleep-stats__label {
  font-size: 11px;
  color: var(--text2);
  display: flex;
  align-items: center;
  gap: 4px;
  min-width: 80px;
  flex-shrink: 0;
}

.sleep-stats__dot {
  width: 6px;
  height: 6px;
  border-radius: 2px;
  flex-shrink: 0;
}

.sleep-stats__duration {
  font-size: 10px;
  color: var(--text3);
  margin-left: 2px;
}

.sleep-stats__bar-wrap {
  flex: 1;
  height: 14px;
  background: var(--surface2);
  border-radius: 7px;
  position: relative;
  overflow: hidden;
}

.sleep-stats__bar {
  height: 100%;
  border-radius: 7px;
  transition: width 0.3s;
}

.sleep-stats__pct {
  font-size: 9px;
  font-weight: 600;
  color: var(--text2);
  min-width: 28px;
  text-align: right;
}

/* ==================== HR chart horizontal scroll ==================== */

.chart-scroll-x {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  width: 100%;
  height: 100%;
}

.chart-scroll-x::-webkit-scrollbar {
  height: 4px;
}

.chart-scroll-x::-webkit-scrollbar-track {
  background: transparent;
}

.chart-scroll-x::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.15);
  border-radius: 2px;
}

/* ==================== GPS preview ==================== */

.gps-preview {
  padding: 8px 0;
  width: 100%;
}

.gps-preview-canvas {
  width: 100%;
  height: 100px;
  background: #0d0d1a;
  display: block;
}
</style>
