<template>
  <div id="page-settings" class="page active">
    <div class="settings-center">
      <!-- 图标 -->
      <div class="settings-icon">
        <i class="fas fa-cog"></i>
      </div>

      <!-- 标题 -->
      <h1 class="settings-title">系统设置</h1>

      <!-- 说明文字 -->
      <p class="settings-desc">
        所有应用设置已迁移到原生界面。<br>点击下方按钮打开系统设置进行管理。
      </p>

      <!-- 打开系统设置按钮 -->
      <button class="settings-btn settings-btn--primary" @click="openSystemSettings">
        <i class="fas fa-mobile-alt"></i>
        <span>打开系统设置</span>
      </button>
      <span class="settings-hint">设置完成后返回将自动回到此页面</span>

      <!-- 分隔线 -->
      <div class="settings-divider"></div>

      <!-- 调试面板按钮 -->
      <button class="settings-btn settings-btn--outline" @click="showDebug = !showDebug">
        <i class="fas fa-terminal"></i>
        <span>调试面板</span>
      </button>

      <!-- 刷新页面按钮 -->
      <button class="settings-btn settings-btn--outline" @click="handleRefresh">
        <i class="fas fa-sync-alt"></i>
        <span>刷新页面</span>
      </button>

      <!-- 分隔线 -->
      <div class="settings-divider"></div>

      <!-- 消息前缀设置 -->
      <button class="settings-btn settings-btn--outline" @click="togglePrefixForm">
        <i class="fas fa-tag"></i>
        <span>消息前缀</span>
        <i class="fas fa-chevron-down prefix-chevron" :class="{ 'prefix-chevron--open': showPrefixForm }"></i>
      </button>

      <Transition name="prefix-fade">
        <div v-if="showPrefixForm" class="prefix-form">
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
          <span v-if="prefixSaved" class="prefix-saved">已保存</span>
          <button class="settings-btn settings-btn--primary prefix-save-btn" @click="handleSavePrefix">
            <i class="fas fa-check"></i>
            <span>保存</span>
          </button>
        </div>
      </Transition>

      <!-- 分隔线 -->
      <div class="settings-divider"></div>

      <!-- 登录/登出区域 -->
      <div class="settings-login-section">
        <div class="settings-login-status">
          <i class="fas fa-user"></i>
          <span>{{ isLoggedIn ? '已登录' : '未登录' }}</span>
        </div>
        <button
          v-if="isLoggedIn"
          class="settings-btn settings-btn--outline settings-btn--danger"
          @click="handleLogout"
        >
          <i class="fas fa-sign-out-alt"></i>
          <span>退出登录</span>
        </button>
        <button
          v-else
          class="settings-btn settings-btn--outline"
          @click="handleLogin"
        >
          <i class="fas fa-sign-in-alt"></i>
          <span>登录</span>
        </button>
      </div>
    </div>

    <!-- 调试面板 -->
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

    <!-- 版本信息 -->
    <div class="version-info">
      <span>Axeuh Health Monitor</span>
      <span>v1.0.0</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useApi } from '@/composables/useApi'
import { usePrefixConfig } from '@/composables/usePrefixConfig'
import type { PrefixConfig } from '@/composables/usePrefixConfig'
import DebugPanel from '@/components/settings/DebugPanel.vue'

const router = useRouter()
const api = useApi()

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
#page-settings {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
}

.settings-center {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 70vh;
  padding: 40px 20px;
  gap: 16px;
  text-align: center;
}

.settings-icon {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: var(--surface2);
  display: flex;
  align-items: center;
  justify-content: center;
}

.settings-icon i {
  font-size: 36px;
  color: var(--primary-light);
}

.settings-title {
  margin: 4px 0 0;
  font-size: 20px;
  font-weight: 700;
  color: var(--text);
}

.settings-desc {
  margin: 0;
  font-size: 13px;
  color: var(--text2);
  line-height: 1.6;
  max-width: 280px;
}

.settings-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  max-width: 280px;
  padding: 12px 32px;
  border-radius: 12px;
  font-size: 14px;
  font-weight: 500;
  font-family: inherit;
  cursor: pointer;
  transition: all 0.15s;
}

.settings-btn:active {
  transform: scale(0.98);
}

.settings-btn i {
  font-size: 15px;
}

.settings-btn--primary {
  margin-top: 8px;
  padding: 14px 40px;
  border: none;
  background: var(--primary);
  color: #fff;
  font-size: 15px;
  font-weight: 600;
}

.settings-btn--primary:active {
  background: var(--primary-light);
}

.settings-btn--outline {
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text2);
}

.settings-btn--outline:active {
  background: var(--surface2);
}

.settings-btn--danger {
  color: #ff6b6b;
}

.settings-btn--danger:active {
  background: rgba(255, 107, 107, 0.1);
}

.settings-hint {
  font-size: 11px;
  color: var(--text3);
  margin-top: 4px;
}

.settings-divider {
  width: 100%;
  max-width: 280px;
  border-top: 1px solid var(--border);
  margin: 8px 0 4px;
}

.settings-login-section {
  width: 100%;
  max-width: 280px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: center;
}

.settings-login-status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text3);
}

.settings-login-status i {
  font-size: 12px;
}

/* 消息前缀设置 */
.prefix-chevron {
  margin-left: auto;
  transition: transform 0.2s;
  font-size: 12px;
}

.prefix-chevron--open {
  transform: rotate(180deg);
}

.prefix-form {
  width: 100%;
  max-width: 280px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.prefix-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.prefix-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--text2);
  text-align: left;
}

.prefix-input {
  width: 100%;
  padding: 10px 12px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
  font-size: 13px;
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

.prefix-saved {
  font-size: 12px;
  color: var(--accent);
  font-weight: 500;
}

.prefix-save-btn {
  margin-top: 0;
}

/* 前缀表单动画 */
.prefix-fade-enter-active,
.prefix-fade-leave-active {
  transition: all 0.2s ease;
}

.prefix-fade-enter-from,
.prefix-fade-leave-to {
  opacity: 0;
  transform: translateY(-8px);
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

/* 版本信息 */
.version-info {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 20px 0 40px;
  font-size: 12px;
  color: var(--text3);
}
</style>
