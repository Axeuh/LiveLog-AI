"""OpenCodeGateway 单元测试 - 覆盖 mock 模式和统一错误格式"""
import sys, os, pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from config.config import get_config
from services.opencode_gateway import get_opencode_gateway, _reset_gateway


@pytest.mark.asyncio
class TestOpenCodeGatewayMockMode:
    """测试 mock 模式下 Gateway"""

    @pytest.fixture(autouse=True)
    def setup(self):
        _reset_gateway()
        cfg = get_config()
        cfg._data.setdefault('features', {})['opencode_mock_enabled'] = True
        yield

    async def test_singleton(self):
        g1, g2 = get_opencode_gateway(), get_opencode_gateway()
        assert g1 is g2

    async def test_health_check(self):
        r = await get_opencode_gateway().health_check()
        assert r['ok'] is True
        assert r['data']['status'] == 'mock'

    async def test_create_session(self):
        r = await get_opencode_gateway().create_session(title='test')
        assert r['ok'] is True
        assert 'mock_' in r['data']['session_id']

    async def test_list_sessions(self):
        r = await get_opencode_gateway().list_sessions()
        assert r['ok'] is True
        assert 'sessions' in r['data']

    async def test_send_message(self):
        r = await get_opencode_gateway().send_message(session_id='s1', message='hello')
        assert r['ok'] is True and r['data']['sent'] is True

    async def test_abort_session(self):
        r = await get_opencode_gateway().abort_session(session_id='s1')
        assert r['ok'] is True and r['data']['aborted'] is True

    async def test_get_session_status(self):
        r = await get_opencode_gateway().get_session_status(session_id='s1')
        assert r['ok'] is True

    async def test_get_available_models(self):
        r = await get_opencode_gateway().get_available_models()
        assert r['ok'] is True
        assert 'providers' in r['data']

    async def test_get_active_sessions(self):
        r = await get_opencode_gateway().get_active_sessions()
        assert r['ok'] is True
        assert 'active_sessions' in r['data']

    def test_default_config(self):
        gw = get_opencode_gateway()
        assert isinstance(gw.get_default_model(), str)
        assert isinstance(gw.get_default_provider(), str)

    async def test_error_format(self):
        r = await get_opencode_gateway().health_check()
        assert set(r.keys()) == {'ok', 'data', 'error'}
        assert r['error'] is None or r['error']['source'] == 'mock'


@pytest.mark.asyncio
class TestOpenCodeGatewayOnlineMode:
    """测试 online 模式（OpenCode 不可用时优雅降级）"""

    @pytest.fixture(autouse=True)
    def setup(self):
        _reset_gateway()
        cfg = get_config()
        cfg._data.setdefault('features', {})['opencode_mock_enabled'] = False
        yield

    async def test_health_check_offline(self):
        """online 模式但 OpenCode 未运行，返回 offline 状态"""
        r = await get_opencode_gateway().health_check()
        assert r['ok'] is True
        assert r['data']['status'] in ('online', 'offline')
