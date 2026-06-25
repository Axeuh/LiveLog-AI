<template>
  <div class="loading-spinner" :class="[size]">
    <i class="fas fa-spinner fa-spin"></i>
    <span v-if="text" class="loading-spinner__text">{{ text }}</span>
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  size?: 'sm' | 'md' | 'lg'
  text?: string
}>(), {
  size: 'md',
})
</script>

<style scoped>
.loading-spinner {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: var(--primary-light);
}

.loading-spinner.sm {
  font-size: 16px;
}

.loading-spinner.md {
  font-size: 24px;
}

.loading-spinner.lg {
  font-size: 36px;
}

.loading-spinner__text {
  font-size: 13px;
  color: var(--text3);
  font-weight: 500;
}
</style>
