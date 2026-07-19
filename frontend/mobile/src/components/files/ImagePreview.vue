<template>
  <div class="preview-image-wrap">
    <!-- 缩略图 -->
    <img
      :src="imageSrc"
      :alt="alt"
      class="preview-img"
      :class="{ 'preview-img--hidden': loading || error }"
      @load="onImgLoad"
      @error="onImgError"
      @click="fullscreen = true"
    />

    <!-- 加载状态 -->
    <div v-if="loading" class="preview-image-loading">加载中...</div>

    <!-- 错误状态 -->
    <div v-if="error" class="preview-image-error">加载失败</div>

    <!-- 全屏 overlay -->
    <div
      v-if="fullscreen"
      class="preview-fs-overlay"
      @wheel.prevent="onWheel"
      @mousedown="onDragStart"
      @mousemove="onDragMove"
      @mouseup="onDragEnd"
      @mouseleave="onDragEnd"
      @touchstart.passive="onTouchStart"
      @touchmove.passive="onTouchMove"
      @touchend.passive="onTouchEnd"
      @dblclick="toggleZoom"
      tabindex="0"
      @keydown="onKeydown"
    >
      <!-- 关闭按钮 -->
      <button class="fs-close-btn" @click="fullscreen = false">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <line x1="18" y1="6" x2="6" y2="18" />
          <line x1="6" y1="6" x2="18" y2="18" />
        </svg>
      </button>

      <!-- 图片容器 -->
      <div class="fs-img-wrap" ref="imgWrapRef">
        <img
          :src="imageSrc"
          :alt="alt"
          :style="imgStyle"
          draggable="false"
          :class="{ dragging: isDragging }"
          @load="onFsImgLoad"
        />
      </div>

      <!-- 缩放指示器 -->
      <div class="fs-zoom-badge">{{ zoomPercent }}%</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import { getFileRawUrl } from '@/api/files'

const props = defineProps<{
  src: string
  alt?: string
}>()

/* ---- 原图 URL ---- */
const imageSrc = computed(() => {
  if (!props.src) return ''
  if (props.src.startsWith('http://') || props.src.startsWith('https://') || props.src.startsWith('/')) {
    return props.src
  }
  return getFileRawUrl(props.src)
})

/* ---- 加载 / 错误 ---- */
const loading = ref(true)
const error = ref(false)

function onImgError(): void {
  loading.value = false
  error.value = true
}

function onImgLoad(_e: Event): void {
  loading.value = false
}

/* ---- 全屏状态 ---- */
const fullscreen = ref(false)
const imgWrapRef = ref<HTMLElement | null>(null)

/* ---- 变换 ---- */
const scale = ref(1)
const panX = ref(0)
const panY = ref(0)
const isDragging = ref(false)
const dragStart = ref({ x: 0, y: 0 })
const lastPinchDist = ref(0)
let naturalW = 0
let naturalH = 0
const fitScale = ref(1)

const imgStyle = computed(() => ({
  transform: `translate(${panX.value}px, ${panY.value}px) scale(${scale.value})`,
  cursor: isDragging.value ? 'grabbing' : 'grab',
}))

const zoomPercent = computed(() => Math.round(scale.value * 100))

/* ---- body overflow 控制 ---- */
watch(fullscreen, (val) => {
  document.body.style.overflow = val ? 'hidden' : ''
})

/* ---- 进入全屏时计算 fitScale ---- */
watch(fullscreen, async (val) => {
  if (val) {
    scale.value = 1
    panX.value = 0
    panY.value = 0
    await nextTick()
    recalcFitScale()
  }
})

function recalcFitScale(): void {
  const wrap = imgWrapRef.value
  if (wrap && naturalW && naturalH) {
    const cw = wrap.clientWidth
    const ch = wrap.clientHeight
    if (cw && ch) {
      fitScale.value = Math.min(cw / naturalW, ch / naturalH)
    }
  }
}

/* ---- 全屏图片加载 ---- */
function onFsImgLoad(e: Event): void {
  const img = e.target as HTMLImageElement
  naturalW = img.naturalWidth
  naturalH = img.naturalHeight
  recalcFitScale()
}

/* ---- 鼠标滚轮缩放 ---- */
function onWheel(e: WheelEvent): void {
  let delta: number
  if (e.ctrlKey || e.metaKey) {
    // Ctrl/Meta + 滚轮：以鼠标位置为中心缩放
    delta = e.deltaY > 0 ? -0.1 : 0.1
  } else {
    delta = e.deltaY > 0 ? -0.1 : 0.1
  }
  let newScale = scale.value * (1 + delta)
  newScale = Math.min(10, Math.max(0.25, newScale))
  scale.value = newScale
}

/* ---- 鼠标拖拽 ---- */
function onDragStart(e: MouseEvent): void {
  if (e.button !== 0) return
  isDragging.value = true
  dragStart.value = { x: e.clientX - panX.value, y: e.clientY - panY.value }
}

function onDragMove(e: MouseEvent): void {
  if (!isDragging.value) return
  panX.value = e.clientX - dragStart.value.x
  panY.value = e.clientY - dragStart.value.y
}

function onDragEnd(): void {
  isDragging.value = false
}

/* ---- 双击切换缩放 ---- */
function toggleZoom(): void {
  if (scale.value < 1.5) {
    scale.value = fitScale.value
  } else {
    scale.value = 1
    panX.value = 0
    panY.value = 0
  }
}

/* ---- 触摸手势 ---- */
function onTouchStart(e: TouchEvent): void {
  if (e.touches.length === 1) {
    isDragging.value = true
    dragStart.value = { x: e.touches[0].clientX - panX.value, y: e.touches[0].clientY - panY.value }
  } else if (e.touches.length === 2) {
    lastPinchDist.value = getTouchDist(e.touches)
  }
}

function onTouchMove(e: TouchEvent): void {
  if (e.touches.length === 1 && isDragging.value) {
    panX.value = e.touches[0].clientX - dragStart.value.x
    panY.value = e.touches[0].clientY - dragStart.value.y
  } else if (e.touches.length === 2) {
    const dist = getTouchDist(e.touches)
    if (lastPinchDist.value > 0) {
      const delta = dist / lastPinchDist.value
      let newScale = scale.value * delta
      newScale = Math.min(10, Math.max(0.25, newScale))
      scale.value = newScale
    }
    lastPinchDist.value = dist
  }
}

function onTouchEnd(): void {
  isDragging.value = false
  lastPinchDist.value = 0
}

function getTouchDist(touches: TouchList): number {
  if (touches.length < 2) return 0
  const dx = touches[0].clientX - touches[1].clientX
  const dy = touches[0].clientY - touches[1].clientY
  return Math.hypot(dx, dy)
}

/* ---- 键盘事件 ---- */
function onKeydown(e: KeyboardEvent): void {
  if (e.key === 'Escape') {
    fullscreen.value = false
  }
}
</script>

<style scoped>
/* ---- 容器 ---- */
.preview-image-wrap {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 200px;
}

/* ---- 缩略图 ---- */
.preview-img {
  max-width: 100%;
  max-height: 70vh;
  border-radius: var(--radius-sm);
  object-fit: contain;
  cursor: pointer;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.3);
  transition: opacity 0.25s ease, transform 0.15s ease;
  user-select: none;
  -webkit-user-drag: none;
}

.preview-img:hover {
  transform: scale(1.02);
}

.preview-img:active {
  transform: scale(0.98);
}

.preview-img--hidden {
  opacity: 0;
  position: absolute;
  pointer-events: none;
}

/* ---- 加载 / 错误 ---- */
.preview-image-loading,
.preview-image-error {
  padding: 40px 20px;
  font-size: 14px;
  text-align: center;
}

.preview-image-loading {
  color: var(--text2);
}

.preview-image-error {
  color: var(--danger);
}

/* ---- 全屏 overlay ---- */
.preview-fs-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  background: rgba(0, 0, 0, 0.85);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  display: flex;
  align-items: center;
  justify-content: center;
  outline: none;
}

/* ---- 关闭按钮 ---- */
.fs-close-btn {
  position: fixed;
  top: 16px;
  right: 16px;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.1);
  border: none;
  color: #fff;
  cursor: pointer;
  z-index: 1001;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s;
}

.fs-close-btn:hover {
  background: rgba(255, 255, 255, 0.2);
}

/* ---- 图片容器 ---- */
.fs-img-wrap {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 90vw;
  height: 90vh;
  overflow: hidden;
}

.fs-img-wrap img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  transition: transform 0.2s ease;
  user-select: none;
  -webkit-user-drag: none;
  will-change: transform;
}

.fs-img-wrap img.dragging {
  transition: none;
}

/* ---- 缩放指示器 ---- */
.fs-zoom-badge {
  position: fixed;
  bottom: 20px;
  right: 20px;
  background: rgba(0, 0, 0, 0.5);
  color: #fff;
  font-size: 13px;
  padding: 4px 10px;
  border-radius: 6px;
  font-family: monospace;
  z-index: 1001;
  pointer-events: none;
  user-select: none;
}
</style>
