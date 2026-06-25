<template>
  <div id="page-dashboard" class="page active">
    <!-- 工具栏 -->
    <div class="dashboard-toolbar">
      <span class="live-dot"></span>
      <div class="toolbar-center">
        <button class="edit-btn nav-arrow" @click="navigateDate(-1)" title="前一天">
          <i class="fas fa-chevron-left"></i>
        </button>
        <span class="dash-date-label">{{ dateLabel }}</span>
        <button class="edit-btn nav-arrow" @click="navigateDate(1)" title="后一天">
          <i class="fas fa-chevron-right"></i>
        </button>
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
    <div v-if="isEditing" class="edit-controls">
      <button
        v-for="item in sensorToggleList"
        :key="item.name"
        class="sensor-toggle-btn"
        :class="{ active: item.visible }"
        @click="toggleSensor(item.name)"
      >
        {{ item.label }}
      </button>
    </div>

    <!-- 加载骨架屏 -->
    <SkeletonLoader v-if="loading" type="card" :count="4" />

    <!-- 仪表盘网格 -->
    <div v-else class="dashboard-grid" :class="{ editing: isEditing }">
      <div
        v-for="(block, idx) in dashboardBlocks"
        :key="block.id"
        class="db-block"
        :class="[block.sizeClass, block.cvClass, { 'drag-over': dragOverIdx === idx }]"
        :data-sensor="block.sensor"
        :data-block-id="block.id"
        :draggable="isEditing"
        :style="{ display: dashboard.sensorStates[block.sensor] === false ? 'none' : '' }"
        @click="toggleBlockExpand(block.id)"
        @dragstart="onDragStart(idx, $event)"
        @dragover.prevent="onDragOver(idx, $event)"
        @dragenter.prevent="onDragEnter(idx)"
        @dragleave="onDragLeave(idx)"
        @drop.prevent="onDrop(idx, $event)"
        @dragend="onDragEnd"
      >
        <div class="db-header">
          <span class="db-label">
            <span v-if="isEditing" class="reorder-btn" title="拖拽排序">
              <i class="fas fa-grip-lines"></i>
            </span>
            <i :class="block.icon" :style="block.iconStyle ? { color: block.iconStyle } : {}"></i>
            {{ block.label }}
          </span>
          <div class="db-controls">
            <button class="mode-btn" title="展开" @click.stop="toggleBlockExpand(block.id)">
              <i class="fas fa-chevron-down" :class="{ rotated: expandedBlocks[block.id] }"></i>
            </button>
          </div>
        </div>
        <div class="cv-row">
          <span class="cv-main">
            {{ getBlockValue(block.id) }}
            <span class="cv-unit">{{ block.unit }}</span>
          </span>
          <span class="cv-trend flat"></span>
        </div>
        <!-- 展开区域: 图表 -->
        <div v-if="expandedBlocks[block.id]" class="db-expand">
          <DashboardChart
            :block-id="block.id"
            :samples="chartSamples"
            :battery-timeline="getBatteryTimeline()"
            :sleep-data="getSleepData()"
            :sleep-stages="sleepStages"
            :gps-points="gpsPoints"
          />
        </div>
      </div>
    </div>

    <!-- GPS 地图按钮 -->
    <button
      v-if="!loading && (gps.hasData.value || dashboard.cachedDashData.value?.perception?.gps_records > 0)"
      class="gps-map-btn"
      @click="openGpsMap"
    >
      <i class="fas fa-map-marker-alt"></i>
      查看 GPS 轨迹
    </button>

    <!-- GPS 全屏地图覆盖层 -->
    <GpsMapOverlay
      :visible="gpsMapVisible"
      :gps-points="gps.gpsPointData.value"
      @close="gpsMapVisible = false"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import SkeletonLoader from '@/components/common/SkeletonLoader.vue'
import GpsMapOverlay from '@/components/dashboard/GpsMapOverlay.vue'
import DashboardChart from '@/components/dashboard/DashboardChart.vue'
import { useDashboardSingleton } from '@/composables/useDashboard'
import { useGpsSingleton } from '@/composables/useGps'

// ==================== Composables ====================

const dashboard = useDashboardSingleton()
const gps = useGpsSingleton()

// ==================== 仪表盘区块配置 ====================

interface DashboardBlockConfig {
  id: string
  label: string
  icon: string
  iconStyle?: string
  unit: string
  sensor: string
  sizeClass: string
  cvClass: string
}

const BLOCK_ORDER_KEY = 'dash_block_order'

const allBlocks: DashboardBlockConfig[] = [
  { id: 'hr', label: '心率', icon: 'fas fa-heart', iconStyle: '#ff6b6b', unit: 'bpm', sensor: 'health', sizeClass: 'size-1', cvClass: 'cv-hr' },
  { id: 'steps', label: '步数', icon: 'fas fa-walking', unit: '步', sensor: 'health', sizeClass: 'size-1', cvClass: 'cv-steps' },
  { id: 'spo2', label: '血氧', icon: '', unit: '%', sensor: 'health', sizeClass: 'size-1', cvClass: 'cv-spo2' },
  { id: 'stress', label: '压力', icon: 'fas fa-tachometer-alt', unit: '/100', sensor: 'health', sizeClass: 'size-1', cvClass: 'cv-stress' },
  { id: 'sleep', label: '睡眠', icon: 'fas fa-moon', unit: '', sensor: 'health', sizeClass: 'size-1', cvClass: 'cv-sleep' },
  { id: 'battery', label: '电量', icon: 'fas fa-battery-three-quarters', unit: '%', sensor: 'battery', sizeClass: 'size-1', cvClass: 'cv-battery' },
  { id: 'usage', label: '使用时长', icon: 'fas fa-stopwatch', unit: 'h', sensor: 'usage', sizeClass: 'size-1', cvClass: 'cv-usage' },
  { id: 'gps', label: 'GPS', icon: 'fas fa-map-marker-alt', unit: '条', sensor: 'gps', sizeClass: 'size-1', cvClass: 'cv-gps' },
]

/** 加载已保存的排序，否则使用默认顺序 */
function loadBlockOrder(): DashboardBlockConfig[] {
  try {
    const saved = localStorage.getItem(BLOCK_ORDER_KEY)
    if (saved) {
      const order: string[] = JSON.parse(saved)
      const ordered: DashboardBlockConfig[] = []
      const map = new Map(allBlocks.map(b => [b.id, b]))
      for (const id of order) {
        const block = map.get(id)
        if (block) ordered.push(block)
      }
      // 追加未保存的新区块
      for (const block of allBlocks) {
        if (!ordered.find(b => b.id === block.id)) ordered.push(block)
      }
      return ordered
    }
  } catch { /* 忽略损坏数据 */ }
  return [...allBlocks]
}

function saveBlockOrder(): void {
  try {
    localStorage.setItem(BLOCK_ORDER_KEY, JSON.stringify(dashboardBlocks.value.map(b => b.id)))
  } catch { /* 忽略存储错误 */ }
}

const dashboardBlocks = ref<DashboardBlockConfig[]>(loadBlockOrder())

// ==================== 拖拽排序 ====================

const dragIndex = ref(-1)
const dragOverIdx = ref(-1)

function onDragStart(idx: number, e: DragEvent): void {
  dragIndex.value = idx
  if (e.dataTransfer) {
    e.dataTransfer.effectAllowed = 'move'
    e.dataTransfer.setData('text/plain', String(idx))
  }
}

function onDragOver(idx: number, e: DragEvent): void {
  if (dragIndex.value === idx || dragIndex.value < 0) return
  e.dataTransfer!.dropEffect = 'move'
  dragOverIdx.value = idx
}

function onDragEnter(idx: number): void {
  if (dragIndex.value === idx || dragIndex.value < 0) return
  dragOverIdx.value = idx
}

function onDragLeave(idx: number): void {
  if (dragOverIdx.value === idx) {
    dragOverIdx.value = -1
  }
}

function onDrop(idx: number, _e: DragEvent): void {
  if (dragIndex.value < 0 || dragIndex.value === idx) {
    dragOverIdx.value = -1
    dragIndex.value = -1
    return
  }
  const arr = [...dashboardBlocks.value]
  const [moved] = arr.splice(dragIndex.value, 1)
  arr.splice(idx, 0, moved)
  dashboardBlocks.value = arr
  saveBlockOrder()
  dragOverIdx.value = -1
  dragIndex.value = -1
}

function onDragEnd(): void {
  dragOverIdx.value = -1
  dragIndex.value = -1
}

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

// ==================== 图表数据 ====================

/** 转换时间值: 支持 Unix 秒数或 ISO 字符串 */
function toTs(t: unknown): string {
  if (typeof t === 'number' && t >= 0) return new Date(t * 1000).toISOString()
  if (typeof t === 'string') return t
  return ''
}

/** 转换健康样本: 将原始样本转为 chart samples 格式 */
const chartSamples = computed(() => {
  const raw = dashboard.cachedHealthData.value?.samples
  if (!raw || raw.length === 0) return []
  return raw.map((s) => ({
    ts: toTs(s.t),
    hr: s.hr,
    steps: s.steps,
    spo2: s.spo2,
    stress: s.stress,
    battery: s.battery,
  }))
})

function getBatteryTimeline(): { t: string; level: number }[] | undefined {
  const tl = dashboard.cachedDashData.value?.perception?.battery_timeline
  if (!tl || tl.length === 0) return undefined
  return tl.map((s) => ({
    t: toTs(s.t),
    level: s.level,
  }))
}

function getSleepData(): { deep_min?: number; light_min?: number; awake_min?: number } | undefined {
  return dashboard.cachedDashData.value?.health?.sleep
}

const sleepStages = computed(() => {
  const raw = dashboard.cachedHealthData.value?.sleep_data?.stages
  if (!raw || raw.length === 0) return []
  // API 返回 {t, stage} 格式, 组件需要 {t, type} 格式
  return raw.map((s: Record<string, unknown>) => ({
    t: String(s.t || ''),
    type: String((s as { type?: string }).type || (s as { stage?: string }).stage || ''),
  }))
})

const gpsPoints = computed(() => gps.gpsPointData.value)

// ==================== 编辑模式 ====================

const isEditing = ref(false)

function toggleEditMode(): void {
  isEditing.value = !isEditing.value
}

// ==================== 区块展开 ====================

const expandedBlocks = reactive<Record<string, boolean>>({})

function toggleBlockExpand(blockId: string): void {
  expandedBlocks[blockId] = !expandedBlocks[blockId]
}

// ==================== 区块数值 ====================

function getBlockValue(blockId: string): string {
  const data = dashboard.cachedDashData.value

  // 从 Dashboard API 聚合数据读取
  if (data) {
    const health = data.health
    const perception = data.perception

    switch (blockId) {
      case 'hr': {
        if (health?.heart_rate?.avg != null) return String(health.heart_rate.avg)
        return '--'
      }
      case 'steps': {
        if (health?.steps != null) return String(health.steps)
        return '--'
      }
      case 'spo2': {
        if (health?.spo2?.avg != null) return String(health.spo2.avg)
        return '--'
      }
      case 'stress': {
        if (health?.stress?.avg != null) return String(health.stress.avg)
        return '--'
      }
      case 'sleep': {
        if (health?.sleep?.duration_min != null) {
          return dashboard.fmtDuration(health.sleep.duration_min)
        }
        return '--'
      }
      case 'battery': {
        // 从 battery_timeline 取最后一条
        const timeline = perception?.battery_timeline
        if (timeline && timeline.length > 0) {
          const last = timeline[timeline.length - 1]
          return String(last.level)
        }
        return '--'
      }
      case 'usage': {
        // 从 Health API 降级数据获取 screen_time
        const healthData = dashboard.cachedHealthData.value
        if (healthData?.daily_summary) {
          const screenTime = healthData.daily_summary['screen_time_min']
          if (screenTime != null) {
            return (Number(screenTime) / 60).toFixed(1)
          }
        }
        return '--'
      }
      case 'gps': {
        if (perception?.gps_records != null) return String(perception.gps_records)
        return gps.gpsPointData.value.length > 0
          ? String(gps.gpsPointData.value.length)
          : '--'
      }
      default:
        return '--'
    }
  }

  // 降级: 从 Health API 原始数据读取
  const healthData = dashboard.cachedHealthData.value
  if (healthData?.samples && healthData.samples.length > 0) {
    const samples = healthData.samples
    const latest = samples[samples.length - 1]

    switch (blockId) {
      case 'hr':
        return latest.hr != null ? String(latest.hr) : '--'
      case 'steps':
        return latest.steps != null ? String(latest.steps) : '--'
      case 'spo2':
        return latest.spo2 != null ? String(latest.spo2) : '--'
      case 'stress':
        return latest.stress != null ? String(latest.stress) : '--'
      case 'battery':
        return latest.battery != null ? String(latest.battery) : '--'
      default:
        break
    }
  }

  // Sleep / Usage 降级: daily_summary
  if (healthData?.daily_summary) {
    const daily = healthData.daily_summary
    if (blockId === 'sleep') {
      const sleepMin = daily['sleep_duration_min'] ?? daily['sleep_min']
      if (sleepMin != null) return dashboard.fmtDuration(Number(sleepMin))
    }
    if (blockId === 'usage') {
      const screenTime = daily['screen_time_min']
      if (screenTime != null) return (Number(screenTime) / 60).toFixed(1)
    }
  }

  // GPS 降级: 从 gpsPointData
  if (blockId === 'gps') {
    return gps.gpsPointData.value.length > 0
      ? String(gps.gpsPointData.value.length)
      : '--'
  }

  return '--'
}

/** 获取区块展开时的数据摘要 */
function getBlockSummary(blockId: string): string {
  const data = dashboard.cachedDashData.value
  if (!data?.health) return '暂无详细数据'

  const health = data.health

  switch (blockId) {
    case 'hr': {
      const hr = health.heart_rate
      if (hr) return `今日心率: 平均 ${hr.avg || '--'} bpm, 最低 ${hr.min || '--'} bpm, 最高 ${hr.max || '--'} bpm`
      return '暂无心率数据'
    }
    case 'steps': {
      const steps = health.steps
      if (steps != null) return `今日步数: ${steps} 步`
      return '暂无步数数据'
    }
    case 'spo2': {
      const spo2 = health.spo2
      if (spo2) return `今日血氧: 平均 ${spo2.avg || '--'}%, 最低 ${spo2.min || '--'}%`
      return '暂无血氧数据'
    }
    case 'stress': {
      const stress = health.stress
      if (stress) return `今日压力: 平均 ${stress.avg || '--'}, 最低 ${stress.min || '--'}, 最高 ${stress.max || '--'}`
      return '暂无压力数据'
    }
    case 'sleep': {
      const sleep = health.sleep
      if (sleep) return `睡眠时长: ${dashboard.fmtDuration(sleep.duration_min || 0)}, 深睡 ${sleep.deep_min || '--'} min`
      return '暂无睡眠数据'
    }
    default:
      return '点击查看详情'
  }
}

// ==================== 日期导航 ====================

const dateLabel = computed(() => {
  const dateStr = dashboard.dashDate.value
  if (!dateStr) return '今天'

  const parts = dateStr.split('-')
  if (parts.length !== 3) return dateStr

  const year = parts[0]
  const month = parseInt(parts[1], 10)
  const day = parseInt(parts[2], 10)

  // 检查是否是今天
  const today = new Date()
  const todayStr =
    today.getFullYear() + '-' +
    String(today.getMonth() + 1).padStart(2, '0') + '-' +
    String(today.getDate()).padStart(2, '0')

  if (dateStr === todayStr) return '今天'

  return `${year}年${month}月${day}日`
})

function navigateDate(dir: 1 | -1): void {
  dashboard.navigateDate(dir)
  gps.loadGpsData(dashboard.dashDate.value)
}

// ==================== 加载状态 ====================

const loading = computed(() => dashboard.loading.value)

// ==================== GPS 地图 ====================

const gpsMapVisible = ref(false)

function openGpsMap(): void {
  // 先重置滚动位置, 避免 -webkit-overflow-scrolling:touch 导致 fixed 定位偏移
  const dash = document.getElementById('page-dashboard')
  if (dash) dash.scrollTop = 0
  gpsMapVisible.value = true
  // 如果 GPS point data 为空但 dashboard 有记录数, 尝试从 dashboard 感知数据加载
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
  margin-bottom: 12px;
}

.toolbar-center {
  display: flex;
  align-items: center;
  gap: 4px;
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

/* 编辑/导航按钮基础样式 */
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
}

.edit-btn:active {
  opacity: 0.7;
}

.edit-btn.editing {
  background: var(--primary);
  color: #fff;
  border-color: var(--primary);
}

/* 导航箭头 */
.nav-arrow {
  font-size: 12px;
  padding: 4px 6px;
  min-width: 28px;
  text-align: center;
}

/* 日期标签 */
.dash-date-label {
  font-size: 12px;
  color: var(--text);
  font-weight: 600;
  min-width: 80px;
  text-align: center;
}

/* 编辑模式: 传感器切换控制 */
.edit-controls {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 12px;
  padding: 8px 0;
}

.sensor-toggle-btn {
  font-size: 11px;
  padding: 4px 10px;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text3);
  cursor: pointer;
  font-family: inherit;
  transition: all 0.15s;
}

.sensor-toggle-btn.active {
  background: var(--primary);
  color: #fff;
  border-color: var(--primary);
}

.sensor-toggle-btn:active {
  opacity: 0.7;
}

/* 仪表盘网格 */
.dashboard-grid {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 0;
}

/* 区块基础 */
.db-block {
  background: var(--surface);
  border-radius: var(--radius-sm);
  cursor: pointer;
  position: relative;
  overflow: hidden;
  transition: transform 0.15s;
}

.db-block:active {
  transform: scale(0.98);
}

/* 区块头部 */
.db-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
}

.db-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text3);
  display: flex;
  align-items: center;
  gap: 5px;
}

.db-controls {
  display: flex;
  gap: 2px;
  align-items: center;
}

.db-controls button {
  -webkit-tap-highlight-color: transparent;
}

.mode-btn {
  width: 24px;
  height: 24px;
  border: none;
  background: transparent;
  color: var(--text3);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  border-radius: 4px;
  transition: background 0.15s;
}

.mode-btn:active {
  background: var(--surface2);
}

.mode-btn i {
  transition: transform 0.2s;
}

.mode-btn i.rotated {
  transform: rotate(180deg);
}

/* 区块数值行 */
.cv-row {
  padding: 0 12px 10px;
}

.cv-main {
  font-size: 20px;
  font-weight: 700;
  color: var(--text);
}

.cv-unit {
  font-size: 11px;
  font-weight: 500;
  color: var(--text3);
  margin-left: 2px;
}

.cv-trend {
  display: none;
}

/* 展开区域 - 覆盖全局 CSS 的 display:none */
.db-expand {
  display: block !important;
  padding: 0 12px 12px;
}

.block-expand-content {
  padding: 10px 12px;
  background: var(--surface2);
  border-radius: var(--radius-sm);
  color: var(--text2);
  font-size: 12px;
  line-height: 1.6;
}

/* GPS 地图按钮 */
.gps-map-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  width: 100%;
  padding: 10px;
  margin-top: 10px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text2);
  font-size: 13px;
  font-family: inherit;
  cursor: pointer;
  transition: all 0.15s;
}

.gps-map-btn:active {
  background: var(--surface2);
  color: var(--primary);
}

/* SpO2 使用特殊文字替代图标 */
.cv-spo2 .db-label::before {
  content: 'O2';
  font-size: 10px;
  font-weight: 800;
  background: var(--accent);
  color: var(--bg);
  padding: 1px 3px;
  border-radius: 3px;
  line-height: 1;
}

.cv-spo2 .db-label i {
  display: none;
}

/* 拖拽排序 */
.dashboard-grid.editing .db-block {
  cursor: grab;
}

.dashboard-grid.editing .db-block:active {
  cursor: grabbing;
}

.db-block.drag-over {
  outline: 2px dashed var(--primary-light);
  outline-offset: -2px;
  border-radius: var(--radius-sm);
  opacity: 0.7;
}

.reorder-btn {
  color: var(--text3);
  font-size: 12px;
  cursor: grab;
  padding: 0 4px;
  margin-right: 2px;
  user-select: none;
  display: inline-flex;
  align-items: center;
}
</style>
