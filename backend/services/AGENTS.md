# Services - 业务服务层

**生成时间**: 2026-06-20
**文件数**: 20 个 Python 文件
**模式**: 全局单例 + 工厂函数

## 概述

业务逻辑层，包含核心服务、OpenCode 网关、定时任务系统、健康存储、声纹识别。所有服务使用单例模式管理。

## 服务分类

### 核心服务

| 服务 | 文件 | 职责 |
|------|------|------|
| ComponentManager | `component_manager.py` | WebSocket 连接管理 + 状态广播 |
| EventLoopManager | `event_loop_manager.py` | 主事件循环引用管理 |
| TTSPlayer | `tts_player.py` | TTS 语音播放 |

### OpenCode 集成

| 服务 | 文件 | 职责 |
|------|------|------|
| OpenCodeClient | `opencode_client.py` | OpenCode API 客户端 |
| OpenCodeGateway | `opencode_gateway.py` | OpenCode 网关 (SSE/事件代理) |

### 定时任务系统

| 服务 | 文件 | 职责 |
|------|------|------|
| TaskScheduler | `task_scheduler.py` | 定时任务调度器（每2秒轮询） |
| TaskStorage | `task_storage.py` | 任务仓储 + YAML 解析/热加载 |
| TaskExecutor | `task_executor.py` | 定时任务执行器 |
| TaskModels | `task_models.py` | 任务数据模型 |
| TaskConfig | `task_config.py` | 任务配置 |

### 自定义脚本系统

| 服务 | 文件 | 职责 |
|------|------|------|
| ScriptRunner | `script_runner.py` | 脚本进程管理器(启动/监控/心跳/自动重启) + 热加载(FileWatcher) + stdout桥接(JSON→Gateway) |
| ScriptSandbox | `script_sandbox.py` | AST 安全审查 + 子进程沙箱(Job Object 256MB) |

### 数据存储

| 服务 | 文件 | 职责 |
|------|------|------|
| PerceptionStore | `perception_store.py` | 感知数据按日存储 |
| HealthStorage | `health_storage.py` | 手环传感器+睡眠按日存储 |

### 声纹识别

| 服务 | 文件 | 职责 |
|------|------|------|
| VoiceprintService | `voiceprint_service.py` | funasr ERes2NetV2 声纹注册/识别 |

### 其他

| 服务 | 文件 | 职责 |
|------|------|------|
| MultimodalAudioManager | `multimodal_audio_manager.py` | 多模态音频模型管理 |
| SSEForwarder | `sse_forwarder.py` | SSE 事件转发 |
| VoiceAssistantService | `voice_assistant_service.py` | 语音助手服务 |
| VoiceAssistantModels | `voice_assistant_models.py` | 语音助手模型 |

## 依赖关系

```
TaskScheduler (YAML定时任务)
├── TaskExecutor (执行器)
├── TaskStorage (持久化+热加载)
└── OpenCodeClient (执行任务时调用)

ScriptRunner (Python脚本任务)
├── ScriptSandbox (AST安全审查)
├── FileWatcher (scripts/热加载)
├── StdoutBridge (JSON→Gateway)
└── OpenCodeGateway (触发任务)

ComponentManager (连接管理)
└── WebSocket 广播

OpenCodeGateway (AI 通信)
├── OpenCodeClient (API 客户端)
└── SSE 事件流

PerceptionStore (感知存储)
HealthStorage (健康存储)
VoiceprintService (声纹识别)
```

## 单例模式

```python
# 懒加载单例
_storage_instance = None
def get_storage() -> StorageManager:
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = StorageManager()
    return _storage_instance

# 直接导出实例
component_manager = ComponentManager()
```

## 已移除的服务

以下服务已从原 Axeuh Home System 中移除：
- `vad_asr_service.py` — VAD + ASR 语音识别
- `stt_service.py` — STT 服务
- `unified_stt.py` — 统一 STT 接口
- `aliyun_asr_service.py` — 阿里云 ASR
- `custom_wakeword.py` — 唤醒词检测
- `sensevoice_service.py` — SenseVoice 识别
- `stock_api.py` — 股票 API

## 兼容保留的服务

以下服务在重构中被标记为"已移除"，因仍有代码引用，继续保留：
- `stt_session_manager.py` — STT 会话管理（被 opencode_gateway、task_executor、session 引用）
- `terminal_service.py` — 终端管理（被 component_manager、ws_main 引用）

## 相关文档

- `../AGENTS.md` - Backend 总览
- `../routers/AGENTS.md` - 路由层文档
