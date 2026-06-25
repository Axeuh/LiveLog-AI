# -*- coding: utf-8 -*-
"""
LiveLog-AI - Pytest 基础设施

本文件在测试 session 启动时执行一次，完成以下工作：

阶段一（模块载入时 - import 侧效）：
  1. 修补 main.py 模块中引用的 init_task_executor / init_task_scheduler，
     避免 lifespan 启动真正的定时任务调度器。
  2. 用内存字典替换 auth.py 的文件级认证配置，避免读写 real auth.json。

阶段二（Fixture 层）：
  - client: FastAPI TestClient，带 lifespan 自动化管理。
  - auth_headers: 调用 /login 获取 Axeuh 用户的 Bearer Token。
  - mock_tts_player: 修补 routers.tts.get_tts_player，避免外部 API 调用。
"""
import hashlib
from unittest.mock import MagicMock, AsyncMock
import pytest
from fastapi.testclient import TestClient

# 从配置读取端口，避免硬编码
from config.config import get_config
_test_cfg = get_config()
TEST_SERVER_HOST = f"localhost:{_test_cfg.BACKEND_HTTPS_PORT}"

# ============================================================
# 第一阶段：在导入 app 之前修补有副作用的模块级引用
# ============================================================

# 1.1 修补定时任务调度器和执行器
# main.py 在模块顶层做了 from services.task_scheduler import init_task_scheduler 等，
# 这些引用都绑定在 main 模块的全局命名空间中。我们在 lifespan 执行前将其替换为 Mock。
import main as _main

_mock_executor = MagicMock()
_mock_executor.execute = AsyncMock()

_mock_scheduler = MagicMock()
_mock_scheduler.start = AsyncMock()
_mock_scheduler.stop = AsyncMock()

_main.init_task_executor = MagicMock(return_value=_mock_executor)
_main.init_task_scheduler = MagicMock(return_value=_mock_scheduler)

# 1.2 修补认证配置使用内存字典而非 auth.json 文件
import auth

_test_password_hash = hashlib.sha256(b"20071011").hexdigest()
_test_auth_config = auth.AuthConfig(
    users={
        "Axeuh": auth.UserInfo(
            password_hash=_test_password_hash,
            display_name="Axeuh"
        )
    },
    tokens={}
)

# 替换 auth 模块的全局配置和 IO 函数
auth.get_auth_config = MagicMock(return_value=_test_auth_config)
auth.save_auth_config = MagicMock()
auth._auth_config = _test_auth_config  # 让全局指针直接指向测试配置

# ============================================================
# 第二阶段：导入 app（此时 lifespan 尚未被调用）
# ============================================================
from main import app


# ============================================================
# 第三阶段：Fixture 定义
# ============================================================

@pytest.fixture
def client():
    """FastAPI TestClient 实例（自动管理 lifespan 进入/退出）"""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth_headers(client):
    """登录 Axeuh 用户并返回 Bearer 认证头字典"""
    resp = client.post("/login", json={
        "username": "Axeuh",
        "password": "20071011"
    })
    assert resp.status_code == 200, f"登录失败: {resp.text}"
    data = resp.json()
    assert data["success"] is True
    return {"Authorization": f"Bearer {data['token']}"}


@pytest.fixture
def mock_vad_service():
    """
    模拟 VAD+ASR 服务
    修补 routers.stt.get_vad_asr_service，避免实际加载 torch / numpy / 阿里云 ASR。
    各测试函数只需声明此 fixture 参数即可激活修补。
    """
    service = MagicMock()
    service._is_running = False
    service._is_awake = False
    service._is_speaking = False
    service._recording = []
    service.config = MagicMock()
    service.config.SILERO_SENSITIVITY = 0.5
    service.config.SILERO_THRESHOLD = 0.5
    service.config.MIN_SPEECH_DURATION = 0.3
    service.config.MIN_SILENCE_DURATION = 0.8
    service.wake_word_config = MagicMock()
    service.wake_word_config.WAKE_WORDS = ["小贺同学"]
    service.wake_word_config.WHISPER_MODEL = "small"
    service.wake_word_config.LISTEN_TIMEOUT = 10.0
    service.wake_word_config.MIN_CONFIDENCE = -1.5
    service.wake_word_config.FUZZY_THRESHOLD = 0.7
    service.start = MagicMock(return_value=True)
    service.stop = MagicMock()
    service.on_result = MagicMock()
    service.on_speech_start = MagicMock()
    service.on_speech_end = MagicMock()
    service.on_wake_word = MagicMock()
    service.on_sleep = MagicMock()
    service.on_error = MagicMock()
    service.on_result_send = MagicMock()
    service.on_realtime = MagicMock()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr('routers.stt.get_vad_asr_service', lambda: service)
        mp.setattr('services.vad_asr_service.get_vad_service', lambda: None)
        yield service


@pytest.fixture
def mock_tts_player():
    """
    模拟 TTS 播放器（避免真实调用 MiMo API）。
    修补 routers.tts.get_tts_player，各测试声明此参数即可激活。
    """
    player = MagicMock()
    player.is_playing = False
    player.speak_async = AsyncMock(return_value=True)
    player.synthesize_to_bytes = AsyncMock(return_value=(b"mock_audio_data", None))
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr('routers.tts.get_tts_player', lambda: player)
        yield player
