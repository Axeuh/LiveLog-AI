# 更新日志

## [1.2.0] - 2026-07-19

### 新增
- 子智能体多级嵌套支持：`parentSessionId` 单级改为 `parentChain` 栈，任意层级可继续打开子智能体列表进入孙会话
- 会话 Token 用量显示：双路径更新（SSE `info.tokens` 实时 + API 消息历史加载），显示 coins 图标 + 格式化数字
- 会话 ID 复制功能：`copySessionId()` 通过 `navigator.clipboard.writeText` + 2 秒勾选反馈
- 测试沙箱 `frontend/refactor/` AGENTS.md 文档
- 子会话栏添加子智能体按钮（之前只有返回按钮，无法在子会话中再打开子智能体）

### 变更
- 前端 SSE 流式消息架构重构：废除 `_activePlaceholder` 模式，改为集中式 Store（SSE 直接修改 `messages.value`）
- 消息角色判定增强：新增兜底逻辑（有 parts 无 content = AI，有 content 无 parts = 用户）
- `initStreaming()` 替代 `configure()` 完成初始化
- 返回按钮文本动态化："返回主会话" → "返回 {父级标题} 会话"

### 修复
- SSE 历史消息回放过早触发 `finalizeStreaming`：`message.updated` 改为 no-op，最终化由 `session.idle` 统一触发
- 用户消息被显示为 AI 消息：`getMessageRole` 添加多层兜底判定

## [1.1.0] - 2026-06-20

### 新增
- 前端 UI 迁移：从单文件 SPA 迁移为模块化 Vue 3 + Vite + TypeScript 架构
  - 30+ 组件、11 个 composables、6 个 API 模块
  - 完整的单元测试 (Vitest) 和 E2E 测试 (Playwright) 覆盖
- 声纹识别功能 (funasr ERes2NetV2)
- OTA 自更新机制
- 多用户隔离认证

### 变更
- 认证中间件重构：统一 Token 校验、移除 localhost 豁免
- 配置系统重构：config.yaml + config.local.yaml 双层覆盖
- 移除硬编码密钥，全部纳入配置管理
- GPS 覆盖层全屏显示、预览 Canvas 连续绘制

### 修复
- 修复 OTA 路由认证绕过问题
- 修复音频采集器 UnicodeDecodeError
- 修复定时任务脚本执行路径问题

### 技术债务
- 后端 config.py 中部分遗留属性待清理
- Android App 仍需手动注册 BroadcastReceiver

## [1.0.0] - 2026-05-27

### 新增
- FastAPI 后端初始版本
  - 感知数据接收 (心率/GPS/步数/音频/屏幕/通知)
  - 健康数据同步与查询
  - TTS 语音合成 (MiMo API)
  - WebSocket 实时通信
  - 定时任务调度 (apscheduler)
- Android 数据采集 App (Jetpack Compose)
  - 传感器数据采集 (心率/GPS/步数/音频/屏幕/通知/电量)
  - WebView 嵌入前端 SPA
  - 前台 Service 持续采集
- WebView 前端 SPA (单文件架构)
  - AI 聊天 (流式输出)
  - 健康看板 (7 种图表)
  - 文件浏览、报告查看、系统设置
- AI 分析系统 (OpenCode)
  - 定时数据检查 (每2小时)
  - 每日复盘与报告生成
  - 异常检测
- Windows 远程 Agent
  - 远程截图/文件操作/命令执行
- 一键启动脚本 (start.bat / launcher.py)
