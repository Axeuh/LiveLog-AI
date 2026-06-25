<template>
  <div class="file-tree">
    <div v-if="loading" class="file-tree__loading">
      <LoadingSpinner size="sm" text="加载文件列表..." />
    </div>
    <div v-else-if="files.length === 0" class="file-tree__empty">
      当前目录为空
    </div>
    <div v-else class="file-tree__list">
      <FileItem
        v-for="entry in files"
        :key="entry.name"
        :entry="entry"
        :depth="0"
        :parent-path="parentPath"
        @preview="handlePreview"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import type { FileEntry } from '@/types'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import FileItem from './FileItem.vue'

defineProps<{
  files: FileEntry[]
  loading: boolean
  parentPath?: string
}>()

const emit = defineEmits<{
  preview: [entry: FileEntry, path: string]
}>()

function handlePreview(entry: FileEntry, path: string): void {
  emit('preview', entry, path)
}
</script>

<style scoped>
.file-tree {
  flex: 1;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  padding-bottom: 12px;
}

.file-tree__loading {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 0;
}

.file-tree__empty {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 0;
  font-size: 13px;
  color: var(--text3);
}

.file-tree__list {
  padding: 4px 0;
}
</style>
