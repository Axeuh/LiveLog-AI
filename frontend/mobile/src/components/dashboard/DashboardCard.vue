<template>
  <div
    class="db-block"
    :class="[
      sizeClass,
      `cv-${sensor}`,
      { 'db-block--editing': editing },
    ]"
    :data-sensor="sensor"
    :data-block-id="blockId"
  >
    <!-- 头部: 图标 + 标签 + 控制按钮 -->
    <div class="db-header">
      <span class="db-label">
        <i
          v-if="icon"
          :class="icon"
          :style="color ? { color } : {}"
        ></i>
        {{ label }}
      </span>
      <div class="db-controls">
        <!-- 编辑模式: 隐藏按钮 -->
        <button
          v-if="editing"
          class="db-ctrl-btn"
          title="隐藏"
          @click.stop="onHide"
        >
          <i class="fas fa-eye-slash"></i>
        </button>
        <!-- 编辑模式: 尺寸切换按钮 -->
        <button
          v-if="editing"
          class="db-ctrl-btn"
          title="切换尺寸"
          @click.stop="onCycleSize"
        >
          <i class="fas fa-expand-arrows-alt"></i>
        </button>
        <!-- 展开/收起按钮 -->
        <button
          class="db-ctrl-btn db-ctrl-btn--expand"
          title="展开"
          @click.stop="onToggleExpand"
        >
          <i
            class="fas fa-chevron-down"
            :class="{ rotated: expanded }"
          ></i>
        </button>
      </div>
    </div>

    <!-- 数值行 -->
    <div class="cv-row">
      <slot name="value">
        <span class="cv-main">--</span>
      </slot>
    </div>

    <!-- 展开区域 (带过渡动画) -->
    <Transition name="db-expand">
      <div v-if="expanded" class="db-expand">
        <slot name="expand"></slot>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

// ==================== Props ====================

const props = defineProps<{
  /** 块唯一标识 */
  blockId: string
  /** 块标签文本 */
  label: string
  /** Font Awesome 图标类名 */
  icon: string
  /** 图标颜色 (CSS 颜色值) */
  color: string
  /** 传感器类型 (用于 data-sensor 属性和样式类) */
  sensor: string
  /** 是否展开 */
  expanded?: boolean
  /**
   * 块尺寸
   * - 1 或 '1': 单列 (size-1)
   * - 2 或 '2': 双列 (size-2)
   * - '2x2': 双列双行 (size-2x2)
   */
  size?: 1 | 2 | '2x2'
  /** 是否处于编辑模式 */
  editing?: boolean
}>()

// ==================== Emits ====================

const emit = defineEmits<{
  /** 展开状态变更 */
  'update:expanded': [value: boolean]
  /** 尺寸变更 */
  'update:size': [value: 1 | 2 | '2x2']
  /** 隐藏该卡片 */
  'toggle-visibility': []
}>()

// ==================== 计算属性 ====================

/** 当前尺寸值, 默认为 1 */
const currentSize = computed(() => props.size ?? 1)

/** 尺寸对应的 CSS 类名 */
const sizeClass = computed(() => {
  const s = currentSize.value
  if (s === '2x2') return 'size-2x2'
  if (s === 2) return 'size-2'
  return 'size-1'
})

// ==================== 事件处理 ====================

/** 切换展开/收起 */
function onToggleExpand(): void {
  emit('update:expanded', !props.expanded)
}

/** 循环切换尺寸: 1 -> 2 -> 2x2 -> 1 */
function onCycleSize(): void {
  const s = currentSize.value
  if (s === 1) {
    emit('update:size', 2)
  } else if (s === 2) {
    emit('update:size', '2x2')
  } else {
    emit('update:size', 1)
  }
}

/** 隐藏卡片 */
function onHide(): void {
  emit('toggle-visibility')
}
</script>

<style scoped>
/* ==================== 块基础 ==================== */

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

/* ==================== 尺寸变体 ==================== */

.size-1 {
  grid-column: span 1;
}

.size-2 {
  grid-column: 1 / -1;
}

.size-2x2 {
  grid-column: 1 / -1;
  grid-row: span 2;
}

/* ==================== 头部 ==================== */

.db-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
}

.size-2 .db-header,
.size-2x2 .db-header {
  padding: 10px 14px;
}

.db-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text3);
  display: flex;
  align-items: center;
  gap: 5px;
}

.db-label i {
  font-size: 12px;
}

/* ==================== 控制按钮 ==================== */

.db-controls {
  display: flex;
  gap: 2px;
  align-items: center;
}

.db-ctrl-btn {
  -webkit-tap-highlight-color: transparent;
  outline: none;
  background: transparent;
  border: none;
  color: var(--text3);
  font-size: 13px;
  cursor: pointer;
  padding: 2px 5px;
  border-radius: 4px;
  transition: all 0.15s;
  line-height: 1;
}

.db-ctrl-btn:hover {
  color: var(--text);
  background: var(--surface3);
}

.db-ctrl-btn--expand i {
  transition: transform 0.2s;
  font-size: 10px;
}

.db-ctrl-btn--expand i.rotated {
  transform: rotate(180deg);
}

/* ==================== 数值行 ==================== */

.cv-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  padding: 2px 14px 8px;
}

.cv-main {
  font-size: 22px;
  font-weight: 700;
  font-family: 'Plus Jakarta Sans', sans-serif;
}

.cv-main :deep(.cv-unit) {
  font-size: 12px;
  font-weight: 400;
  color: var(--text2);
  margin-left: 2px;
}

.cv-main :deep(.cv-trend) {
  font-size: 11px;
  display: flex;
  align-items: center;
  gap: 3px;
}

:deep(.cv-trend.up) {
  color: var(--accent);
}

:deep(.cv-trend.down) {
  color: var(--accent2);
}

:deep(.cv-trend.flat) {
  color: var(--text3);
}

/* ==================== 传感器特定颜色 ==================== */

.cv-hr .cv-main {
  color: #ff6b6b;
}

.cv-steps .cv-main {
  color: var(--accent);
}

.cv-spo2 .cv-main {
  color: var(--primary-light);
}

.cv-stress .cv-main {
  color: var(--accent3);
}

.cv-battery .cv-main {
  color: #fdcb6e;
}

.cv-sleep .cv-main {
  color: var(--primary-light);
}

.cv-usage .cv-main {
  color: #74b9ff;
}

/* ==================== 展开区域 ==================== */

.db-expand {
  padding: 0 14px 14px;
}

.size-2 .db-expand :deep(.chart-wrap),
.size-2x2 .db-expand :deep(.chart-wrap) {
  height: 120px;
}

.size-2x2 .db-expand :deep(.chart-wrap) {
  height: 200px;
}

/* ==================== 展开/收起过渡动画 ==================== */

.db-expand-enter-active {
  animation: dbExpandIn 0.3s ease;
}

.db-expand-leave-active {
  animation: dbExpandIn 0.2s ease reverse;
}

@keyframes dbExpandIn {
  from {
    opacity: 0;
    max-height: 0;
    padding-top: 0;
    padding-bottom: 0;
  }
  to {
    opacity: 1;
    max-height: 400px;
    padding-top: 0;
    padding-bottom: 14px;
  }
}

/* ==================== 编辑模式高亮 ==================== */

.db-block--editing {
  outline: 1px dashed rgba(162, 155, 254, 0.3);
  outline-offset: -1px;
}
</style>
