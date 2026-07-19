<template>
  <div class="skeleton-loader" :class="[type]">
    <!-- Card skeleton -->
    <template v-if="type === 'card'">
      <div
        v-for="i in count"
        :key="i"
        class="skeleton-card"
      >
        <div class="skeleton skeleton-line skeleton-title"></div>
        <div class="skeleton skeleton-line skeleton-body"></div>
      </div>
    </template>

    <!-- Chart skeleton -->
    <template v-else-if="type === 'chart'">
      <div
        v-for="i in count"
        :key="i"
        class="skeleton skeleton-chart"
      ></div>
    </template>

    <!-- List skeleton -->
    <template v-else>
      <div
        v-for="i in count"
        :key="i"
        class="skeleton-list-item"
      >
        <div class="skeleton skeleton-avatar"></div>
        <div class="skeleton-list-content">
          <div class="skeleton skeleton-line skeleton-line-short"></div>
          <div class="skeleton skeleton-line skeleton-line-long"></div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  type: 'card' | 'chart' | 'list'
  count?: number
}>(), {
  count: 3,
})
</script>

<style scoped>
.skeleton-loader {
  width: 100%;
}

.skeleton {
  background: linear-gradient(90deg, var(--surface) 25%, var(--surface2) 50%, var(--surface) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: var(--radius-sm);
}

/* Card skeleton */
.skeleton-card {
  background: var(--surface);
  border-radius: var(--radius-sm);
  padding: 16px;
  margin-bottom: 10px;
}

.skeleton-title {
  height: 16px;
  width: 60%;
  margin-bottom: 12px;
}

.skeleton-body {
  height: 12px;
  width: 90%;
}

/* Chart skeleton */
.skeleton-chart {
  height: 120px;
  margin-bottom: 10px;
}

/* List skeleton */
.skeleton-list-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 0;
  border-bottom: 1px solid var(--border);
}

.skeleton-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  flex-shrink: 0;
}

.skeleton-list-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.skeleton-line {
  height: 12px;
}

.skeleton-line-short {
  width: 40%;
}

.skeleton-line-long {
  width: 80%;
}
</style>
