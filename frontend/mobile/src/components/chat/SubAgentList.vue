<template>
  <!-- 遮罩层 -->
  <Transition name="fade">
    <div v-if="visible" class="subagent-overlay" @click.self="$emit('close')">
      <!-- 面板 -->
      <div class="subagent-panel">
        <!-- 头部 -->
        <div class="subagent-header">
          <h3>子智能体</h3>
          <button class="subagent-close" @click="$emit('close')">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"/>
              <line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>

        <!-- 列表 -->
        <div class="subagent-list">
          <template v-if="agents.length === 0">
            <div class="subagent-empty">
              <p>暂无子智能体</p>
              <span>当 AI 调用 task 工具时会出现在这里</span>
            </div>
          </template>

          <div
            v-for="agent in agents"
            :key="agent.id"
            class="subagent-item"
            :class="{ disabled: !agent.childSessionId }"
            @click="handleClick(agent)"
          >
            <!-- 类型图标 -->
            <span class="subagent-icon" :class="getTypeClass(agent.type)">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <!-- 终端 (默认) -->
                <template v-if="agent.type === 'bash' || agent.type === 'quick'">
                  <polyline points="4 17 10 11 4 5"/>
                  <line x1="12" y1="19" x2="20" y2="19"/>
                </template>
                <!-- 搜索 (explore/librarian) -->
                <template v-else-if="agent.type === 'explore' || agent.type === 'librarian'">
                  <circle cx="11" cy="11" r="8"/>
                  <line x1="21" y1="21" x2="16.65" y2="16.65"/>
                </template>
                <!-- 构建/深度 (build/deep/oracle) -->
                <template v-else-if="agent.type === 'build' || agent.type === 'deep' || agent.type === 'oracle'">
                  <polyline points="16 18 22 12 16 6"/>
                  <polyline points="8 6 2 12 8 18"/>
                </template>
                <!-- 视觉 (visual-engineering) -->
                <template v-else-if="agent.type === 'visual-engineering'">
                  <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
                  <circle cx="8.5" cy="8.5" r="1.5"/>
                  <polyline points="21 15 16 10 5 21"/>
                </template>
                <!-- 写作 -->
                <template v-else-if="agent.type === 'writing'">
                  <path d="M12 20h9"/>
                  <path d="M16.5 3.5a2.121 2.121 0 013 3L7 19l-4 1 1-4L16.5 3.5z"/>
                </template>
                <!-- Git -->
                <template v-else-if="agent.type === 'git'">
                  <circle cx="12" cy="12" r="10"/>
                  <line x1="12" y1="8" x2="12" y2="16"/>
                  <line x1="8" y1="12" x2="16" y2="12"/>
                </template>
                <!-- 默认齿轮 -->
                <template v-else>
                  <circle cx="12" cy="12" r="3"/>
                  <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/>
                </template>
              </svg>
            </span>

            <!-- 信息 -->
            <div class="subagent-info">
              <div class="subagent-name">{{ agent.name }}</div>
              <div class="subagent-meta">
                <span class="subagent-type">{{ agent.type }}</span>
                <span class="subagent-status" :class="agent.status">
                  {{ statusLabel(agent.status) }}
                </span>
              </div>
            </div>

            <!-- 箭头 -->
            <svg v-if="agent.childSessionId" class="subagent-chevron" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="9 18 15 12 9 6"/>
            </svg>
            <span v-else class="subagent-nosession" title="子会话 ID 未提取到">-</span>
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import type { SubAgentInfo } from '@/composables/useSubAgents'

defineProps<{
  visible: boolean
  agents: SubAgentInfo[]
}>()

const emit = defineEmits<{
  close: []
  select: [sessionId: string]
}>()

/** 点击子智能体 */
function handleClick(agent: SubAgentInfo): void {
  if (!agent.childSessionId) return
  emit('select', agent.childSessionId)
}

/** 类型 → CSS class */
function getTypeClass(type: string): string {
  return 'type-' + type.toLowerCase().replace(/[^a-z0-9]/g, '-')
}

/** 状态标签 */
function statusLabel(status: string): string {
  switch (status) {
    case 'completed': return '已完成'
    case 'running': return '运行中'
    case 'failed': return '失败'
    case 'error': return '错误'
    default: return status
  }
}
</script>

<style scoped>
/* 叠加层 */
.subagent-overlay {
  position: fixed;
  inset: 0;
  z-index: 200;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: flex-end;
  justify-content: center;
  -webkit-backdrop-filter: blur(4px);
  backdrop-filter: blur(4px);
}

/* 面板 */
.subagent-panel {
  width: 100%;
  max-width: 480px;
  max-height: 70vh;
  background: var(--surface);
  border-radius: 20px 20px 0 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 -4px 24px rgba(0, 0, 0, 0.4);
}

/* 头部 */
.subagent-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px 12px;
  border-bottom: 0.5px solid var(--border);
  flex-shrink: 0;
}

.subagent-header h3 {
  font-size: 17px;
  font-weight: 600;
  color: var(--text);
  margin: 0;
}

.subagent-close {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  border: none;
  background: var(--surface2);
  color: var(--text2);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s;
}

.subagent-close:active {
  background: var(--surface3);
}

/* 列表 */
.subagent-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px 16px 24px;
  -webkit-overflow-scrolling: touch;
}

.subagent-empty {
  text-align: center;
  padding: 40px 20px;
  color: var(--text3);
}

.subagent-empty p {
  font-size: 15px;
  margin: 0 0 4px;
  color: var(--text2);
}

.subagent-empty span {
  font-size: 13px;
}

/* 列表项 */
.subagent-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 8px;
  border-radius: 12px;
  cursor: pointer;
  transition: background 0.15s;
  border-bottom: 0.5px solid var(--border);
}

.subagent-item:last-child {
  border-bottom: none;
}

.subagent-item:active {
  background: var(--surface2);
}

.subagent-item.disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* 图标 */
.subagent-icon {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

/* 智能体类型颜色 */
.type-explore { background: rgba(14, 165, 233, 0.15); color: #0ea5e9; }
.type-librarian { background: rgba(99, 102, 241, 0.15); color: #6366f1; }
.type-oracle { background: rgba(168, 85, 247, 0.15); color: #a855f7; }
.type-build { background: rgba(245, 158, 11, 0.15); color: #f59e0b; }
.type-quick { background: rgba(34, 197, 94, 0.15); color: #22c55e; }
.type-deep { background: rgba(236, 72, 153, 0.15); color: #ec4899; }
.type-visual-engineering { background: rgba(59, 130, 246, 0.15); color: #3b82f6; }
.type-writing { background: rgba(20, 184, 166, 0.15); color: #14b8a6; }
.type-git { background: rgba(239, 68, 68, 0.15); color: #ef4444; }
.type-vue-best-practices { background: rgba(16, 185, 129, 0.15); color: #10b981; }
.type-bash { background: rgba(100, 116, 139, 0.15); color: #64748b; }

/* 信息 */
.subagent-info {
  flex: 1;
  min-width: 0;
}

.subagent-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.subagent-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 2px;
}

.subagent-type {
  font-size: 11px;
  color: var(--text3);
  font-family: 'SF Mono', 'Consolas', monospace;
}

.subagent-status {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 4px;
  font-weight: 500;
}

.subagent-status.completed {
  background: rgba(52, 199, 89, 0.15);
  color: #34c759;
}

.subagent-status.running {
  background: rgba(10, 132, 255, 0.15);
  color: #0a84ff;
}

.subagent-status.failed,
.subagent-status.error {
  background: rgba(255, 69, 58, 0.15);
  color: #ff453a;
}

/* 箭头 */
.subagent-chevron {
  color: var(--text3);
  flex-shrink: 0;
}

.subagent-nosession {
  font-size: 12px;
  color: var(--text3);
}

/* 过渡动画 */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.25s ease;
}

.fade-enter-active .subagent-panel,
.fade-leave-active .subagent-panel {
  transition: transform 0.25s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.fade-enter-from .subagent-panel {
  transform: translateY(100%);
}

.fade-leave-to .subagent-panel {
  transform: translateY(100%);
}

/* PC 端适配 */
@media (min-width: 768px) {
  .subagent-overlay {
    align-items: center;
  }

  .subagent-panel {
    max-width: 420px;
    max-height: 60vh;
    border-radius: 16px;
    margin: 0;
  }
}
</style>
