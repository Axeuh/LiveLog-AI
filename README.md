# Axeuh Health Monitor

AI 驱动的健康监测系统。通过 Android App 采集传感器数据（心率、GPS、步数、音频环境等），配合 Windows 远程 Agent，由 AI 自动分析用户健康状态和行为模式。

## 架构

```
┌─────────────────────────────────────────────────┐
│                  Android App                      │
│  DataCollectorService ── HTTPS POST ──┐           │
│  MobileActivity (WebView) ── HTTPS ──┤           │
│  OTA 自更新 ── HTTPS ──┐            │           │
└─────────────────────────┘            │           │
                                       │           │
┌─────────────────────────────────────────────────┐
│              Windows 远程 Agent                   │
│  截图/文件/命令 ── WS/HTTP ────┐                │
└───────────────────────────────┘                │
                                                 │
┌─────────────────────────────────────────────────┐
│           后端层 (FastAPI 1256/8768)              │
│  AuthMiddleware ── 用户认证隔离                    │
│  TTS 语音合成                                     │
│  定时任务调度 (AI自动化)                            │
│  感知数据接收 (perception/health)                  │
│  声纹识别管理                                     │
│  Agent 远程管理                                   │
│  OTA 更新                                        │
│  手机通知推送                                     │
└────────────────────┬────────────────────────────┘
                     │
┌─────────────────────────────────────────────────┐
│            OpenCode AI (4096 端口)               │
│  定时数据检查 ── 脚本→子智能体→验收               │
│  每日复盘 ── 数据验证→报告生成→记忆收割            │
│  健康异常检测                                     │
│  行为模式分析                                     │
└─────────────────────────────────────────────────┘
```

## 安装

```bash
# 克隆仓库
git clone https://github.com/Axeuh/axeuh-health-monitor.git
cd axeuh-health-monitor

# 后端依赖
pip install -r backend/requirements.txt

# 如需 ML 功能（声纹识别等），额外安装：
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu124
pip install funasr modelscope
# 或一条命令：
pip install -e ".[ml]"

# 前端依赖
cd frontend/mobile && npm install
```

## 快速启动

```bash
# 配置（首次运行前）
# 编辑项目根目录的 config.yaml，填入你的 API Key 等配置
# backend/config/config.example.yaml 列出所有可选字段供参考

# 一键启动（Windows）
start.bat

# 或 Python 启动器（推荐，自动读取 config.yaml）
python launcher.py

# 单独启动后端（开发模式，HTTP 8768 端口）
cd backend && python -m uvicorn main:app --reload --port 8768
```

### HTTPS 证书生成

项目要求 HTTPS 连接。开发环境可用自签名证书：

```bash
# 生成自签名证书（有效期 365 天）
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem \
  -days 365 -nodes -subj "/CN=localhost"

# 将 cert.pem 和 key.pem 路径填入项目根目录 config.yaml 的 ssl.cert / ssl.key 字段
```

Android App 首次连接自签名服务器时，需在浏览器中打开 `https://<你的IP>:<端口>/health` 并信任证书。也可将 cert.pem 导入 Android 信任存储。**生产环境请使用受信任 CA 签发的证书**。

## 目录结构

```
axeuh-health-monitor/
├── launcher.py               # 统一启动器 (OpenCode + 后端)
├── start.bat                 # Windows 一键启动
├── backend/
│   ├── main.py               # FastAPI 主入口
│   ├── routers/               # API 路由
│   │   ├── tts.py            # 语音合成
│   │   ├── tasks.py          # 定时任务
│   │   ├── health.py         # 健康数据同步/查询
│   │   ├── session.py        # 会话管理
│   │   ├── agents_remote.py  # Agent 远程管理
│   │   ├── ws_main.py        # 主 WebSocket
│   │   ├── speakers.py       # 声纹管理
│   │   ├── ota.py            # OTA 更新
│   │   ├── mobile.py         # 手机端文件浏览 API
│   │   ├── notifications.py  # 通知推送
│   │   ├── pc.py             # PC 感知数据接收
│   │   └── ...               # 其他
│   ├── services/             # 业务服务
│   ├── middleware/            # 认证中间件
│   ├── config/               # 配置模块
│   └── tests/                # 测试
├── frontend/mobile/          # App WebView 页面
├── ai/                       # AI 监测系统
│   ├── AGENTS.md             # AI 智能体上下文
│   ├── agents/               # 子智能体 prompt
│   ├── analysis/             # 分析脚本
│   ├── data/                 # 按日组织的数据文件
│   └── 记忆/                 # 长期记忆系统
├── app/                      # Android 数据采集 App
├── agent/                    # Windows 远程 Agent
└── scripts/                  # 工具脚本
```

## 核心功能

| 功能 | 说明 |
|------|------|
| 感知数据采集 | Android 传感器（心率/GPS/步数/音频/屏幕/通知等） |
| 健康数据同步 | 心率、血氧、压力、睡眠、步数（手环+手机） |
| AI 定时分析 | 每2小时数据检查 + 每日复盘 |
| TTS 语音播报 | MiMo API 语音合成 |
| 声纹识别 | funasr ERes2NetV2 说话人识别 |
| 手机通知推送 | 异常检测/任务完成/日常建议 |
| 定时任务 | 自动执行 AI 分析任务 |
| 远程 Agent 管理 | Windows 远程截图/文件/命令 |
| OTA 自更新 | Android App 远程自动升级 |
| 多用户隔离 | 独立登录 + 数据按用户路由 |

## 开发

```bash
# 后端
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8768

# 测试
cd backend
python -m pytest tests/ -v
```

## Android App 构建

```bash
# 在项目根目录执行
cd app

# Debug APK
../gradlew assembleDebug

# 产物位置: app/build/outputs/apk/debug/app-debug.apk

# Release APK（需配置签名）
../gradlew assembleRelease
```

编译要求：
- Android Studio Hedgehog (2023.1) 或更高版本
- JDK 17
- Android SDK 36 (compileSdk)
- Gradle 8.x (由 Gradle Wrapper 自动管理)

Android App 主要功能：
- 传感器数据采集（心率/GPS/步数/音频/屏幕/通知/电量）
- 后台 Service 持续运行
- WebView 加载后端前端页面
- OTA 自更新

## API 端点

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/screen/tts/speak` | POST | 语音合成 |
| `/api/screen/tts/stop` | POST | 停止播放 |
| `/api/screen/tasks` | GET | 定时任务列表 |
| `/api/screen/session/*` | * | 会话管理 |
| `/api/screen/ws` | WS | WebSocket 主连接 |
| `/api/health/sync` | POST | 健康数据上传 |
| `/api/health/query` | GET | 健康数据查询 |
| `/api/speakers/*` | * | 声纹管理 |
| `/api/agents/*` | * | Agent 管理 |
| `/api/notification/*` | * | 通知推送 |
| `/api/ota/*` | * | OTA 更新 |
| `/api/mobile/*` | * | 手机端文件浏览 |
| `/mobile` | GET | App WebView 页面 |
| `/login` | POST | 登录 |
| `/health` | GET | 健康检查 |

## 依赖

- Python 3.10+
- FastAPI, Uvicorn
- OpenCode (AI 运行环境)

## 许可证

[Apache 2.0](LICENSE) © 2026 Axeuh

## 贡献

欢迎贡献！请参阅 [CONTRIBUTING.md](CONTRIBUTING.md) 了解参与方式。

