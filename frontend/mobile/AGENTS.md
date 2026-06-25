# 前端 SPA -- Vue 3 / TypeScript (Android WebView)

## 概览

Axeuh Health Monitor 的手机端界面。运行在 Android App 的 WebView 中，提供 AI 聊天、健康看板、文件浏览、报告查看和系统设置功能。

## 目录结构

```
src/
├── api/               # HTTP 客户端 + 6 个 API 模块
├── components/
│   ├── chat/          # 聊天相关 (ChatInput, MessageBubble, MarkdownContent ...)
│   ├── common/        # 通用组件 (LoginOverlay, PageState, SkeletonLoader ...)
│   ├── dashboard/     # 看板图表 (HrateChart, GpsMapOverlay ...)
│   ├── files/         # 文件浏览 (FileTree, PreviewOverlay ...)
│   ├── nav/           # 底部导航栏 BottomNav
│   ├── reports/       # 报告卡片 + 筛选器
│   └── settings/      # 调试面板 DebugPanel
├── composables/       # 11 个组合式函数 (useChat, useDashboard, useGps ...)
├── types/             # TypeScript 类型定义 (7 文件)
├── utils/             # 工具函数 (纯函数, 只包含 markdown.ts)
├── router/            # hash 模式路由配置
├── styles/            # 5 个 CSS 文件 (变量/基础/动画/组件/主样式)
├── views/             # 5 个页面视图 (Chat/Dashboard/Files/Reports/Settings)
├── App.vue            # 根组件
└── main.ts            # 入口
```

## 约定

- Vue 3 Composition API + `<script setup lang="ts">`，严格 TS 模式
- 无 Pinia/Vuex -- 所有状态由 composables 管理
- Vue Router hash 模式 (`createWebHashHistory`)，路径别名 `@` -> `./src`
- 组件命名: PascalCase，文件与组件名一致
- 组合式函数命名: `useXxx` 驼峰，一个文件一个 composable
- 类型文件按领域拆分 (chat.ts, health.ts, gps.ts ...)，统一从 `types/index.ts` 导出
- API 模块按后端资源拆分: `health.ts`, `session.ts`, `files.ts`, `sse.ts`, `ws.ts`
- CSS 变量全局管理颜色/间距/字体，不写内联样式

## 关键架构

| 决策 | 说明 |
|------|------|
| 自定义 Markdown 渲染器 | `utils/markdown.ts` 自实现，无第三方库，避免 XSS 且兼容流式渲染 |
| 看板双源加载 | 优先 `/api/screen/dashboard` 聚合接口，不可用时回退逐传感器查询 |
| SSE + WebSocket | 双通道实时连接，`useRealTime` 统一管理自动重连和生命周期 |
| Vite 构建 | `base='./'` + `target='es2015'`，兼容 WebView 路径和 JS 引擎 |

## 命令

以下在 `frontend/mobile/` 目录下执行：

```bash
npm run dev           # 开发服务器 (localhost:5173)
npm run build         # vue-tsc 类型检查 + Vite 构建 -> dist/
npm run test:unit     # Vitest 单元测试 (happy-dom)
npm run test:e2e      # Playwright E2E 测试 (chromium)
npm run typecheck     # 仅类型检查，不构建
```

## 注意事项

- `npm run build` 后产物在 `dist/`，后端自动从 `frontend/mobile/dist/` 提供静态文件服务
- Android WebView 访问 URL: `https://<host>:<port>/mobile/`
- 每次修改前端代码后必须 `npm run build`，否则 App 加载的是旧构建产物
- 原始单文件 SPA (约 3950 行) 保留在 `index.original.html` 作为备份
- 所有调试连接用 HTTPS，不要降级到 HTTP
