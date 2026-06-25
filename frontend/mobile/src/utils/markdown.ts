/**
 * 自定义 Markdown 渲染器
 *
 * 匹配 index.original.html 中 renderMarkdown 和 renderObsidianMarkdown 的行为,
 * 合并两者的能力:
 *   - renderMarkdown: 列表分组 (<ul>/<ol>), 代码块语言类, 链接, escapeHtml 前置
 *   - renderObsidianMarkdown: 表格, Obsidian callouts, wiki-links
 * 无第三方依赖.
 */

/** 转义 HTML 特殊字符防止 XSS */
function escapeHtml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
}

/** 转义 HTML 属性中的引号 */
function escapeAttr(s: string): string {
  return String(s).replace(/['"]/g, '')
}

/** 行内格式化: wiki-links, 行内代码, 加粗, 斜体, 链接 */
function inlineFormat(text: string): string {
  return text
    // wiki-links 优先, 避免与 [text](url) 冲突
    .replace(/\[\[([^\]]+?)\]\]/g, (_match: string, p1: string) => {
      const parts = p1.split('|')
      const display = parts[1] || parts[0]
      return (
        '<a class="wiki-link" onclick="alert(\'[[ ' +
        escapeAttr(parts[0]) +
        ' ]]\')">' +
        escapeHtml(display) +
        '</a>'
      )
    })
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2">$1</a>')
}

/**
 * 将 Markdown 文本渲染为安全的 HTML 字符串.
 *
 * 支持的语法:
 *   - 标题: # / ## / ###
 *   - 加粗: **text**
 *   - 斜体: *text*
 *   - 链接: [text](url)
 *   - 无序列表: - item / * item (自动包裹 <ul>)
 *   - 有序列表: 1. item (自动包裹 <ol>)
 *   - 代码块: 三反引号 (可指定语言类)
 *   - 行内代码: `code`
 *   - 引用: > text
 *   - Obsidian callouts: > [!warning] / > [!tip] / > [!abstract] 等
 *   - 表格: | col1 | col2 |  + 分隔行
 *   - 水平线: --- / ***
 *   - Wiki-links: [[link]] / [[link|display]]
 *   - YAML frontmatter 自动剥离
 */
export function renderMarkdown(text: string): string {
  // 1. XSS 保护: 先转义 HTML
  text = escapeHtml(text)

  // 2. 剥离 YAML frontmatter
  text = text.replace(/^---[\s\S]*?---\n*/, '')

  const lines = text.split('\n')
  let html = ''
  let inCode = false
  let codeLang = ''
  const codeLines: string[] = []
  let listType: 'ul' | 'ol' | null = null
  const listItems: string[] = []

  /** 刷新当前列表 (闭合 <ul>/<ol>) */
  function flushList(): void {
    if (listType) {
      html += '<' + listType + '>' + listItems.join('') + '</' + listType + '>'
      listType = null
      listItems.length = 0
    }
  }

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]

    // ── 代码块 ──────────────────────────────────────────
    if (/^```/.test(line)) {
      if (inCode) {
        html +=
          '<pre><code' +
          (codeLang ? ' class="' + codeLang + '"' : '') +
          '>' +
          codeLines.join('\n') +
          '</code></pre>'
        inCode = false
        codeLang = ''
        codeLines.length = 0
      } else {
        inCode = true
        codeLang = line.slice(3).trim()
      }
      continue
    }
    if (inCode) {
      codeLines.push(line)
      continue
    }

    // ── 关闭已打开的列表 ───────────────────────────────
    if (listType) {
      const isListItem = /^(\d+\.\s|[-*+]\s)/.test(line)
      if (!isListItem) {
        flushList()
      }
    }

    // ── 空行 ─────────────────────────────────────────────
    if (!line.trim()) {
      html += '<br>'
      continue
    }

    // ── 表格: 检测 |...| 表头 + 下一行 |---|---| 分隔 ──
    if (
      /^\|.+/.test(line) &&
      /\|$/.test(line) &&
      i + 1 < lines.length &&
      /^\|[-:\s|]+\|$/.test(lines[i + 1])
    ) {
      let tableHtml = '<table><thead><tr>'
      line
        .split('|')
        .filter((c) => c.trim() !== '')
        .forEach((cell) => {
          tableHtml += '<th>' + inlineFormat(cell.trim()) + '</th>'
        })
      tableHtml += '</tr></thead><tbody>'
      i++ // 跳过分隔行
      i++ // 移动到第一个数据行
      while (i < lines.length) {
        const dataLine = lines[i]
        if (!/^\|/.test(dataLine)) {
          i--
          break
        }
        tableHtml += '<tr>'
        dataLine
          .split('|')
          .filter((c) => c.trim() !== '')
          .forEach((cell) => {
            tableHtml += '<td>' + inlineFormat(cell.trim()) + '</td>'
          })
        tableHtml += '</tr>'
        i++
      }
      html += tableHtml + '</tbody></table>'
      continue
    }

    // ── Obsidian callouts ──────────────────────────────
    const calloutMatch = line.match(/^>\s*\[!(\w+)\]\s*(.*)/i)
    if (calloutMatch) {
      const calloutType = calloutMatch[1].toLowerCase()
      const calloutTitle = calloutMatch[2] || calloutType
      html +=
        '<div class="callout callout-' +
        calloutType +
        '"><div class="callout-title">' +
        escapeHtml(calloutTitle) +
        '</div><div class="callout-body">'
      i++
      while (i < lines.length && lines[i].startsWith('>')) {
        html += '<p>' + inlineFormat(lines[i].replace(/^>\s*/, '')) + '</p>'
        i++
      }
      html += '</div></div>'
      i--
      continue
    }

    // ── 普通 blockquote ─────────────────────────────────
    if (line.startsWith('>')) {
      html +=
        '<blockquote>' + inlineFormat(line.replace(/^>\s*/, '')) + '</blockquote>'
      continue
    }

    // ── 水平线 ───────────────────────────────────────────
    if (/^---+\s*$/.test(line) || /^\*\*\*+\s*$/.test(line)) {
      html += '<hr>'
      continue
    }

    // ── 标题 h1 / h2 / h3 ──────────────────────────────
    if (/^#{1,3}\s/.test(line)) {
      const level = line.match(/^#+/)![0].length
      const title = line.replace(/^#+\s*/, '')
      html += '<h' + level + '>' + inlineFormat(title) + '</h' + level + '>'
      continue
    }

    // ── 无序列表 ────────────────────────────────────────
    const ulMatch = line.match(/^[-*+]\s(.+)/)
    if (ulMatch) {
      if (listType !== 'ul') {
        flushList()
        listType = 'ul'
      }
      listItems.push('<li>' + inlineFormat(ulMatch[1]) + '</li>')
      continue
    }

    // ── 有序列表 ────────────────────────────────────────
    const olMatch = line.match(/^\d+\.\s(.+)/)
    if (olMatch) {
      if (listType !== 'ol') {
        flushList()
        listType = 'ol'
      }
      listItems.push('<li>' + inlineFormat(olMatch[1]) + '</li>')
      continue
    }

    // ── 普通段落 ────────────────────────────────────────
    html += '<p>' + inlineFormat(line) + '</p>'
  }

  // ── 收尾: 闭合未关闭的结构 ─────────────────────────
  flushList()
  if (inCode) {
    html += '<pre><code>' + codeLines.join('\n') + '</code></pre>'
  }

  return html
}
