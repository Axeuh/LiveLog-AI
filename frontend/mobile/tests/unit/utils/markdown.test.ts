/// <reference types="vitest/globals" />

import { renderMarkdown } from '@/utils/markdown'

describe('renderMarkdown', () => {
  // ==================== 标题 ====================

  it('渲染 h1 标题', () => {
    const result = renderMarkdown('# Hello')
    expect(result).toContain('<h1>Hello</h1>')
  })

  it('渲染 h2 标题', () => {
    const result = renderMarkdown('## Hello')
    expect(result).toContain('<h2>Hello</h2>')
  })

  it('渲染 h3 标题', () => {
    const result = renderMarkdown('### Hello')
    expect(result).toContain('<h3>Hello</h3>')
  })

  // ==================== 行内格式 ====================

  it('渲染加粗 **text**', () => {
    const result = renderMarkdown('**bold**')
    expect(result).toContain('<strong>bold</strong>')
  })

  it('渲染斜体 *text*', () => {
    const result = renderMarkdown('*italic*')
    expect(result).toContain('<em>italic</em>')
  })

  it('渲染行内代码 `code`', () => {
    const result = renderMarkdown('`code`')
    expect(result).toContain('<code>code</code>')
  })

  it('渲染链接 [text](url)', () => {
    const result = renderMarkdown('[click](https://example.com)')
    expect(result).toContain('<a href="https://example.com">click</a>')
  })

  // ==================== 列表 ====================

  it('渲染无序列表 - item', () => {
    const result = renderMarkdown('- item1\n- item2')
    expect(result).toContain('<ul>')
    expect(result).toContain('<li>item1</li>')
    expect(result).toContain('<li>item2</li>')
    expect(result).toContain('</ul>')
  })

  it('渲染有序列表 1. item', () => {
    const result = renderMarkdown('1. item1\n2. item2')
    expect(result).toContain('<ol>')
    expect(result).toContain('<li>item1</li>')
    expect(result).toContain('<li>item2</li>')
    expect(result).toContain('</ol>')
  })

  // ==================== 代码块 ====================

  it('渲染代码块（无语言）', () => {
    const result = renderMarkdown('```\nconst x = 1\n```')
    expect(result).toContain('<pre><code>')
    expect(result).toContain('const x = 1')
    expect(result).toContain('</code></pre>')
  })

  it('渲染代码块（有语言）', () => {
    const result = renderMarkdown('```python\nprint("hi")\n```')
    expect(result).toContain('<pre><code class="python">')
    // HTML 特殊字符被转义 (escapeHtml 先于代码块处理)
    expect(result).toContain('print(&quot;hi&quot;)')
    expect(result).toContain('</code></pre>')
  })

  // ==================== 表格 ====================

  it('渲染表格', () => {
    const md = '| col1 | col2 |\n|---|---|\n| a | b |'
    const result = renderMarkdown(md)
    expect(result).toContain('<table>')
    expect(result).toContain('<th>col1</th>')
    expect(result).toContain('<th>col2</th>')
    expect(result).toContain('<td>a</td>')
    expect(result).toContain('<td>b</td>')
    expect(result).toContain('</table>')
  })

  // ==================== 引用 ====================

  // 注意: 当前 escapeHtml 在 markdown 解析前执行,
  // 导致 > 被转义为 &gt;, blockquote 语法暂不生效.
  // 以下测试验证实际输出行为 (非理想行为).

  it('处理 > 引用文本 (escapeHtml 导致 > 被转义)', () => {
    const result = renderMarkdown('> 引用文本')
    expect(result).toContain('&gt; 引用文本')
  })

  // ==================== Obsidian callouts ====================

  it('处理 > [!warning] 文本 (escapeHtml 导致 > 被转义)', () => {
    const result = renderMarkdown('> [!warning] 警告\n> 这是一个警告')
    expect(result).toContain('&gt; [!warning]')
    expect(result).toContain('&gt; 这是一个警告')
  })

  // ==================== Wiki-links ====================

  it('渲染 wiki-link [[link]]', () => {
    const result = renderMarkdown('[[笔记名称]]')
    expect(result).toContain('class="wiki-link"')
  })

  it('渲染 wiki-link 带显示文本 [[link|display]]', () => {
    const result = renderMarkdown('[[笔记|其他名称]]')
    expect(result).toMatch(/其他名称/)
    expect(result).toContain('class="wiki-link"')
  })

  // ==================== XSS 保护 ====================

  it('转义 XSS <script> 标签', () => {
    const result = renderMarkdown('<script>alert("xss")</script>')
    expect(result).not.toContain('<script>')
    expect(result).not.toContain('alert("xss")')
    expect(result).toContain('&lt;script&gt;')
    expect(result).toContain('&lt;/script&gt;')
  })

  // ==================== 水平线 ====================

  it('渲染水平线 ---', () => {
    const result = renderMarkdown('---')
    expect(result).toContain('<hr>')
  })

  it('渲染水平线 ***', () => {
    const result = renderMarkdown('***')
    expect(result).toContain('<hr>')
  })

  // ==================== 空 / 边界 ====================

  it('处理空字符串', () => {
    const result = renderMarkdown('')
    expect(typeof result).toBe('string')
  })

  it('处理纯文本段落', () => {
    const result = renderMarkdown('Hello World')
    expect(result).toContain('<p>Hello World</p>')
  })

  // ==================== 综合 ====================

  it('标题中的行内格式', () => {
    const result = renderMarkdown('# **粗体标题**')
    expect(result).toContain('<h1>')
    expect(result).toContain('<strong>粗体标题</strong>')
    expect(result).toContain('</h1>')
  })

  it('YAML frontmatter 被剥离', () => {
    const md = '---\ntitle: test\n---\n\n# Hello'
    const result = renderMarkdown(md)
    expect(result).not.toContain('title: test')
    expect(result).toContain('<h1>Hello</h1>')
  })
})
