# Routers - API 路由层

**生成时间**: 2026-06-20
**文件数**: 17 个路由文件
**前缀**: `/api/screen`, `/api/agents`, `/api/health` 等

## 概述

FastAPI 路由层，按业务领域分文件组织。提供 REST API 和 WebSocket。

## 路由文件列表

| 文件 | 前缀 | 职责 |
|------|------|------|
| `tts.py` | `/api/screen` | TTS 语音合成 |
| `tasks.py` | `/api/screen` | 定时任务 |
| `scripts.py` | `/api/scripts` | 脚本任务管理(列表/详情/启停) |
| `session.py` | `/api/screen` | 会话管理 |
| `ws_main.py` | `/ws` | 主 WebSocket |
| `notifications.py` | `/api` | 通知推送 |
| `model_config.py` | `/api/screen` | 模型设置 |
| `agents_remote.py` | `/api/agents` | Agent 注册/心跳/状态 |
| `health.py` | `/api/health` | 健康数据同步/查询 |
| `ota.py` | `/api/ota` | OTA 更新 |
| `speakers.py` | `/api/screen` | 声纹管理 |
| `mobile.py` | `/api/mobile` | 手机端文件浏览 |
| `pc.py` | `/api/pc` | PC 感知数据接收 |
| `maintenance.py` | `/api` | 维护管理（重启等） |
| `voice_assistant_ws.py` | `/ws` | 语音助手 WebSocket |
| `agents_remote.py` | `/ws` | Agent 持活 WebSocket |
| `__init__.py` | — | 模块导出 |

## 关键端点

| 功能 | 端点 | 方法 |
|------|------|------|
| 健康检查 | `/health` | GET |
| 登录 | `/login` | POST |
| TTS 合成 | `/api/screen/tts/speak` | POST |
| TTS 停止 | `/api/screen/tts/stop` | POST |
| 任务列表 | `/api/screen/tasks` | GET |
| 任务创建 | `/api/screen/tasks` | POST |
| 任务执行记录 | `/api/screen/tasks/{id}/executions` | GET |
| 健康数据上传 | `/api/health/sync` | POST |
| 健康数据查询 | `/api/health/query` | GET |
| 有数据的日期 | `/api/health/dates` | GET |
| WebSocket | `/ws` | WS |
| Agent 持活 | `/ws/agent` | WS |
| Agent 注册 | `/api/agents/register` | POST |
| Agent 列表 | `/api/agents/list` | GET |
| 声纹注册 | `/api/screen/speakers/enroll` | POST |
| 声纹识别 | `/api/screen/speakers/identify` | POST |
| 通知发送 | `/api/notification/send` | POST |
| App 轮询通知 | `/api/notification/poll` | GET |
| OTA 检查 | `/api/ota/check?version=N` | GET |
| OTA 下载 | `/api/ota/download?token=xxx` | GET（需登录 token） |
| OTA 信息 | `/api/ota/info` | GET |

| 脚本列表 | `/api/scripts` | GET |
| 脚本详情 | `/api/scripts/{name}` | GET |
| 启动脚本 | `/api/scripts/{name}/start` | POST |
| 停止脚本 | `/api/scripts/{name}/stop` | POST |

## 已移除的路由

以下路由已从原 Axeuh Home System 中移除：
- `components.py` — 组件 CRUD（TV大屏不需要）
- `terminals.py` — 终端管理（TV大屏不需要）
- `bash.py` — Bash 执行（TV大屏不需要）
- `stocks.py` — 股票追踪（TV大屏不需要）
- `texts.py` — 文本组件（TV大屏不需要）
- `customs.py` — 自定义组件（TV大屏不需要）
- `stt.py` — 语音识别（本系统不包含STT）
- `stt_ws.py` — STT WebSocket
- `events.py` — SSE 事件代理
- `ws_terminal.py` — 终端 WebSocket

## 相关文档

- `../AGENTS.md` - Backend 总览
- `../services/AGENTS.md` - 服务层文档
