# Backend - FastAPI 后端

**生成时间**: 2026-06-20
**框架**: FastAPI + Uvicorn
**Python**: >=3.10

## 概述

FastAPI 后端服务，提供健康数据接收、定时任务调度、自定义脚本任务、TTS 语音合成、远程 Agent 管理、声纹识别、手机通知推送、OTA 更新等功能。

## 目录结构

```
backend/
├── main.py              # 主入口，lifespan + 路由注册
├── middleware/           # 中间件
│   ├── __init__.py
│   └── auth_middleware.py
├── models.py            # Pydantic 数据模型
├── auth.py              # Token 认证系统
├── routers/             # API 路由
├── services/            # 业务服务
├── config/              # 配置模块
├── scripts/             # 用户自定义脚本（AI 通过写文件创建）
├── tests/               # 测试文件
├── data/                # 运行时数据目录（自动生成）
├── logs/                # 日志文件（按日轮转，保留30天）
├── .env                 # 环境配置
└── requirements.txt     # 依赖列表
```

## 快速定位

| 任务 | 位置 | 说明 |
|------|------|------|
| 添加新 API | `routers/` | 创建新文件，在 main.py 注册 |
| 修改业务逻辑 | `services/` | 单例模式，通过 get_*() 获取 |
| 数据模型 | `models.py` | Pydantic BaseModel |
| 脚本任务 | `services/script_runner.py`, `routers/scripts.py` | Python 脚本自动执行 + AST 安全审查 |
| 认证逻辑 | `auth.py` | Token 生成/验证, 多用户 |
| Agent管理 | `routers/agents_remote.py` | Agent 注册/心跳/WS持活 |
| 声纹服务 | `services/voiceprint_service.py` | funasr ERes2NetV2 |
| 定时任务 | `services/task_scheduler.py` | 自动调度 + 热加载 |

## 启动方式

```bash
# 开发
cd backend && python -m uvicorn main:app --port 8768 --reload

# 生产 (HTTPS)
python -m uvicorn main:app --port 8768 \
  --ssl-certfile /path/to/cert.pem --ssl-keyfile /path/to/key.pem

# 使用 launcher.py
cd .. && python launcher.py
```

## 认证中间件

- 多用户支持，token 携带 user_id
- AuthMiddleware 注入 request.state.user_id
- 本地访问 (localhost) 免认证
- 公网访问需要 Bearer Token
- 公开路径: `/health`, `/login`, `/logout`, `/auth/check`

## 配置模块

| 属性 | 说明 |
|------|------|
| `config.yaml` | 生产配置（gitignored） |
| `config.local.yaml` | 本地覆盖（gitignored） |
| `config.example.yaml` | 模板配置（含占位符） |
| `config.py` | 33+ 属性，`@lru_cache` 单例 |

新增配置项需在 `config.py` 添加 `@property`，在 `config.yaml` 添加对应键。

## 已移除的硬编码

- MiMo API Key: `tts_player.py` 硬编码 → config.yaml api.mimo_key
- OTA 独立 Token: `ota.py` `axeuh-ota-2026` → 改为登录 Bearer 认证
- 回退密码: `auth.py` `b"20071011"` → 强制从 config 读取 password_hash

## 相关文档

- `../AGENTS.md` - 项目根目录文档
- `services/AGENTS.md` - 服务层文档
- `routers/AGENTS.md` - 路由层文档
