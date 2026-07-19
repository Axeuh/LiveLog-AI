<template>
  <div id="page-dashboard" class="page active">
    <!-- 工具栏 -->
    <div class="dashboard-toolbar">
      <span class="live-dot"></span>
      <div class="toolbar-center">
        <div class="segmented-control">
          <button
            v-for="tab in tabs"
            :key="tab.key"
            class="seg-btn"
            :class="{ active: activeTab === tab.key }"
            @click="activeTab = tab.key"
          >
            {{ tab.label }}
          </button>
        </div>
      </div>
      <button
        class="edit-btn"
        :class="{ editing: isEditing }"
        @click="toggleEditMode"
      >
        {{ isEditing ? '完成' : '编辑' }}
      </button>
    </div>

    <!-- 编辑模式: 传感器显示/隐藏控制 -->
    <DashboardEditControls
      :is-editing="isEditing"
      :sensor-toggle-list="sensorToggleList"
      @toggle-sensor="toggleSensor"
    />

    <!-- 加载骨架屏 -->
    <SkeletonLoader v-if="loading" type="card" :count="4" />

    <!-- 主内容 -->
    <div v-else class="health-content">

      <!-- 心率卡片: SVG 环形图 -->
      <div class="health-card heart-rate-card">
        <div class="card-label">
          <i class="fas fa-heart" style="color: var(--accent2)"></i>
          心率
        </div>
        <div class="hr-ring-wrapper">
          <svg class="hr-ring" viewBox="0 0 200 200">
            <!-- 背景轨道 -->
            <circle
              cx="100"
              cy="100"
              r="80"
              fill="none"
              stroke="var(--border)"
              stroke-width="12"
            />
            <!-- 进度弧 -->
            <circle
              cx="100"
              cy="100"
              r="80"
              fill="none"
              stroke="var(--accent2)"
              stroke-width="12"
              stroke-linecap="round"
              :stroke-dasharray="hrDashArray"
              :stroke-dashoffset="hrDashOffset"
              transform="rotate(-90 100 100)"
            />
          </svg>
          <div class="hr-center">
            <span class="hr-value">{{ mockData.heartRate.current }}</span>
            <span class="hr-unit">{{ mockData.heartRate.unit }}</span>
          </div>
        </div>
        <div class="hr-stats">
          <div class="hr-stat">
            <span class="hr-stat-val">{{ mockData.heartRate.min }}</span>
            <span class="hr-stat-label">最低</span>
          </div>
          <div class="hr-stat">
            <span class="hr-stat-val">{{ mockData.heartRate.avg }}</span>
            <span class="hr-stat-label">平均</span>
          </div>
          <div class="hr-stat">
            <span class="hr-stat-val">{{ mockData.heartRate.max }}</span>
            <span class="hr-stat-label">最高</span>
          </div>
        </div>
      </div>

      <!-- 步数卡片 -->
      <div class="health-card steps-card">
        <div class="card-label">
          <i class="fas fa-shoe-prints" style="color: var(--accent)"></i>
          步数
        </div>
        <div class="steps-value-row">
          <span class="steps-current">{{ stepsFormatted }}</span>
          <span class="steps-goal">/ {{ stepsGoalFormatted }}</span>
        </div>
        <div class="steps-bar-track">
          <div class="steps-bar-fill" :style="{ width: stepsPercent + '%' }"></div>
        </div>
        <div class="steps-percent-label">{{ stepsPercent }}% 目标</div>
      </div>

      <!-- 睡眠卡片 -->
      <div class="health-card sleep-card">
        <div class="card-label">
          <i class="fas fa-moon" style="color: var(--primary)"></i>
          睡眠
          <span class="sleep-total">{{ mockData.sleep.total }}</span>
        </div>
        <div class="sleep-bar-track">
          <div
            class="sleep-segment deep"
            :style="{ width: sleepSegments.deep + '%' }"
            :title="'深睡 ' + mockData.sleep.deep"
          ></div>
          <div
            class="sleep-segment rem"
            :style="{ width: sleepSegments.rem + '%' }"
            :title="'REM ' + mockData.sleep.rem"
          ></div>
          <div
            class="sleep-segment light"
            :style="{ width: sleepSegments.light + '%' }"
            :title="'浅睡 ' + mockData.sleep.light"
          ></div>
          <div
            class="sleep-segment awake"
            :style="{ width: sleepSegments.awake + '%' }"
            :title="'清醒 ' + mockData.sleep.awake"
          ></div>
        </div>
        <div class="sleep-labels">
          <span class="sleep-label"><i class="sleep-dot deep"></i>深睡 {{ mockData.sleep.deep }}</span>
          <span class="sleep-label"><i class="sleep-dot rem"></i>REM {{ mockData.sleep.rem }}</span>
          <span class="sleep-label"><i class="sleep-dot light"></i>浅睡 {{ mockData.sleep.light }}</span>
          <span class="sleep-label"><i class="sleep-dot awake"></i>清醒 {{ mockData.sleep.awake }}</span>
        </div>
      </div>

      <!-- 小指标网格 -->
      <div class="metrics-grid">
        <!-- 血氧 -->
        <div class="health-card metric-card">
          <div class="card-label">
            <span class="spo2-badge">O2</span>
            血氧
          </div>
          <span class="metric-value" style="color: var(--primary)">{{ mockData.bloodOxygen.current }}<span class="metric-unit">%</span></span>
        </div>

        <!-- 压力 -->
        <div class="health-card metric-card">
          <div class="card-label">
            <i class="fas fa-brain" style="color: var(--accent3)"></i>
            压力
          </div>
          <span class="metric-value" style="color: var(--accent3)">{{ mockData.stress.current }}<span class="metric-unit">/100</span></span>
        </div>

        <!-- 电量 -->
        <div class="health-card metric-card">
          <div class="card-label">
            <i class="fas fa-battery-three-quarters" style="color: var(--accent)"></i>
            电量
          </div>
          <span class="metric-value" style="color: var(--accent)">{{ mockData.battery.current }}<span class="metric-unit">%</span></span>
        </div>
      </div>

      <!-- GPS 行 -->
      <div class="gps-row">
        <span class="gps-info">
          <i class="fas fa-location-dot"></i>
          GPS 轨迹 ({{ gpsFormatted }} 条)
        </span>
        <button class="gps-map-btn" @click="openGpsMap">
          <i class="fas fa-map"></i>
          查看地图
        </button>
      </div>
    </div>

    <!-- GPS 全屏地图覆盖层 -->
    <GpsMapOverlay
      :visible="gpsMapVisible"
      :gps-points="gpsPointsForMap"
      @close="gpsMapVisible = false"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import SkeletonLoader from '@/components/common/SkeletonLoader.vue'
import GpsMapOverlay from '@/components/dashboard/GpsMapOverlay.vue'
import DashboardEditControls from '@/components/dashboard/DashboardEditControls.vue'
// DashboardChart.vue 保留用于未来展开详情视图, 当前未使用
import { useDashboardSingleton, MOCK_HEALTH_DATA } from '@/composables/useDashboard'
import { useGpsSingleton } from '@/composables/useGps'
import type { MergedGpsPoint } from '@/types/gps'

// ==================== Composables ====================

const dashboard = useDashboardSingleton()
const gps = useGpsSingleton()

// ==================== 真实数据转换 ====================

/**
 * 将 API DashboardResponse 转换为组件模板使用的扁平结构
 * 无数据时用 MOCK_HEALTH_DATA 降级显示
 */
const mockData = computed(() => {
  const dash = dashboard.cachedDashData.value
  if (!dash?.health) return MOCK_HEALTH_DATA

  const h = dash.health
  const p = dash.perception

  // 取电池时间线最新值
  let batteryLevel = 0
  if (p?.battery_timeline && p.battery_timeline.length > 0) {
    batteryLevel = p.battery_timeline[p.battery_timeline.length - 1].level
  }

  return {
    heartRate: {
      current: h.heart_rate?.avg || 0,
      unit: 'bpm',
      min: h.heart_rate?.min || 0,
      max: h.heart_rate?.max || 0,
      avg: h.heart_rate?.avg || 0,
    },
    steps: {
      current: h.steps || 0,
      goal: 10000,
      unit: '步',
    },
    sleep: {
      total: dashboard.fmtDuration(h.sleep?.duration_min ?? null),
      deep: dashboard.fmtDuration(h.sleep?.deep_min ?? null),
      rem: dashboard.fmtDuration(h.sleep?.rem_min ?? null),
      light: dashboard.fmtDuration(h.sleep?.light_min ?? null),
      awake: dashboard.fmtDuration(h.sleep?.awake_min ?? null),
    },
    bloodOxygen: {
      current: h.spo2?.avg || 0,
      unit: '%',
      min: h.spo2?.min || 0,
      max: h.spo2?.max || 0,
    },
    stress: {
      current: h.stress?.avg || 0,
      unit: '/100',
    },
    battery: {
      current: batteryLevel,
      unit: '%',
    },
    gps: {
      points: p?.gps_records || 0,
    },
  }
})

// ==================== 分段控制 ====================

const tabs = [
  { key: 'today', label: '今日' },
  { key: 'week', label: '本周' },
  { key: 'month', label: '本月' },
]
const activeTab = ref('today')

// ==================== 心率环形图计算 ====================

/** 环形周长 */
const HR_CIRCUMFERENCE = 2 * Math.PI * 80 // r=80

/** 心率百分比 (基于 max 200 bpm) */
const hrPercent = computed(() => Math.min(mockData.value.heartRate.current / 200, 1))

/** stroke-dasharray: 周长 */
const hrDashArray = computed(() => HR_CIRCUMFERENCE.toFixed(2))

/** stroke-dashoffset: 负值表示顺时针绘制 */
const hrDashOffset = computed(() => {
  const offset = HR_CIRCUMFERENCE * (1 - hrPercent.value)
  return offset.toFixed(2)
})

// ==================== 步数计算 ====================

const stepsFormatted = computed(() => mockData.value.steps.current.toLocaleString())
const stepsGoalFormatted = computed(() => mockData.value.steps.goal.toLocaleString())
const stepsPercent = computed(() => Math.round((mockData.value.steps.current / mockData.value.steps.goal) * 100))

// ==================== 睡眠分段计算 ====================

/** 解析 "XhYm" 格式为分钟数 */
function parseDuration(str: string): number {
  const hMatch = str.match(/(\d+)h/)
  const mMatch = str.match(/(\d+)m/)
  const h = hMatch ? parseInt(hMatch[1], 10) : 0
  const m = mMatch ? parseInt(mMatch[1], 10) : 0
  return h * 60 + m
}

const sleepSegments = computed(() => {
  const deep = parseDuration(mockData.value.sleep.deep)
  const rem = parseDuration(mockData.value.sleep.rem)
  const light = parseDuration(mockData.value.sleep.light)
  const awake = parseDuration(mockData.value.sleep.awake)
  const total = deep + rem + light + awake
  if (total === 0) return { deep: 0, rem: 0, light: 0, awake: 0 }
  return {
    deep: Math.round((deep / total) * 100),
    rem: Math.round((rem / total) * 100),
    light: Math.round((light / total) * 100),
    awake: Math.round((awake / total) * 100),
  }
})

// ==================== GPS 格式化 ====================

const gpsFormatted = computed(() => mockData.value.gps.points.toLocaleString())

// ==================== 传感器显示控制 ====================

interface SensorToggleItem {
  name: string
  label: string
  visible: boolean
}

const sensorToggleList = computed<SensorToggleItem[]>(() => [
  { name: 'health', label: '健康数据', visible: dashboard.sensorStates.health },
  { name: 'battery', label: '电量', visible: dashboard.sensorStates.battery },
  { name: 'usage', label: '使用时长', visible: dashboard.sensorStates.usage },
  { name: 'gps', label: 'GPS', visible: dashboard.sensorStates.gps },
])

function toggleSensor(name: string): void {
  dashboard.toggleSensor(name)
}

// ==================== 编辑模式 ====================

const isEditing = ref(false)

function toggleEditMode(): void {
  isEditing.value = !isEditing.value
}

// ==================== 加载状态 ====================

const loading = computed(() => dashboard.loading.value)

// ==================== GPS 地图 ====================

const gpsMapVisible = ref(false)
const gpsPointsForMap = computed(() => gps.gpsPointData.value as unknown as MergedGpsPoint[])

function openGpsMap(): void {
  const dash = document.getElementById('page-dashboard')
  if (dash) dash.scrollTop = 0
  gpsMapVisible.value = true
  if (gps.gpsPointData.value.length === 0 && dashboard.cachedDashData.value?.perception) {
    gps.loadGpsData(dashboard.dashDate.value)
  }
}

// ==================== 生命周期 ====================

onMounted(() => {
  dashboard.loadDashboardData(dashboard.dashDate.value)
  gps.loadGpsData(dashboard.dashDate.value)
})
</script>

<style scoped>
/* 页面容器 */
#page-dashboard {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  padding: 16px 20px 12px;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
}

/* 工具栏 */
.dashboard-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
}

.toolbar-center {
  display: flex;
  align-items: center;
  flex: 1;
  justify-content: center;
}

/* 实时录制指示器 */
.live-dot {
  width: 6px;
  height: 6px;
  background: var(--accent);
  border-radius: 50%;
  display: inline-block;
  animation: livePulse 1.5s infinite;
  flex-shrink: 0;
}

@keyframes livePulse {
  0%, 100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.5;
    transform: scale(1.3);
  }
}

/* 分段控制 (iOS 风格) */
.segmented-control {
  display: flex;
  background: var(--surface);
  border-radius: 10px;
  padding: 2px;
  gap: 2px;
}

.seg-btn {
  font-size: 13px;
  font-weight: 500;
  padding: 6px 16px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--text2);
  cursor: pointer;
  font-family: inherit;
  transition: all 0.2s;
}

.seg-btn.active {
  background: var(--primary);
  color: #fff;
}

.seg-btn:active {
  opacity: 0.7;
}

/* 编辑按钮 */
.edit-btn {
  font-size: 11px;
  padding: 5px 12px;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text2);
  cursor: pointer;
  font-family: inherit;
  transition: all 0.15s;
  flex-shrink: 0;
}

.edit-btn:active {
  opacity: 0.7;
}

.edit-btn.editing {
  background: var(--primary);
  color: #fff;
  border-color: var(--primary);
}

/* 主内容容器 */
.health-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* 卡片基础样式 */
.health-card {
  background: var(--surface);
  border-radius: var(--radius);
  padding: 16px;
}

/* 卡片标签 */
.card-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text2);
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 12px;
}

/* ==================== 心率卡片 ==================== */

.heart-rate-card {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.hr-ring-wrapper {
  position: relative;
  width: 160px;
  height: 160px;
  margin-bottom: 16px;
}

.hr-ring {
  width: 100%;
  height: 100%;
}

.hr-center {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  flex-direction: column;
  align-items: center;
}

.hr-value {
  font-size: 42px;
  font-weight: 700;
  color: var(--text);
  line-height: 1;
}

.hr-unit {
  font-size: 14px;
  color: var(--text2);
  margin-top: 4px;
}

.hr-stats {
  display: flex;
  gap: 32px;
}

.hr-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.hr-stat-val {
  font-size: 18px;
  font-weight: 600;
  color: var(--text);
}

.hr-stat-label {
  font-size: 11px;
  color: var(--text3);
  margin-top: 2px;
}

/* ==================== 步数卡片 ==================== */

.steps-value-row {
  display: flex;
  align-items: baseline;
  gap: 4px;
  margin-bottom: 12px;
}

.steps-current {
  font-size: 28px;
  font-weight: 700;
  color: var(--text);
}

.steps-goal {
  font-size: 14px;
  color: var(--text3);
}

.steps-bar-track {
  width: 100%;
  height: 8px;
  background: var(--surface2);
  border-radius: 4px;
  overflow: hidden;
}

.steps-bar-fill {
  height: 100%;
  background: var(--accent);
  border-radius: 4px;
  transition: width 0.6s ease;
}

.steps-percent-label {
  font-size: 11px;
  color: var(--text3);
  margin-top: 6px;
  text-align: right;
}

/* ==================== 睡眠卡片 ==================== */

.sleep-total {
  margin-left: auto;
  font-size: 16px;
  font-weight: 700;
  color: var(--text);
}

.sleep-bar-track {
  display: flex;
  width: 100%;
  height: 10px;
  border-radius: 5px;
  overflow: hidden;
  gap: 2px;
  margin-bottom: 10px;
}

.sleep-segment {
  height: 100%;
  transition: width 0.4s ease;
}

.sleep-segment.deep {
  background: #5e5ce6;
  border-radius: 5px 0 0 5px;
}

.sleep-segment.rem {
  background: #bf5af2;
}

.sleep-segment.light {
  background: #64d2ff;
}

.sleep-segment.awake {
  background: var(--accent3);
  border-radius: 0 5px 5px 0;
}

.sleep-labels {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
}

.sleep-label {
  font-size: 11px;
  color: var(--text2);
  display: flex;
  align-items: center;
  gap: 4px;
}

.sleep-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}

.sleep-dot.deep {
  background: #5e5ce6;
}

.sleep-dot.rem {
  background: #bf5af2;
}

.sleep-dot.light {
  background: #64d2ff;
}

.sleep-dot.awake {
  background: var(--accent3);
}

/* ==================== 小指标网格 ==================== */

.metrics-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.metric-card {
  display: flex;
  flex-direction: column;
}

.metric-value {
  font-size: 24px;
  font-weight: 700;
  color: var(--text);
  margin-top: auto;
}

.metric-unit {
  font-size: 14px;
  font-weight: 500;
  color: var(--text3);
  margin-left: 2px;
}

/* 血氧 O2 徽章 */
.spo2-badge {
  font-size: 10px;
  font-weight: 800;
  background: var(--primary);
  color: #fff;
  padding: 1px 4px;
  border-radius: 3px;
  line-height: 1;
}

/* ==================== GPS 行 ==================== */

.gps-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--surface);
  border-radius: var(--radius);
  padding: 12px 16px;
}

.gps-info {
  font-size: 13px;
  color: var(--text2);
  display: flex;
  align-items: center;
  gap: 6px;
}

.gps-info i {
  color: var(--accent);
}

.gps-map-btn {
  font-size: 12px;
  padding: 6px 12px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--surface2);
  color: var(--primary);
  cursor: pointer;
  font-family: inherit;
  display: flex;
  align-items: center;
  gap: 4px;
  transition: all 0.15s;
}

.gps-map-btn:active {
  background: var(--primary);
  color: #fff;
}

/* ==================== PC 响应式 ==================== */

@media (min-width: 768px) {
  .health-content {
    max-width: 600px;
    margin: 0 auto;
  }

  .metrics-grid {
    grid-template-columns: repeat(3, 1fr);
  }
}
</style>
