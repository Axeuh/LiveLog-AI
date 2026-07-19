<template>
  <Teleport to="body">
    <Transition name="login-overlay">
      <div
        v-if="visible"
        class="login-overlay"
        @keydown.escape="handleEscape"
        tabindex="-1"
        ref="overlayRef"
      >
        <!-- 关闭按钮 (加载中隐藏) -->
        <button
          v-if="!loading"
          class="login-close"
          @click="handleClose"
          aria-label="关闭登录"
        >
          <i class="fas fa-times"></i>
        </button>

        <!-- 登录卡片 -->
        <div class="login-card">
          <!-- 标题 -->
          <h2 class="login-title">
            <i class="fas fa-right-to-bracket"></i>
            登录
          </h2>
          <p class="login-subtitle">请登录后使用 Axeuh Mobile</p>

          <!-- 表单 -->
          <form class="login-form" @submit.prevent="handleLogin">
            <!-- 用户名输入 -->
            <div class="login-field">
              <label class="login-label" for="login-username">用户名</label>
              <div class="login-input-wrap">
                <i class="fas fa-user login-input-icon"></i>
                <input
                  id="login-username"
                  ref="usernameRef"
                  v-model="username"
                  type="text"
                  placeholder="输入用户名"
                  autocomplete="username"
                  :disabled="loading"
                />
              </div>
            </div>

            <!-- 密码输入 -->
            <div class="login-field">
              <label class="login-label" for="login-password">密码</label>
              <div class="login-input-wrap has-toggle">
                <i class="fas fa-lock login-input-icon"></i>
                <input
                  id="login-password"
                  v-model="password"
                  :type="showPassword ? 'text' : 'password'"
                  placeholder="输入密码"
                  autocomplete="current-password"
                  :disabled="loading"
                />
                <button
                  type="button"
                  class="login-eye"
                  @click="showPassword = !showPassword"
                  :aria-label="showPassword ? '隐藏密码' : '显示密码'"
                >
                  <i :class="showPassword ? 'fas fa-eye-slash' : 'fas fa-eye'"></i>
                </button>
              </div>
            </div>

            <!-- 错误信息 -->
            <Transition name="error-slide">
              <div v-if="errorMsg" class="login-error">
                <i class="fas fa-circle-exclamation"></i>
                {{ errorMsg }}
              </div>
            </Transition>

            <!-- 登录按钮 -->
            <button
              type="submit"
              class="login-btn"
              :disabled="loading || !username.trim() || !password.trim()"
            >
              <i v-if="loading" class="fas fa-spinner fa-spin"></i>
              <span>{{ loading ? '登录中...' : '登录' }}</span>
            </button>
            <p class="login-hint">提示：在电脑上登录后，复制 URL 中的 token 参数即可</p>
          </form>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { useApi } from '@/composables/useApi'

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  close: []
  'login-success': [token: string]
}>()

const { login } = useApi()

// 表单状态
const username = ref('')
const password = ref('')
const showPassword = ref(false)
const loading = ref(false)
const errorMsg = ref('')

// DOM 引用
const overlayRef = ref<HTMLElement | null>(null)
const usernameRef = ref<HTMLInputElement | null>(null)

/**
 * 处理登录提交
 * 调用 useApi().login(), 成功后 emit login-success 事件
 */
async function handleLogin(): Promise<void> {
  const u = username.value.trim()
  const p = password.value.trim()
  if (!u || !p || loading.value) return

  loading.value = true
  errorMsg.value = ''

  try {
    const result = await login(u, password.value)

    if (result === null) {
      errorMsg.value = '网络错误, 请检查连接后重试'
      return
    }

    if (result.success && result.token) {
      // 登录成功: 通知父组件
      emit('login-success', result.token)
      // 重置表单
      username.value = ''
      password.value = ''
      errorMsg.value = ''
    } else {
      // 登录失败: 显示服务器返回的错误信息
      errorMsg.value = result.message || '用户名或密码错误'
    }
  } catch {
    errorMsg.value = '登录请求失败, 请稍后重试'
  } finally {
    loading.value = false
  }
}

/** ESC 键关闭 (加载中不可关闭) */
function handleEscape(): void {
  if (!loading.value) {
    handleClose()
  }
}

/** 关闭按钮 */
function handleClose(): void {
  if (loading.value) return
  errorMsg.value = ''
  emit('close')
}

/**
 * 监听 visible 变化
 * 打开时自动聚焦用户名输入框并清空错误信息
 */
watch(() => props.visible, async (newVal) => {
  if (newVal) {
    errorMsg.value = ''
    await nextTick()
    usernameRef.value?.focus()
  }
})

// 输入时清除错误信息
watch(username, () => {
  if (errorMsg.value) errorMsg.value = ''
})
watch(password, () => {
  if (errorMsg.value) errorMsg.value = ''
})
</script>

<style scoped>
/* 组件级设计 token: --danger (扩展设计系统) */
.login-overlay {
  --danger: #ff6b6b;

  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.88);
  backdrop-filter: blur(14px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 700;
  padding: 20px;
  outline: none;
}

/* 过渡动画 */
.login-overlay-enter-active,
.login-overlay-leave-active {
  transition: opacity 0.3s ease, transform 0.3s ease;
}

.login-overlay-enter-from,
.login-overlay-leave-to {
  opacity: 0;
  transform: scale(0.95);
}

/* 关闭按钮 */
.login-close {
  position: absolute;
  top: 14px;
  right: 20px;
  z-index: 10;
  background: transparent;
  border: none;
  color: var(--text3);
  font-size: 22px;
  cursor: pointer;
  padding: 6px 10px;
  border-radius: 6px;
  transition: background 0.15s, color 0.15s;
}

.login-close:hover {
  background: var(--surface2);
  color: var(--text);
}

/* 登录卡片 */
.login-card {
  width: 100%;
  max-width: 360px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 32px 24px;
}

/* 标题 */
.login-title {
  text-align: center;
  font-size: 20px;
  font-weight: 700;
  color: var(--text);
  margin: 0 0 28px;
  font-family: 'Plus Jakarta Sans', sans-serif;
}

.login-title i {
  color: var(--primary);
  margin-right: 6px;
}

/* 副标题 */
.login-subtitle {
  text-align: center;
  font-size: 13px;
  color: var(--text2);
  margin: -16px 0 24px;
}

/* 表单 */
.login-form {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

/* 字段 */
.login-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.login-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text2);
}

/* 输入框容器 */
.login-input-wrap {
  position: relative;
  display: flex;
  align-items: center;
}

.login-input-icon {
  position: absolute;
  left: 14px;
  color: var(--text3);
  font-size: 14px;
  pointer-events: none;
  z-index: 1;
}

.login-input-wrap input {
  width: 100%;
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 12px 14px 12px 40px;
  color: var(--text);
  font-family: inherit;
  font-size: 14px;
  outline: none;
  transition: border-color 0.2s;
}

.login-input-wrap.has-toggle input {
  padding-right: 42px;
}

.login-input-wrap input::placeholder {
  color: var(--text3);
}

.login-input-wrap input:focus {
  border-color: var(--primary);
}

.login-input-wrap input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* 密码可见切换按钮 */
.login-eye {
  position: absolute;
  right: 6px;
  background: transparent;
  border: none;
  color: var(--text3);
  cursor: pointer;
  padding: 6px 8px;
  font-size: 14px;
  border-radius: 6px;
  transition: color 0.15s, background 0.15s;
}

.login-eye:hover {
  color: var(--text);
  background: var(--surface3);
}

/* 错误信息 */
.login-error {
  background: color-mix(in srgb, var(--danger) 12%, transparent);
  border: 1px solid color-mix(in srgb, var(--danger) 30%, transparent);
  border-radius: var(--radius-sm);
  padding: 10px 14px;
  color: var(--danger);
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 8px;
  line-height: 1.4;
}

/* 错误信息过渡动画 */
.error-slide-enter-active,
.error-slide-leave-active {
  transition: all 0.3s ease;
  overflow: hidden;
}

.error-slide-enter-from,
.error-slide-leave-to {
  opacity: 0;
  max-height: 0;
  padding-top: 0;
  padding-bottom: 0;
  margin-top: -18px;
}

.error-slide-enter-to,
.error-slide-leave-from {
  max-height: 80px;
}

/* 登录按钮 */
.login-btn {
  width: 100%;
  background: var(--primary);
  color: #fff;
  border: none;
  border-radius: 12px;
  padding: 13px;
  font-size: 15px;
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  transition: background 0.15s, opacity 0.15s;
}

.login-btn:hover {
  background: var(--primary-light);
}

.login-btn:active {
  opacity: 0.9;
}

.login-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.login-btn .fa-spin {
  font-size: 14px;
}

/* 提示文字 */
.login-hint {
  text-align: center;
  font-size: 11px;
  color: var(--text3);
  margin: 16px 0 0;
  line-height: 1.4;
}
</style>
