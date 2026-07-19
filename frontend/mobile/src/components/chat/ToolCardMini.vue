<template>
  <div class="tool-card-mini" :class="[tool.name || 'default', { expanded: _expanded }]">
    <!-- 头部 (所有工具通用: 图标+名称+状态+展开按钮) -->
    <div class="tcm-header" @click="toggle">
      <!-- 工具类型图标 -->
      <span class="tcm-icon" v-html="toolIcon"></span>
      <span class="tcm-name">{{ headerName }}</span>
      <span class="tcm-status" :class="status"></span>
      <span class="tcm-chevron">
        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><polyline points="6 9 12 15 18 9"/></svg>
      </span>
    </div>

    <!-- 体部 (按工具类型定制) - 用 v-if 控制展开 -->
    <div class="tcm-body" v-if="_expanded">
      <!-- === bash === -->
      <template v-if="tool.name === 'bash'">
        <div class="tool-bash-cmd">$ {{ bashCommand }}</div>
        <div v-if="tool.output" class="tool-bash-output"><pre>{{ bashOutput }}</pre></div>
        <div class="tool-exit-code" :class="{ success: exitCode === 0 || isNaN(exitCode), error: exitCode !== 0 && !isNaN(exitCode) }">退出码: {{ isNaN(exitCode) ? '-' : exitCode }}</div>
      </template>

      <!-- === read === -->
      <template v-else-if="tool.name === 'read'">
        <div class="tool-file-path">{{ filePath }}</div>
        <div v-if="fileLines" class="tool-file-meta">{{ fileLines }} 行</div>
        <pre v-if="filePreview" class="tool-file-preview"><code>{{ filePreview }}</code></pre>
      </template>

      <!-- === write / wrote === -->
      <template v-else-if="tool.name === 'write' || tool.name === 'wrote'">
        <div class="tool-file-path">{{ filePath }}</div>
        <div v-if="writeLines" class="tool-file-meta">{{ writeLines }} 行写入</div>
        <pre v-if="writePreview" class="tool-file-preview"><code>{{ writePreview }}</code></pre>
      </template>

      <!-- === edit === -->
      <template v-else-if="tool.name === 'edit'">
        <div class="tool-file-path">{{ editFilePath }}</div>
        <div v-if="diffLines.length > 0" class="tool-diff unified">
          <div v-for="(line, i) in diffLines" :key="i" class="diff-row" :class="line.type">
            <span class="diff-marker">{{ line.type === 'remove' ? '-' : line.type === 'add' ? '+' : ' ' }}</span>
            <pre class="diff-code"><code>{{ line.text }}</code></pre>
          </div>
        </div>
      </template>

      <!-- === glob === -->
      <template v-else-if="tool.name === 'glob'">
        <div class="tool-glob-pattern">{{ globPattern }}</div>
        <div v-if="globCount !== null" class="tool-file-meta">共 {{ globCount }} 个文件</div>
        <div v-if="globFiles.length > 0" class="tool-file-list">
          <div v-for="(f, i) in globFiles" :key="i" class="tool-file-item">{{ f }}</div>
          <div v-if="globFiles.length < (globCount || 0)" class="tool-file-more">...还有 {{ (globCount || 0) - globFiles.length }} 个</div>
        </div>
      </template>

      <!-- === grep === -->
      <template v-else-if="tool.name === 'grep'">
        <div class="tool-grep-pattern">搜索 '{{ grepPattern }}'</div>
        <div v-if="grepCount !== null" class="tool-file-meta">共 {{ grepCount }} 处匹配</div>
        <div v-if="grepMatches.length > 0" class="tool-grep-matches">
          <div v-for="(m, i) in grepMatches" :key="i" class="tool-grep-item"><pre><code>{{ m }}</code></pre></div>
          <div v-if="grepMatches.length < (grepCount || 0)" class="tool-file-more">...还有 {{ (grepCount || 0) - grepMatches.length }} 处</div>
        </div>
      </template>

      <!-- === task === -->
      <template v-else-if="tool.name === 'task'">
        <div class="tool-task-agent">智能体: {{ taskAgentType }}</div>
        <div v-if="taskDescription" class="tool-task-desc">{{ taskDescription }}</div>
        <div v-if="tool.output" class="tool-task-output tool-default-output"><pre>{{ truncatedOutput }}</pre></div>
      </template>

      <!-- === send_notification / screen-mcp_send_notification === -->
      <template v-else-if="tool.name === 'screen-mcp_send_notification'">
        <div class="tool-notif-title">{{ notifTitle }}</div>
        <div v-if="notifContent" class="tool-notif-content">{{ notifContent }}</div>
      </template>

      <!-- === tts / screen-mcp_tts_speak === -->
      <template v-else-if="tool.name === 'screen-mcp_tts_speak'">
        <div class="tool-tts-text">{{ ttsSpokenText }}</div>
      </template>

      <!-- === webfetch === -->
      <template v-else-if="tool.name === 'webfetch'">
        <div class="tool-web-url">{{ webUrl }}</div>
        <div v-if="webStatus" class="tool-file-meta">HTTP {{ webStatus }}</div>
        <pre v-if="tool.output" class="tool-web-preview"><code>{{ truncatedOutput }}</code></pre>
      </template>

      <!-- === question / ask_user === -->
      <template v-else-if="tool.name === 'question' || tool.name === 'ask_user'">
        <div class="tool-question">问题: {{ questionText }}</div>
      </template>

      <!-- === default: 通用 JSON + 输出 === -->
      <template v-else>
        <div v-if="argsPreview" class="tcm-label">参数</div>
        <pre v-if="argsPreview"><code>{{ argsPreview }}</code></pre>
        <div v-if="tool.output" class="tcm-label">输出</div>
        <pre v-if="tool.output"><code>{{ truncatedOutput }}</code></pre>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

export interface ToolCall {
  id: string
  name: string
  args: Record<string, unknown> | string
  status: string
  output?: string
}

const props = defineProps<{
  tool: ToolCall
  status: 'running' | 'completed' | 'error'
  expanded?: boolean
}>()

/** 是否默认展开 (按工具类型) */
function isDefaultExpanded(): boolean {
  const name = props.tool.name
  // 默认展开: bash/write/wrote/edit/tts/通知
  if (name === 'bash' || name === 'write' || name === 'wrote' || name === 'edit') return true
  if (name === 'screen-mcp_tts_speak' || name === 'screen-mcp_send_notification') return true
  // 有实际 params 内容的工具默认展开
  const a = props.tool.args as Record<string, unknown> | undefined
  if (a?.params && typeof a.params === 'object') {
    const p = a.params as Record<string, unknown>
    if (p.text || p.content || p.title) return true
  }
  // 默认折叠: read/glob/grep/webfetch/question/task 及其他
  return false
}

/** 展开状态 */
const _expanded = ref(isDefaultExpanded())

/** 切换展开/折叠 */
function toggle() {
  _expanded.value = !_expanded.value
}

// ==================== 通用计算属性 ====================

const truncatedOutput = computed<string>(() => {
  const output = props.tool.output || ''
  if (output.length <= 500) return output
  return output.slice(0, 500) + '...'
})

const argsPreview = computed<string>(() => {
  const args = props.tool.args
  if (!args) return ''
  if (typeof args === 'string') return args
  try {
    return JSON.stringify(args, null, 2)
  } catch {
    return String(args)
  }
})

// ==================== 工具图标 ====================

const toolIcon = computed<string>(() => {
  const name = props.tool.name || ''
  // terminal
  if (name === 'bash') return '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>'
  // file
  if (name === 'read' || name === 'write' || name === 'wrote') return '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>'
  // edit / diff
  if (name === 'edit') return '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>'
  // folder
  if (name === 'glob' || name === 'grep') return '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>'
  // robot
  if (name === 'task') return '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>'
  // globe
  if (name === 'webfetch') return '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>'
  // speaker (TTS)
  if (name === 'screen-mcp_tts_speak') return '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"/></svg>'
  // bell (notification)
  if (name === 'screen-mcp_send_notification') return '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>'
  // help-circle
  if (name === 'question' || name === 'ask_user') return '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>'
  // wrench (default)
  return '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>'
})

// ==================== 头部摘要 ====================

const headerName = computed<string>(() => {
  const name = props.tool.name || ''
  if (name === 'bash') return bashCommand.value || 'bash'
  if (name === 'read' || name === 'write' || name === 'wrote') return filePath.value || name
  if (name === 'edit') return editFilePath.value || 'edit'
  if (name === 'glob') return globPattern.value || 'glob'
  if (name === 'grep') return `搜索 '${grepPattern.value}'` || 'grep'
  if (name === 'task') return taskAgentType.value || 'task'
  if (name === 'webfetch') return webUrl.value || 'webfetch'
  if (name === 'screen-mcp_tts_speak') return '语音消息'
  if (name === 'screen-mcp_send_notification') return '系统通知'
  if (name === 'question' || name === 'ask_user') return '提问'
  return name
})

// ==================== bash ====================

const bashCommand = computed<string>(() => {
  const args = props.tool.args
  let cmd = ''
  if (typeof args === 'string') cmd = args
  else if (args && typeof args === 'object') {
    cmd = (args as Record<string, string>).command || (args as Record<string, string>).cmd || ''
  }
  // 过滤 AI 自动添加的环境变量前缀（只过滤已知的沙箱变量）
  const knownEnvVars = [
    'CI', 'DEBIAN_FRONTEND', 'GIT_TERMINAL_PROMPT', 'GCM_INTERACTIVE',
    'HOMEBREW_NO_AUTO_UPDATE', 'GIT_EDITOR', 'EDITOR', 'VISUAL',
    'GIT_SEQUENCE_EDITOR', 'GIT_MERGE_AUTOEDIT', 'GIT_PAGER', 'PAGER',
    'npm_config_yes', 'PIP_NO_INPUT', 'YARN_ENABLE_IMMUTABLE_INSTALLS',
  ]
  const envPattern = knownEnvVars.map((v) => "\\$env:" + v + "='(?:[^'\\\\]|\\\\.)*';\\s*").join('|')
  const regex = new RegExp('^(?:' + envPattern + ')+', 'g')
  return cmd.replace(regex, '').trim()
})

const bashOutput = computed<string>(() => {
  const out = props.tool.output || ''
  return out.length > 300 ? out.slice(0, 300) + '...' : out
})

const exitCode = computed<number>(() => {
  const status = props.tool.status
  if (status === 'error') return 1
  if (status === 'completed') return 0
  return NaN
})

// ==================== read / write ====================

const filePath = computed<string>(() => {
  const args = props.tool.args
  if (typeof args === 'string') return args
  if (args && typeof args === 'object') {
    return (args as Record<string, string>).filePath || (args as Record<string, string>).path || ''
  }
  return ''
})

const fileLines = computed<string>(() => {
  const out = props.tool.output
  if (!out) return ''
  const lines = out.split('\n').length
  return `${lines}`
})

const filePreview = computed<string>(() => {
  const out = props.tool.output
  if (!out) return ''
  const lines = out.split('\n')
  return lines.slice(0, 20).join('\n') + (lines.length > 20 ? '\n...' : '')
})

const writeLines = computed<string>(() => {
  const args = props.tool.args
  if (typeof args === 'string') return ''
  const content = args && typeof args === 'object' ? (args as Record<string, string>).content : ''
  if (!content) return ''
  return `${content.split('\n').length}`
})

const writePreview = computed<string>(() => {
  const args = props.tool.args
  if (typeof args === 'string') return ''
  const content = args && typeof args === 'object' ? (args as Record<string, string>).content || '' : ''
  const lines = content.split('\n')
  return lines.slice(0, 20).join('\n') + (lines.length > 20 ? '\n...' : '')
})

// ==================== edit ====================

const editFilePath = computed<string>(() => filePath.value)

const editOldStr = computed<string>(() => {
  const args = props.tool.args
  if (typeof args === 'string') return ''
  if (args && typeof args === 'object') {
    return (args as Record<string, string>).oldString || ''
  }
  return ''
})

const editNewStr = computed<string>(() => {
  const args = props.tool.args
  if (typeof args === 'string') return ''
  if (args && typeof args === 'object') {
    return (args as Record<string, string>).newString || ''
  }
  return ''
})

/** 行级 diff: 对比 old/new, 生成 { type, text }[] */
interface DiffLine { type: 'add' | 'remove' | 'context'; text: string }
const diffLines = computed<DiffLine[]>(() => {
  const oldStr = editOldStr.value
  const newStr = editNewStr.value
  if (!oldStr && !newStr) return []
  if (!oldStr) return [{ type: 'add', text: newStr }]
  if (!newStr) return [{ type: 'remove', text: oldStr }]

  const oldLines = oldStr.split('\n')
  const newLines = newStr.split('\n')
  const result: DiffLine[] = []

  // 找公共前缀行数
  let prefixEnd = 0
  while (
    prefixEnd < oldLines.length &&
    prefixEnd < newLines.length &&
    oldLines[prefixEnd] === newLines[prefixEnd]
  ) {
    prefixEnd++
  }

  // 找公共后缀行数
  let suffixStartOld = oldLines.length
  let suffixStartNew = newLines.length
  while (
    suffixStartOld > prefixEnd &&
    suffixStartNew > prefixEnd &&
    oldLines[suffixStartOld - 1] === newLines[suffixStartNew - 1]
  ) {
    suffixStartOld--
    suffixStartNew--
  }

  // 公共前缀: 白色
  for (let i = 0; i < prefixEnd; i++) {
    result.push({ type: 'context', text: oldLines[i] })
  }

  // 差异中间: 旧行红色(-), 新行绿色(+)
  for (let i = prefixEnd; i < suffixStartOld; i++) {
    result.push({ type: 'remove', text: oldLines[i] })
  }
  for (let i = prefixEnd; i < suffixStartNew; i++) {
    result.push({ type: 'add', text: newLines[i] })
  }

  // 公共后缀: 白色
  for (let i = suffixStartOld; i < oldLines.length; i++) {
    result.push({ type: 'context', text: oldLines[i] })
  }

  return result
})

// ==================== glob ====================

const globPattern = computed<string>(() => {
  const args = props.tool.args
  if (typeof args === 'string') return args
  if (args && typeof args === 'object') {
    return (args as Record<string, string>).pattern || ''
  }
  return ''
})

const globCount = computed<number | null>(() => {
  const out = props.tool.output
  if (!out) return null
  return out.split('\n').length
})

const globFiles = computed<string[]>(() => {
  const out = props.tool.output
  if (!out) return []
  return out.split('\n').slice(0, 10)
})

// ==================== grep ====================

const grepPattern = computed<string>(() => {
  const args = props.tool.args
  if (typeof args === 'string') return args
  if (args && typeof args === 'object') {
    return (args as Record<string, string>).pattern || ''
  }
  return ''
})

const grepCount = computed<number | null>(() => {
  const out = props.tool.output
  if (!out) return null
  const trimmed = out.trim()
  if (!trimmed) return null
  return out.split('\n').length
})

const grepMatches = computed<string[]>(() => {
  const out = props.tool.output
  if (!out) return []
  return out.split('\n').slice(0, 5)
})

// ==================== task ====================

const taskAgentType = computed<string>(() => {
  const args = props.tool.args
  if (typeof args === 'string') return args
  if (args && typeof args === 'object') {
    const a = args as Record<string, unknown>
    return (a.subagent_type as string) || (a.category as string) || (a.name as string) || 'sub-agent'
  }
  return 'sub-agent'
})

const taskDescription = computed<string>(() => {
  const args = props.tool.args
  if (typeof args === 'string') return ''
  if (args && typeof args === 'object') {
    return (args as Record<string, string>).description || (args as Record<string, string>).prompt || ''
  }
  return ''
})

// ==================== send_notification / screen-mcp_send_notification ====================

/** 从工具 args 提取通知标题 (实际结构: { params: { title, content } }) */
const notifTitle = computed<string>(() => {
  const a = props.tool.args as Record<string, unknown> | undefined
  if (!a) return '系统通知'
  // params 层
  const params = a.params as Record<string, string> | undefined
  if (params?.title) return params.title
  // 直接层
  if (typeof a.title === 'string') return a.title
  return '系统通知'
})

/** 从工具 args 提取通知内容 (实际结构: { params: { title, content } }) */
const notifContent = computed<string>(() => {
  const a = props.tool.args as Record<string, unknown> | undefined
  if (!a) return ''
  // params 层
  const params = a.params as Record<string, string> | undefined
  if (params?.content) return params.content
  // 直接层
  if (typeof a.content === 'string') return a.content
  if (typeof a.message === 'string') return a.message
  // 报错: 从 output 兜底
  const out = props.tool.output || ''
  if (!out) return ''
  const match = out.match(/通知已发送:\s*(.+)/)
  if (match) return match[1]
  return out
})

// ==================== webfetch ====================

const webUrl = computed<string>(() => {
  const args = props.tool.args
  if (typeof args === 'string') return args
  if (args && typeof args === 'object') {
    const url = (args as Record<string, string>).url || ''
    return url.length > 60 ? url.slice(0, 60) + '...' : url
  }
  return ''
})

const webStatus = computed<string>(() => {
  const out = props.tool.output
  if (!out) return ''
  const match = out.match(/HTTP\/\d\.\d\s+(\d+)/)
  return match ? match[1] : ''
})

// ==================== question ====================

const questionText = computed<string>(() => {
  const args = props.tool.args
  if (typeof args === 'string') return args
  if (args && typeof args === 'object') {
    return (args as Record<string, string>).question || (args as Record<string, string>).text || ''
  }
  return ''
})

// ==================== tts / screen-mcp_tts_speak ====================

/** 从工具 args 提取 TTS 播报的文字，报错/空时从 output 兜底 */
const ttsSpokenText = computed<string>(() => {
  // 优先从 args 拿 (实际结构: { params: { text: "..." } })
  if (props.tool.args && typeof props.tool.args === 'object') {
    const a = props.tool.args as Record<string, unknown>
    // 第一层: params
    const params = a.params as Record<string, string> | undefined
    if (params?.text) return params.text
    // 第二层: 直接 text/tts/content
    const text = a.text || a.tts || a.content || ''
    if (text && typeof text === 'string') return text
  }
  // 报错: 从 output 兜底
  const out = props.tool.output || ''
  if (!out) return ''
  try {
    const parsed = JSON.parse(out)
    const result = parsed.result || ''
    const prefix = 'TTS语音已成功发送:'
    const idx = result.indexOf(prefix)
    if (idx >= 0) {
      let text = result.slice(idx + prefix.length).trim()
      text = text.replace(/^"/, '').replace(/"$/, '')
      text = text.replace(/\\"/g, '"')
      return text
    }
    return result
  } catch {
    return out
  }
})
</script>

<style scoped>
.tool-card-mini {
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 6px 10px;
  margin: 6px 0;
  background: var(--surface);
}

.tcm-header {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  user-select: none;
}

.tcm-icon {
  color: var(--primary-light);
  font-size: 12px;
  width: 16px;
  height: 14px;
  text-align: center;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.tcm-name {
  flex: 1;
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tcm-chevron {
  color: var(--text3);
  display: flex;
  align-items: center;
  transition: transform 0.2s;
}

.tool-card-mini.expanded .tcm-chevron {
  transform: rotate(180deg);
}

.tcm-body {
  display: none;
  margin-top: 6px;
  padding-top: 6px;
  border-top: 1px solid var(--border);
  font-size: 12px;
}

.tool-card-mini.expanded .tcm-body {
  display: block;
}

.tcm-body pre {
  background: var(--surface2);
  padding: 8px;
  border-radius: 6px;
  overflow-x: auto;
  margin: 4px 0;
  font-size: 11px;
  max-height: 300px;
  overflow-y: auto;
}

.tcm-body pre code {
  background: none;
  padding: 0;
}

.tcm-label {
  font-size: 10px;
  color: var(--text3);
  margin: 6px 0 2px;
  font-weight: 600;
}

/* 状态指示点 */
.tcm-status {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  display: inline-block;
  flex-shrink: 0;
}

.tcm-status.running {
  background: var(--accent3);
  animation: pulse 1.5s infinite;
}

.tcm-status.completed {
  background: var(--accent);
}

.tcm-status.error {
  background: var(--danger);
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

/* ==================== bash ==================== */
.tool-bash-cmd {
  font-family: monospace;
  font-size: 12px;
  color: var(--text);
  background: var(--surface2);
  padding: 6px 8px;
  border-radius: 4px;
  margin-bottom: 4px;
  white-space: pre-wrap;
  word-break: break-all;
}
.tool-bash-output {
  margin: 4px 0;
}
.tool-exit-code {
  display: inline-block;
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 3px;
  font-weight: 600;
}
.tool-exit-code.success {
  background: rgba(52, 199, 89, 0.15);
  color: #34c759;
}
.tool-exit-code.error {
  background: rgba(255, 69, 58, 0.15);
  color: #ff453a;
}

/* ==================== read / write ==================== */
.tool-file-path {
  font-family: monospace;
  font-size: 11px;
  color: var(--text2);
  margin-bottom: 4px;
}
.tool-file-meta {
  font-size: 10px;
  color: var(--text3);
  margin-bottom: 4px;
}
.tool-file-preview {
  max-height: 200px !important;
  font-size: 11px;
}
.tool-file-more {
  font-size: 10px;
  color: var(--text3);
  font-style: italic;
  margin-top: 4px;
}

/* ==================== edit (unified diff) ==================== */
.tool-diff.unified {
  border: 1px solid var(--border);
  border-radius: 6px;
  overflow: auto;
  font-size: 12px;
  max-height: 300px;
}
.diff-row {
  display: flex;
  align-items: stretch;
}
.diff-marker {
  width: 18px;
  min-height: 100%;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 2px 0;
  font-family: monospace;
  font-size: 11px;
  font-weight: 700;
  flex-shrink: 0;
  user-select: none;
  opacity: 0.5;
  line-height: 1.3;
}
/* 无变化: 白色/灰色文字 */
.diff-row.context {
  background: transparent;
}
.diff-row.context .diff-marker {
  color: var(--text3);
}
.diff-row.context .diff-code code {
  color: var(--text2) !important;
}
/* 删除: 红色背景 + 红色 - 号 */
.diff-row.remove {
  background: rgba(255, 69, 58, 0.08);
}
.diff-row.remove .diff-marker {
  color: #ff453a;
  opacity: 1;
}
/* 添加: 绿色背景 + 绿色 + 号 */
.diff-row.add {
  background: rgba(52, 199, 89, 0.08);
}
.diff-row.add .diff-marker {
  color: #34c759;
  opacity: 1;
}
.diff-row + .diff-row {
  border-top: 0.5px solid var(--border);
}
.diff-code {
  flex: 1;
  margin: 0 !important;
  padding: 2px 6px !important;
  border-radius: 0 !important;
  border: none !important;
  background: transparent !important;
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.3;
}

/* ==================== glob / grep ==================== */
.tool-glob-pattern,
.tool-grep-pattern {
  font-family: monospace;
  font-size: 12px;
  color: var(--text);
  margin-bottom: 4px;
}
.tool-file-list,
.tool-grep-matches {
  max-height: 200px;
  overflow-y: auto;
}
.tool-file-item {
  font-family: monospace;
  font-size: 11px;
  color: var(--text2);
  padding: 1px 0;
}
.tool-grep-item pre {
  margin: 2px 0;
}

/* ==================== task ==================== */
.tool-task-agent {
  font-size: 12px;
  font-weight: 600;
  color: var(--primary);
  margin-bottom: 4px;
}
.tool-task-desc {
  font-size: 11px;
  color: var(--text2);
  margin-bottom: 4px;
  line-height: 1.4;
}

/* ==================== webfetch ==================== */
.tool-web-url {
  font-family: monospace;
  font-size: 11px;
  color: var(--primary-light);
  margin-bottom: 4px;
  word-break: break-all;
}
.tool-web-preview {
  max-height: 200px !important;
}

/* ==================== question ==================== */
.tool-question {
  font-size: 12px;
  color: var(--text);
  padding: 4px 0;
  line-height: 1.4;
}

/* ==================== tts / screen-mcp_tts_speak ==================== */
.tool-tts-text {
  font-size: 13px;
  color: var(--text);
  padding: 4px 0;
  line-height: 1.5;
  font-style: italic;
}
.tool-tts-text::before {
  content: '\201C';
  color: var(--primary-light);
  font-size: 16px;
  margin-right: 2px;
}
.tool-tts-text::after {
  content: '\201D';
  color: var(--primary-light);
  font-size: 16px;
  margin-left: 2px;
}

/* ==================== send_notification / screen-mcp_send_notification ==================== */
.tool-notif-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
  margin-bottom: 4px;
}
.tool-notif-content {
  font-size: 12px;
  color: var(--text2);
  line-height: 1.4;
}
</style>
