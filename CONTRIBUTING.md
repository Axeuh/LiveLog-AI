# 贡献指南

感谢你考虑为 Axeuh Health Monitor 做出贡献！

## 报告问题

- 使用 GitHub Issues 报告 bug 或功能请求
- 描述问题时请包含：运行环境、复现步骤、期望行为和实际表现
- 如果是安全相关问题，请通过电子邮件私下报告，不要提交公开 Issue

## 提交 Pull Request

1. Fork 本仓库
2. 从 `master` 分支创建你的特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交你的改动 (`git commit -m 'feat: add amazing feature'`)
4. 推送到你的分支 (`git push origin feature/amazing-feature`)
5. 创建一个 Pull Request

## Commit 规范

本项目使用中文提交信息，格式如下：

```
<类型>: <简要描述>

类型:
- feat:    新功能
- fix:     Bug 修复
- refactor: 重构
- style:   代码风格调整 (不影响功能)
- docs:    文档更新
- test:    测试相关
- chore:   构建/工具链相关
```

示例：
```
feat: 添加心率数据实时同步接口
fix: 修复 OTA 更新包校验失败问题
docs: 更新 README 中的 API 文档
```

## 开发规范

### Python (backend/)

- 遵循 PEP 8 编码规范
- 类型注解必须完整 (Python 3.10+)
- 路由在 `backend/routers/` 中定义，业务逻辑在 `backend/services/` 中实现
- 配置项在 `backend/config/config.py` 中声明，值通过 `config.yaml` 注入
- 新增功能需包含 pytest 测试

### TypeScript (frontend/mobile/)

- Vue 3 Composition API + `<script setup lang="ts">`
- 严格 TypeScript 模式 (`strict: true`)
- 状态管理使用 composables，不使用 Pinia/Vuex
- 新增功能需包含 Vitest 单元测试

### Kotlin (app/)

- 遵循 Kotlin 官方编码规范
- 分层架构: 网络层 -> 状态层 -> 采集层 -> UI 层
- 测试使用 JUnit 5 + MockK + Truth

## 项目结构

```
backend/        # FastAPI 后端
app/            # Android 数据采集 App
frontend/mobile/ # WebView SPA 前端
ai/             # AI 分析系统
agent/          # Windows 远程 Agent
```

## 开发环境设置

详见 [README.md](README.md) 中的快速启动指南。
