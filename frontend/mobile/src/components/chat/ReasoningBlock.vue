<template>
  <div class="reasoning-block" :class="{ collapsed: isCollapsed }">
    <div class="rb-toggle" @click="toggle">
      <span class="rb-toggle-icon">&#9654;</span>
      {{ label }}
    </div>
    <div class="rb-content">
      <MarkdownContent :content="content" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import MarkdownContent from './MarkdownContent.vue'

const props = withDefaults(
  defineProps<{
    content: string
    collapsed?: boolean
    label?: string
  }>(),
  {
    collapsed: true,
    label: '思考过程',
  }
)

/** 使用本地状态, 不依赖父组件处理 update:collapsed 事件 */
const isCollapsed = ref(props.collapsed)

function toggle() {
  isCollapsed.value = !isCollapsed.value
}
</script>

<style scoped>
.reasoning-block {
  border-left: 3px solid var(--primary-light);
  padding: 4px 0 4px 10px;
  margin: 6px 0;
  font-size: 13px;
  color: var(--text2);
  background: var(--surface2);
  border-radius: 0 8px 8px 0;
}

.rb-toggle {
  cursor: pointer;
  font-size: 12px;
  color: var(--text3);
  user-select: none;
  display: flex;
  align-items: center;
  gap: 4px;
}

.rb-toggle:hover {
  color: var(--text2);
}

.rb-toggle-icon {
  display: inline-block;
  transition: transform 0.2s;
  font-size: 10px;
}

.reasoning-block.collapsed .rb-toggle-icon {
  transform: rotate(0deg);
}

.reasoning-block:not(.collapsed) .rb-toggle-icon {
  transform: rotate(90deg);
}

.reasoning-block.collapsed .rb-content {
  display: none;
}

.rb-content {
  margin-top: 4px;
}
</style>
