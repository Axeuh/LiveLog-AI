# Axeuh Health Monitor - 手机端 WebView 界面

基于 Vue 3 + Vite + TypeScript 构建的移动端单页应用 (SPA)，运行于 Android WebView 中，为用户提供 Axeuh Health Monitor 系统的交互界面。

---

## 项目概述

本项目是 Axeuh Health Monitor 健康监测系统的手机端前端界面。原始版本是一个约 3950 行的单文件 SPA（`index.original.html`），已完整迁移为模块化的 Vue 3 + Vite + TypeScript 架构。

用户通过 Android App 内的 WebView 加载此界面，实现与后端 AI 服务的交互，包括实时聊天、健康看板、文件浏览、报告查看和系统设置等功能。

---

## 技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| Vue 3 | ^3.5.0 | 前端框架 (Composition API + `<script setup>`) |
| Vite | ^6.3.0 | 构建工具 |
| TypeScript | ~5.7.0 | 类型系统 (strict 模式) |
| Vue Router | ^4.5.0 | 路由 (hash 模式) |
| Chart.js | ^4.4.0 | 图表渲染 (心率/血氧/压力/步数/睡眠/电量) |
| Leaflet | ^1.9.4 | GPS 轨迹地图展示 |
| Vitest | ^3.1.0 | 单元测试框架 |
| Playwright | ^1.52.0 | E2E 测试框架 |
| vue-tsc | ^2.2.0 | Vue TypeScript 类型检查 |
| happy-dom | ^17.0.0 | Vitest DOM 环境 |

严格模式配置（`tsconfig.app.json`）：
- `strict: true` -- 完整严格模式
- `noUnusedLocals: true` -- 禁止未使用的局部变量
- `noUnusedParameters: true` -- 禁止未使用的参数

---

## 项目结构

```
frontend/mobile/
├── src/
│   ├── api/                    # API 客户端层
│   │   ├── client.ts           # HTTP 客户端 (axios 封装, 自动处理 auth)
│   │   ├── health.ts           # 健康数据 API
│   │   ├── session.ts          # 会话 API
│   │   ├── files.ts            # 文件浏览 API
│   │   ├── sse.ts              # SSE (Server-Sent Events) 客户端
│   │   └── ws.ts               # WebSocket 客户端
│   │
│   ├── components/             # 组件
│   │   ├── chat/               # 聊天组件
│   │   │   ├── ChatInput.vue           # 聊天输入框
│   │   │   ├── MessageBubble.vue       # 消息气泡
│   │   │   ├── MarkdownContent.vue     # Markdown 渲染
│   │   │   ├── ReasoningBlock.vue      # AI 推理过程展示
│   │   │   ├── SessionDrawer.vue       # 会话侧边栏
│   │   │   ├── StreamingText.vue       # 流式文本渲染
│   │   │   └── ToolCardMini.vue        # 工具调用卡片
│   │   │
│   │   ├── common/             # 通用组件
│   │   │   ├── LoginOverlay.vue        # 登录覆盖层 (401 自动弹出)
│   │   │   ├── PageState.vue           # 页面状态 (加载/空/错误)
│   │   │   ├── SkeletonLoader.vue      # 骨架屏加载
│   │   │   ├── LoadingSpinner.vue      # 加载旋转器
│   │   │   ├── DetailOverlay.vue       # 详情覆盖层
│   │   │   ├── NotificationList.vue    # 通知列表
│   │   │   └── PullIndicator.vue       # 下拉刷新指示器
│   │   │
│   │   ├── dashboard/          # 看板组件
│   │   │   ├── DashboardCard.vue       # 看板卡片容器
│   │   │   ├── HrateChart.vue          # 心率图表
│   │   │   ├── SpO2Chart.vue           # 血氧图表
│   │   │   ├── StressChart.vue         # 压力图表
│   │   │   ├── StepsChart.vue          # 步数图表
│   │   │   ├── SleepChart.vue          # 睡眠图表
│   │   │   ├── BatteryChart.vue        # 电量图表
│   │   │   ├── GpsPreview.vue          # GPS 轨迹预览
│   │   │   └── GpsMapOverlay.vue       # GPS 全屏地图覆盖层
│   │   │
│   │   ├── files/              # 文件组件
│   │   │   ├── FileItem.vue           # 文件/文件夹项
│   │   │   ├── FileTree.vue           # 文件树结构
│   │   │   ├── SearchBar.vue          # 搜索栏
│   │   │   ├── SearchResultItem.vue   # 搜索结果项
│   │   │   └── PreviewOverlay.vue     # 文件预览覆盖层
│   │   │
│   │   ├── nav/                # 导航
│   │   │   └── BottomNav.vue          # 底部导航栏 (5 Tab)
│   │   │
│   │   ├── reports/            # 报告组件
│   │   │   ├── ReportCard.vue         # 报告卡片
│   │   │   └── ReportFilter.vue       # 报告筛选器
│   │   │
│   │   └── settings/           # 设置组件
│   │       └── DebugPanel.vue         # 调试面板
│   │
│   ├── composables/            # 组合式函数 (Composables)
│   │   ├── useApi.ts                  # API 认证状态管理
│   │   ├── useChat.ts                 # 聊天状态管理
│   │   ├── useChatIntegration.ts      # 聊天集成 (SSE 路由 + 实时连接初始化)
│   │   ├── useStreamingMessage.ts     # 流式消息处理
│   │   ├── useSendMessage.ts          # 消息发送逻辑
│   │   ├── useDashboard.ts            # 看板数据管理
│   │   ├── useChart.ts                # 图表辅助函数
│   │   ├── useGps.ts                  # GPS 轨迹数据管理
│   │   ├── useFileBrowser.ts          # 文件浏览器状态管理
│   │   ├── useReports.ts              # 报告数据管理
│   │   └── useRealTime.ts             # 实时连接管理 (SSE + WS)
│   │
│   ├── types/                  # TypeScript 类型定义
│   │   ├── index.ts                   # 统一导出
│   │   ├── api.ts                     # API 通用类型
│   │   ├── chat.ts                    # 聊天相关类型
│   │   ├── health.ts                  # 健康数据类型
│   │   ├── gps.ts                     # GPS 数据类型
│   │   ├── files.ts                   # 文件系统类型
│   │   └── reports.ts                 # 报告类型
│   │
│   ├── router/                 # Vue Router (hash 模式)
│   │   └── index.ts                   # 路由配置 (5 个页面)
│   │
│   ├── styles/                 # CSS 样式
│   │   ├── variables.css              # CSS 变量 (颜色/间距/字体)
│   │   ├── base.css                   # 基础样式重置
│   │   ├── animations.css             # 动画关键帧
│   │   ├── components.css             # 组件通用样式
│   │   └── main.css                   # 主样式入口 (导入所有样式)
│   │
│   ├── utils/                  # 工具函数
│   │   └── markdown.ts                # 自定义 Markdown 渲染器
│   │
│   ├── views/                  # 页面视图 (5 个 Tab)
│   │   ├── ChatView.vue               # 聊天页面
│   │   ├── DashboardView.vue          # 健康看板页面
│   │   ├── FilesView.vue              # 文件浏览页面
│   │   ├── ReportsView.vue            # 报告页面
│   │   └── SettingsView.vue           # 设置页面
│   │
│   ├── App.vue                 # 根组件 (导航 + 登录覆盖层 + 实时连接)
│   └── main.ts                 # 入口文件 (挂载 app 和 router)
│
├── e2e/                        # Playwright E2E 测试
│   └── app.spec.ts                    # 11 个 E2E 测试场景
│
├── tests/                      # Vitest 单元测试
│   └── unit/
│       ├── components/
│       │   ├── ChatInput.test.ts
│       │   ├── MessageBubble.test.ts
│       │   ├── DashboardCard.test.ts
│       │   ├── FileItem.test.ts
│       │   ├── ReportCard.test.ts
│       │   ├── LoginOverlay.test.ts
│       │   └── SettingsView.test.ts
│       ├── composables/
│       │   ├── useChat.test.ts
│       │   ├── useStreamingMessage.test.ts
│       │   ├── useDashboard.test.ts
│       │   ├── useGps.test.ts
│       │   ├── useFileBrowser.test.ts
│       │   └── useReports.test.ts
│       └── utils/
│           └── markdown.test.ts
│
├── dist/                       # 构建产物 (Vite build 输出)
├── index.html                  # Vite 入口 HTML
├── index.original.html         # 原始单文件 SPA (备份, 约 3950 行)
├── playwright.config.ts        # Playwright 配置
├── vite.config.ts              # Vite 构建配置
├── vitest.config.ts            # Vitest 测试配置
├── tsconfig.json               # TypeScript 项目引用
├── tsconfig.app.json           # TypeScript 应用配置 (strict)
├── tsconfig.node.json          # TypeScript Node 配置
├── env.d.ts                    # 环境类型声明
└── package.json                # 依赖与脚本
```

---

## 架构决策

### Hash 模式路由

Vue Router 使用 `createWebHashHistory()` (hash 模式)：

```typescript
import { createRouter, createWebHashHistory } from 'vue-router'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/chat' },
    { path: '/chat', component: () => import('@/views/ChatView.vue') },
    { path: '/dashboard', component: () => import('@/views/DashboardView.vue') },
    { path: '/files', component: () => import('@/views/FilesView.vue') },
    { path: '/reports', component: () => import('@/views/ReportsView.vue') },
    { path: '/settings', component: () => import('@/views/SettingsView.vue') },
  ],
})
```

**原因**：项目部署在后端 FastAPI 服务的 `/mobile/` 路径下，后端有自己的一套路由系统。使用 hash 模式 (URL 格式为 `/#/chat`) 可以避免前端路由与后端路由的冲突，后端只需要 serve `index.html`，前端路由完全由 hash 片段处理。这对于嵌入 Android WebView 的场景尤其重要。

### 组合式函数替代 Pinia

项目未使用 Pinia 或 Vuex 状态管理库，全部状态管理通过 Vue 3 的 Composition API 组合式函数 (composables) 实现。每个 composable 独立封装一个领域的状态和逻辑：

- **`useChat`** -- 管理聊天消息列表、会话切换、消息历史
- **`useStreamingMessage`** -- 处理流式消息的逐 token 渲染
- **`useSendMessage`** -- 封装消息发送请求与重试逻辑
- **`useDashboard`** -- 管理看板数据加载、日期切换、传感器可见性
- **`useChart`** -- Chart.js 图表创建和更新辅助
- **`useGps`** -- 管理 GPS 轨迹数据、Leaflet 地图交互
- **`useFileBrowser`** -- 文件树导航、搜索、面包屑路径
- **`useReports`** -- 报告列表、筛选、分页
- **`useApi`** -- API 认证状态、token 管理、auth fail 事件
- **`useRealTime`** -- SSE + WebSocket 连接生命周期管理
- **`useChatIntegration`** -- 聊天集成层，协调 SSE 事件到聊天状态的路由

**原因**：项目规模适中 (5 个页面)，composable 模式比 Pinia 更轻量，避免了额外的依赖。同时 composable 天然支持 tree-shaking，按需引入。

### 自定义 Markdown 渲染器

`src/utils/markdown.ts` 包含一个自实现的 Markdown 解析/渲染器，未使用任何第三方 Markdown 库 (如 marked、markdown-it)。

**原因**：
- 减少依赖体积，项目只需要支持 Markdown 子集 (标题、列表、代码块、加粗、链接等)
- 完全控制渲染行为，方便与流式文本渲染 (SSE 逐 token) 集成
- 避免 XSS 风险，渲染器只生成受控的 HTML 结构

### 看板数据双源加载

DashboardView 的数据加载采用双源策略：

1. 优先请求 `GET /api/screen/dashboard` -- 专门的看板数据聚合接口
2. 若聚合接口不可用，自动回退到 `GET /api/health/query` -- 逐个传感器查询

**原因**：后端存在两个版本的 API 接口。聚合接口效率更高，但部分部署环境可能未支持。双源策略保证了兼容性，在不影响用户体验的前提下平滑降级。

### SSE + WebSocket 双通道实时连接

项目同时维护两条实时通信通道：

- **SSE (Server-Sent Events)** -- 接收 AI 响应流 (`/api/screen/chat/send` 的流式响应)、消息通知
- **WebSocket** -- 双向通信，用于文件变更推送、系统状态更新

连接由 `useRealTime` composable 统一管理，包括：
- 自动重连 (token 过期后登录成功自动恢复)
- 连接状态追踪 (`connectedSSE`、`connectedWS`)
- 优雅断开 (`disconnect()`)

---

## 页面路由

| 路径 | 视图 | 功能 |
|------|------|------|
| `/#/chat` | ChatView | AI 对话 (支持流式输出、工具调用、会话管理) |
| `/#/dashboard` | DashboardView | 健康看板 (心率/血氧/压力/步数/睡眠/电量/GPS) |
| `/#/files` | FilesView | 手机文件浏览 (目录树、搜索、文件预览) |
| `/#/reports` | ReportsView | AI 报告列表 (筛选、分页查看) |
| `/#/settings` | SettingsView | 系统设置 (连接状态、调试面板) |

底部导航栏共 5 个 Tab，对应上述 5 个页面。

---

## 构建与部署

### 开发

```bash
# 启动开发服务器 (默认 http://localhost:5173)
npm run dev
```

### 构建

```bash
# 类型检查 + 构建 (输出到 dist/)
npm run build
```

构建配置 (`vite.config.ts`)：
- `base: './'` -- 相对路径引用资源，适配后端 `/mobile/` 路径部署
- `target: 'es2015'` -- 兼容 Android WebView 的 JS 引擎
- `outDir: 'dist'` -- 构建输出目录
- `@` 路径别名指向 `./src`

### 部署

1. `npm run build` 生成 `dist/` 目录
2. 后端自动从 `frontend/mobile/dist/` 提供静态文件服务
3. Android WebView 加载 URL: `https://<host>:<port>/mobile/`

> **注意**：每次更新前端代码后，需重新运行 `npm run build` 以更新 `dist/` 中的静态资源。否则 Android App 加载的仍是旧的构建产物。

---

## 测试

### 单元测试 (Vitest)

```bash
npm run test:unit
```

- 框架: Vitest 3 + happy-dom (DOM 环境)
- 配置: `vitest.config.ts` (与 Vite 共享别名配置)
- 数量: 14 个测试文件
- 覆盖范围:
  - 组件: ChatInput、MessageBubble、DashboardCard、FileItem、ReportCard、LoginOverlay、SettingsView
  - 组合式函数: useChat、useStreamingMessage、useDashboard、useGps、useFileBrowser、useReports
  - 工具: markdown 渲染器

### E2E 测试 (Playwright)

```bash
npm run test:e2e
```

- 框架: Playwright 1.52
- 配置: `playwright.config.ts` (Chromium + Firefox)
- 数量: 11 个测试场景
- 覆盖范围:
  - 页面结构验证 (Chat/Dashboard/Files/Reports/Settings)
  - 交互测试 (登录表单、日期导航、编辑模式切换)
  - UI 组件测试 (PageState、SearchBar 搜索/清除)

---

## 常见问题排查

### 401 认证错误

页面自动弹出 LoginOverlay 登录覆盖层。如果看到登录界面：
1. 输入用户名和密码登录
2. 登录成功后覆盖层关闭，实时连接自动重连 (SSE + WS)
3. 如果反复弹出登录框，检查后端服务是否正常运行

### 静态资源不更新

修改代码后页面未生效：
1. 运行 `npm run build` 重新构建
2. 确认 `dist/` 目录中文件时间戳已更新
3. 如果仍不生效，尝试在 Android App 中清空 WebView 缓存

### 后端重启后的操作

后端服务重启后需要重新登录。可通过以下端点重启后端：

```bash
POST /api/screen/restart
Authorization: Bearer <token>
```

---

## 迁移状态

原始版本为单文件 SPA（`index.original.html`，约 3950 行），已完整迁移至模块化的 Vue 3 + Vite + TypeScript 架构。迁移覆盖：

- [x] 组件拆分 -- 7 个组件目录，共 30+ 个 Vue SFC
- [x] 类型系统 -- 完整的 TypeScript 类型定义
- [x] 组合式函数 -- 11 个 composables 管理状态和逻辑
- [x] API 层 -- 6 个 API 模块封装后端接口
- [x] 样式模块化 -- 5 个 CSS 文件按职责分离
- [x] 测试覆盖 -- 14 个单元测试 + 11 个 E2E 场景
- [x] 构建脚本 -- Vite 构建 + vue-tsc 类型检查
- [x] 原始文件保留 -- `index.original.html` 作为备份

---

## 许可证

本项目为 Axeuh Health Monitor 系统的一部分。
