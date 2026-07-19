<template>
  <div class="md-content" v-html="renderedHtml"></div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { renderMarkdown } from '@/utils/markdown'

const props = defineProps<{
  content: string
}>()

const renderedHtml = computed<string>(() => renderMarkdown(props.content))
</script>
