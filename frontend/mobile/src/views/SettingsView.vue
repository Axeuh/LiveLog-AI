<template>
  <div id="page-settings" class="page active">
    <div class="settings-scroll">

      <!-- 组1: 账户 -->
      <div class="settings-group">
        <div class="group-header">账户</div>
        <div class="group-body">
          <div class="setting-row" @click="handleLogin">
            <span class="row-icon">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                <circle cx="12" cy="7" r="4"/>
              </svg>
            </span>
            <span class="row-title">{{ isLoggedIn ? '已登录' : '登录' }}</span>
            <span class="row-value">{{ isLoggedIn ? '' : '未登录' }}</span>
            <span class="row-arrow">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="9 18 15 12 9 6"/>
              </svg>
            </span>
          </div>
          <div v-if="isLoggedIn" class="setting-row" @click="handleLogout">
            <span class="row-icon" style="color:var(--danger)">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
                <polyline points="16 17 21 12 16 7"/>
                <line x1="21" y1="12" x2="9" y2="12"/>
              </svg>
            </span>
            <span class="row-title" style="color:var(--danger)">退出登录</span>
          </div>
        </div>
      </div>

      <!-- 组2: 聊天设置 -->
      <div class="settings-group">
        <div class="group-header">聊天</div>
        <div class="group-body">
          <div class="setting-row setting-row--expandable" @click="togglePrefixForm">
            <span class="row-icon">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/>
                <line x1="7" y1="7" x2="7.01" y2="7"/>
              </svg>
            </span>
            <span class="row-title">消息前缀</span>
            <span class="row-value">{{ showPrefixForm ? '' : '已配置' }}</span>
            <span class="row-arrow" :class="{ 'row-arrow--open': showPrefixForm }">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="6 9 12 15 18 9"/>
              </svg>
            </span>
          </div>
          <Transition name="prefix-expand">
            <div v-if="showPrefixForm" class="prefix-form-inline">
              <div class="prefix-field">
                <label class="prefix-label">说话人</label>
                <input
                  v-model="editingConfig.speaker"
                  class="prefix-input"
                  type="text"
                  placeholder="输入说话人名称"
                />
              </div>
              <div class="prefix-field">
                <label class="prefix-label">系统提示</label>
                <textarea
                  v-model="editingConfig.prompt"
                  class="prefix-input prefix-textarea"
                  rows="3"
                  placeholder="输入前缀提示词"
                ></textarea>
              </div>
              <div class="prefix-actions">
                <span v-if="prefixSaved" class="prefix-saved">已保存</span>
                <button class="prefix-save-btn" @click="handleSavePrefix">保存</button>
              </div>
            </div>
          </Transition>
        </div>
      </div>

      <!-- 组3: 主题 -->
      <div class="settings-group">
        <div class="group-header">外观</div>
        <div class="group-body">
          <div class="setting-row" @click="cycleTheme">
            <span class="row-icon">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="13.5" cy="6.5" r="2.5"/>
                <path d="M17.5 10.5c-1 1.5-3 2.5-5 2.5s-4-1-5-2.5L3 17h18L17.5 10.5z"/>
              </svg>
            </span>
            <span class="row-title">主题</span>
            <span class="row-value">{{ themeNames[theme] }}</span>
          </div>
          <div class="setting-row" @click="openSystemSettings">
            <span class="row-icon">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="3"/>
                <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/>
              </svg>
            </span>
            <span class="row-title">打开系统设置</span>
            <span class="row-arrow">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="9 18 15 12 9 6"/>
              </svg>
            </span>
          </div>
        </div>
      </div>

      <!-- 组4: 调试 -->
      <div class="settings-group">
        <div class="group-header">调试</div>
        <div class="group-body">
          <div class="setting-row" @click="showDebug = !showDebug">
            <span class="row-icon">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="4 17 10 11 4 5"/>
                <line x1="12" y1="19" x2="20" y2="19"/>
              </svg>
            </span>
            <span class="row-title">调试面板</span>
            <span class="row-arrow">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="9 18 15 12 9 6"/>
              </svg>
            </span>
          </div>
          <div class="setting-row" @click="handleRefresh">
            <span class="row-icon">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="23 4 23 10 17 10"/>
                <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
              </svg>
            </span>
            <span class="row-title">刷新页面</span>
            <span class="row-arrow">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="9 18 15 12 9 6"/>
              </svg>
            </span>
          </div>
        </div>
      </div>

      <!-- 组5: 关于 -->
      <div class="settings-group">
        <div class="group-header">关于</div>
        <div class="group-body">
          <div class="setting-row">
            <span class="row-icon">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="10"/>
                <line x1="12" y1="16" x2="12" y2="12"/>
                <line x1="12" y1="8" x2="12.01" y2="8"/>
              </svg>
            </span>
            <span class="row-title">版本</span>
            <span class="row-value">v1.0.0</span>
          </div>
        </div>
      </div>

      <!-- 底部标识 -->
      <div class="settings-footer">
        <span>Axeuh Health Monitor</span>
      </div>

    </div>

    <!-- 调试面板覆盖层 -->
    <Transition name="debug-slide">
      <div v-if="showDebug" class="debug-overlay">
        <div class="debug-overlay__header">
          <span class="debug-overlay__title">
            <i class="fas fa-terminal"></i>
            调试面板
          </span>
          <button class="debug-overlay__close" @click="showDebug = false">
            <i class="fas fa-times"></i>
          </button>
        </div>
        <div class="debug-overlay__body">
          <DebugPanel />
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useApi } from '@/composables/useApi'
import { usePrefixConfig } from '@/composables/usePrefixConfig'
import { useTheme } from '@/composables/useTheme'
import type { PrefixConfig } from '@/composables/usePrefixConfig'
import DebugPanel from '@/components/settings/DebugPanel.vue'

const router = useRouter()
const api = useApi()
const { theme, setTheme, availableThemes } = useTheme()

// 主题名称映射
const themeNames: Record<string, string> = { dark: '深色', light: '浅色', glacier: '冰川' }

// 循环切换主题
function cycleTheme(): void {
  const idx = availableThemes.indexOf(theme.value)
  const next = availableThemes[(idx + 1) % availableThemes.length]
  setTheme(next)
}

// 登录状态
const isLoggedIn = computed(() => api.isLoggedIn.value)

// 调试面板显示状态
const showDebug = ref(false)

// 消息前缀设置
const { prefixConfig, updatePrefixConfig } = usePrefixConfig()
const showPrefixForm = ref(false)
const editingConfig = ref<PrefixConfig>({ ...prefixConfig.value })
const prefixSaved = ref(false)
let prefixSavedTimer: ReturnType<typeof setTimeout> | null = null

function togglePrefixForm(): void {
  showPrefixForm.value = !showPrefixForm.value
  if (showPrefixForm.value) {
    editingConfig.value = { ...prefixConfig.value }
  }
}

function handleSavePrefix(): void {
  updatePrefixConfig({ ...editingConfig.value })
  prefixSaved.value = true
  if (prefixSavedTimer) clearTimeout(prefixSavedTimer)
  prefixSavedTimer = setTimeout(() => {
    prefixSaved.value = false
  }, 2000)
}

/**
 * 打开系统设置
 * 触发 axeuh://open-settings scheme，由原生 WebViewClient 拦截
 */
function openSystemSettings(): void {
  window.location.href = 'axeuh://open-settings'
}

/**
 * 刷新页面
 */
function handleRefresh(): void {
  window.location.reload()
}

/**
 * 登出处理
 */
function handleLogout(): void {
  const confirmed = window.confirm('确定要退出登录吗？')
  if (confirmed) {
    api.logout()
    router.push('/chat')
  }
}

/**
 * 登录处理 - 跳转到聊天页触发登录覆盖层
 */
function handleLogin(): void {
  router.push('/chat')
}
</script>

<style scoped>
/* 页面容器 */
#page-settings {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
}

.settings-scroll {
  padding: 16px 16px 40px;
  max-width: 600px;
  margin: 0 auto;
}

/* 分组 */
.settings-group {
  margin-bottom: 24px;
}

.group-header {
  font-size: 13px;
  font-weight: 500;
  color: var(--text3);
  padding: 0 16px 6px;
  text-transform: uppercase;
  letter-spacing: 0.02em;
}

.group-body {
  background: var(--surface);
  border-radius: 12px;
  overflow: hidden;
}

/* 行 */
.setting-row {
  display: flex;
  align-items: center;
  height: 44px;
  padding: 0 16px;
  cursor: pointer;
  transition: background 0.12s;
  -webkit-tap-highlight-color: transparent;
}

.setting-row:active {
  background: var(--surface2);
}

.setting-row:not(:last-child) {
  border-bottom: 0.5px solid var(--border);
}

/* 前缀展开行下方也需要分隔线 */
.prefix-form-inline + .setting-row,
.prefix-expand-enter-active + .setting-row {
  border-top: 0.5px solid var(--border);
}

.row-icon {
  width: 20px;
  height: 20px;
  margin-right: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--primary);
  flex-shrink: 0;
}

.row-title {
  font-size: 16px;
  color: var(--text);
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.row-value {
  font-size: 16px;
  color: var(--text3);
  margin-right: 4px;
  white-space: nowrap;
}

.row-arrow {
  color: var(--text3);
  margin-left: 4px;
  display: flex;
  align-items: center;
  transition: transform 0.2s ease;
  flex-shrink: 0;
}

.row-arrow--open {
  transform: rotate(180deg);
}

/* 前缀表单内联展开 */
.prefix-form-inline {
  padding: 12px 16px 16px;
  border-top: 0.5px solid var(--border);
}

.prefix-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 10px;
}

.prefix-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--text2);
}

.prefix-input {
  width: 100%;
  padding: 10px 12px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--text);
  font-size: 14px;
  font-family: inherit;
  outline: none;
  box-sizing: border-box;
  transition: border-color 0.15s;
}

.prefix-input:focus {
  border-color: var(--primary);
}

.prefix-input::placeholder {
  color: var(--text3);
}

.prefix-textarea {
  resize: vertical;
  min-height: 60px;
  line-height: 1.5;
}

.prefix-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 4px;
}

.prefix-saved {
  font-size: 13px;
  color: var(--accent);
  font-weight: 500;
}

.prefix-save-btn {
  padding: 8px 20px;
  border-radius: 8px;
  border: none;
  background: var(--primary);
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  transition: background 0.15s;
}

.prefix-save-btn:active {
  background: var(--primary-light);
}

/* 前缀展开动画 */
.prefix-expand-enter-active {
  transition: all 0.25s ease;
  overflow: hidden;
}

.prefix-expand-leave-active {
  transition: all 0.2s ease;
  overflow: hidden;
}

.prefix-expand-enter-from,
.prefix-expand-leave-to {
  opacity: 0;
  max-height: 0;
  padding-top: 0;
  padding-bottom: 0;
}

.prefix-expand-enter-to,
.prefix-expand-leave-from {
  max-height: 300px;
}

/* 底部标识 */
.settings-footer {
  text-align: center;
  padding: 12px 0 0;
  font-size: 12px;
  color: var(--text3);
}

/* 调试面板覆盖层 */
.debug-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.92);
  backdrop-filter: blur(16px);
  z-index: 700;
  display: flex;
  flex-direction: column;
}

.debug-overlay__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 20px;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.debug-overlay__title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 700;
  color: var(--text);
}

.debug-overlay__title i {
  color: var(--primary-light);
}

.debug-overlay__close {
  background: transparent;
  border: none;
  color: var(--text3);
  font-size: 20px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 6px;
}

.debug-overlay__close:active {
  background: var(--surface2);
}

.debug-overlay__body {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px 90px;
}

/* 调试面板动画 */
.debug-slide-enter-active,
.debug-slide-leave-active {
  transition: opacity 0.2s ease;
}

.debug-slide-enter-from,
.debug-slide-leave-to {
  opacity: 0;
}

/* PC 模式 */
@media (min-width: 768px) {
  .settings-scroll {
    padding: 24px 24px 40px;
  }
}
</style>
