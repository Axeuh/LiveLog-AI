<template>
  <div class="pull-indicator" :class="{ active: pulling }">
    <template v-if="pulling">
      <i class="fas fa-arrow-down" v-if="state === 'pending'"></i>
      <i class="fas fa-spinner fa-spin" v-else-if="state === 'loading'"></i>
      <i class="fas fa-check" v-else></i>
      <span class="pull-indicator__text">{{ text }}</span>
    </template>
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  pulling?: boolean
  state?: 'pending' | 'loading' | 'done'
  text?: string
}>(), {
  pulling: false,
  state: 'pending',
  text: '下拉刷新',
})
</script>

<style scoped>
.pull-indicator {
  text-align: center;
  padding: 8px;
  font-size: 11px;
  color: var(--text3);
  display: none;
  gap: 6px;
  align-items: center;
  justify-content: center;
}

.pull-indicator.active {
  display: flex;
}

.pull-indicator__text {
  font-size: 11px;
  color: var(--text3);
}
</style>
