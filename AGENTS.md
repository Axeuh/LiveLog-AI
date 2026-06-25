# LiveLog-AI

**技术栈**: Python 3.10+ (FastAPI) + Kotlin (Android/Compose) + TypeScript (Vue 3/Vite)
**仓库模式**: 单体仓库 (Monorepo)，4个独立子系统公用同一后端平台
**生成时间**: 2026-06-24

## 概览

AI 驱动的健康监测系统。Android App 采集传感器数据(心率/GPS/步数/音频等)，FastAPI 后端接收存储，OpenCode AI 定时分析健康状态和行为模式。Windows Agent 提供远程PC管理能力。

## 目录结构

```
LiveLog-AI/
├── backend/           # FastAPI 后端 (Python) - 见 backend/AGENTS.md
├── app/               # Android 数据采集 App (Kotlin) - 见 app/AGENTS.md
├── frontend/mobile/   # WebView SPA 前端 (Vue 3/TS) - 见 frontend/mobile/AGENTS.md
├── ai/                # AI 分析系统 (OpenCode) - 见 ai/AGENTS.md
├── agent/             # Windows 远程 Agent (Python) - 小模块
├── ai-template/       # AI 模板参考
├── behavior/          # API 行为测试快照
├── scripts/           # 工具脚本
├── .opencode/         # OpenCode 项目配置
├── .sisyphus/         # Sisyphus 工作跟踪
├── launcher.py        # Python 统一启动器（所有服务从此启动）
├── start.bat          # Windows 一键启动（委托给 launcher.py）
└── start.ps1          # PowerShell 启动脚本（委托给 launcher.py，不重复配置路径）
```

## 子系统速查

| 子系统 | 位置 | 语言/框架 | 入口 | 关键文档 |
|--------|------|-----------|------|----------|
| 后端 | `backend/` | Python 3.10+ / FastAPI | `main.py` (uvicorn) | `backend/AGENTS.md` |
| Android App | `app/` | Kotlin / Jetpack Compose | `MainActivity.kt` | `app/AGENTS.md` |
| 前端 SPA | `frontend/mobile/` | TypeScript / Vue 3 + Vite | `src/main.ts` | `frontend/mobile/AGENTS.md` |
| AI 分析 | `ai/` | Python + OpenCode | `data/tasks.yaml` | `ai/AGENTS.md` |
| Windows Agent | `agent/` | Python / FastAPI | `agent_server.py` | (根文档覆盖) |

## 快速定位

| 任务 | 位置 |
|------|------|
| 添加 API 端点 | `backend/routers/`，在 `backend/main.py` 注册 |
| 修改业务逻辑 | `backend/services/` |
| 修改 AI 任务/行为 | `ai/data/tasks.yaml` + `ai/agents/*.md` |
| Android 采集器 | `app/.../service/collectors/` |
| Android UI 设置页 | `app/.../ui/settings/` |
| 前端页面/组件 | `frontend/mobile/src/views/` + `components/` |
| 前端组合式函数 | `frontend/mobile/src/composables/` |
| 启动服务 | `python launcher.py` 或 `start.bat`（生产）；uvicorn reload（开发） |

## 操作准则

### 服务管理
- **禁止**使用 `Stop-Process`、`taskkill`、`kill` 等方式结束进程
- 服务需要重启/停用时，使用 HTTP/HTTPS **重启端点** 进行优雅操作
- Agent 有 `/restart` 端点，后端有 `/api/system/restart` 端点

### 调试连接
- 所有调试连接必须使用 HTTPS，不要降级到 HTTP

### 代码修改
- **禁止**使用脚本(Python/Shell/Bat)直接修改 `.kt`、`.java`、`.py`、`.ts` 等源代码文件 —— 会导致乱码
- 所有代码修改应通过 `task()` 委托给子智能体执行

### 临时文件
- 所有临时文件存放在 `D:\opencode`

## 项目级约定

### 跨子系统约定
- Git 提交必须实时：每次 AI 任务完成后立即 `git add` + `git commit`
- `config.yaml`、`config.local.yaml`、`.env` 不提交到 git
- `backend/config/auth.json` 包含加密密码 —— **注意不要在 git 中泄露**
- AGENTS.md 用中文编写，子目录不重复父目录内容

### Python 约定 (backend/ + agent/)
- FastAPI routers + services(单例模式) + middleware(auth) 架构
- 配置优先级：`config.yaml` > `config.local.yaml` > 环境变量 > 默认值
- Token Bearer 认证，localhost 免认证
- 测试: pytest + TestClient，conftest.py 提供 client/auth_headers fixture

### Kotlin/Android 约定 (app/)
- 包名 `com.axeuh.health.monitor`，minSdk 26 / targetSdk 36
- Kotlin 代码在 `src/main/java/` 目录下（兼容 Gradle 标准）
- 分层架构：网络层(AppHttpClient) -> 状态层(SensorStateHolder) -> 采集层(BaseCollector) -> UI层(ViewModel/Compose)
- 测试: JUnit 5 + MockK + Robolectric + Truth，反引号函数命名 `@Test fun \`should do X\``

### TypeScript/Vue 约定 (frontend/mobile/)
- Vue 3 Composition API + `<script setup>`，严格TS模式
- 无 Pinia —— 所有状态用 composables 管理
- Router hash 模式，路径别名 `@` -> `./src`
- 测试: Vitest + happy-dom (单元)，Playwright (E2E)

## 构建与运行命令

```bash
# 启动整个系统
python launcher.py                     # 推荐，支持 --config 参数
start.bat                              # Windows 一键启动

# 后端开发
cd backend && python -m uvicorn main:app --reload --port 8768

# 前端开发
cd frontend/mobile && npm run dev

# 前端构建（构建后需重启后端）
cd frontend/mobile && npm run build

# Android 构建
gradlew assembleDebug

# 运行测试
cd backend && python -m pytest tests/ -v    # 后端测试
cd frontend/mobile && npm run test:unit     # 前端单元测试
cd frontend/mobile && npm run test:e2e      # 前端 E2E 测试
gradlew test                                # Android 测试
```

## 反模式（禁止）
1. **强杀进程**：使用 `Stop-Process`/`taskkill` 释放端口 —— 应使用重启端点
2. **脚本改代码**：任何 Python/Shell 脚本直接写 .kt/.py/.ts 文件 —— 委托给 task()
3. **运行时数据提交**：日志文件、用户数据、`outputs/.npy` 不应提交到 git
4. **配置硬编码**：路径、端口、密码应走 `config.yaml`，不硬编码在脚本中
5. **同时修改 config.yaml 和 config.local.yaml**：只改 `config.local.yaml`，保持 `config.yaml` 为默认模板
6. **在 AI 会话中查看项目代码**：AI (`ai/`) 只关心 `ai/` 目录内的数据文件，不读项目代码

## 注意事项

- 前端修改后需 `npm run build` 并在后端生效（后端 serve `frontend/mobile/dist/`）
- `start.ps1` 使用 `Stop-Process` 释放端口 —— 与操作准则矛盾，已知问题
- `backend/models.py`（Pydantic 数据模型）与 `backend/models/`（ML 权重目录）命名冲突，导入时注意
- `app/` 目录是 Android 模块（Gradle），不是 FastAPI 的 app 包
- 后端 `port 1256` HTTPS（生产）/ `port 8768` HTTP 开发；Agent `port 18888` 本地 HTTP
- OpenCode AI 服务运行在 `port 4096`，后端通过 `opencode_gateway.py` 通信
