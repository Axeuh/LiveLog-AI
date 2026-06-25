<template>
  <div class="page-state" :class="[state]">
    <!-- Loading -->
    <template v-if="state === 'loading'">
      <div class="page-state__icon">
        <i class="fas fa-spinner fa-spin"></i>
      </div>
      <h1 class="page-state__title">{{ message || '加载中...' }}</h1>
    </template>

    <!-- Empty -->
    <template v-else-if="state === 'empty'">
      <div class="page-state__icon">
        <i class="fas" :class="icon || 'fa-inbox'"></i>
      </div>
      <h1 class="page-state__title">{{ message || '暂无数据' }}</h1>
      <p class="page-state__desc" v-if="description">{{ description }}</p>
    </template>

    <!-- Error -->
    <template v-else-if="state === 'error'">
      <div class="page-state__icon">
        <i class="fas" :class="icon || 'fa-exclamation-triangle'"></i>
      </div>
      <h1 class="page-state__title">{{ message || '加载失败' }}</h1>
      <p class="page-state__desc" v-if="description">{{ description }}</p>
      <button class="page-state__retry" @click="$emit('retry')">
        <i class="fas fa-redo-alt"></i> 重试
      </button>
    </template>

    <!-- Success -->
    <template v-else>
      <div class="page-state__icon">
        <i class="fas" :class="icon || 'fa-check-circle'"></i>
      </div>
      <h1 class="page-state__title">{{ message || '操作成功' }}</h1>
      <p class="page-state__desc" v-if="description">{{ description }}</p>
    </template>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  state: 'loading' | 'empty' | 'error' | 'success'
  message?: string
  icon?: string
  description?: string
}>()

defineEmits<{
  retry: []
}>()
</script>

<style scoped>
.page-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  gap: 12px;
  min-height: 50vh;
  animation: sdFadeIn 0.3s ease;
}

.page-state__icon {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: var(--surface2);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.5rem;
  color: var(--primary-light);
}

.page-state.error .page-state__icon {
  color: #ff6b6b;
}

.page-state.success .page-state__icon {
  color: var(--accent);
}

.page-state.loading .page-state__icon {
  color: var(--primary-light);
}

.page-state__title {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--text);
  margin: 0;
  line-height: 1.3;
  text-align: center;
}

.page-state__desc {
  font-size: 0.9rem;
  color: var(--text2);
  margin: 0;
  max-width: 280px;
  line-height: 1.5;
  text-align: center;
}

.page-state__retry {
  margin-top: 8px;
  padding: 10px 24px;
  border: none;
  border-radius: 10px;
  background: var(--primary);
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  font-family: inherit;
  display: flex;
  align-items: center;
  gap: 6px;
  transition: background 0.15s;
}

.page-state__retry:active {
  background: var(--primary-light);
}
</style>
