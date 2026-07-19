<template>
  <div v-if="isEditing" class="edit-controls">
    <button
      v-for="item in sensorToggleList"
      :key="item.name"
      class="sensor-toggle-btn"
      :class="{ active: item.visible }"
      @click="$emit('toggle-sensor', item.name)"
    >
      {{ item.label }}
    </button>
  </div>
</template>

<script setup lang="ts">
interface SensorToggleItem {
  name: string
  label: string
  visible: boolean
}

defineProps<{
  isEditing: boolean
  sensorToggleList: SensorToggleItem[]
}>()

defineEmits<{
  'toggle-sensor': [name: string]
}>()
</script>

<style scoped>
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
</style>
