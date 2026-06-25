# 更新日志

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
