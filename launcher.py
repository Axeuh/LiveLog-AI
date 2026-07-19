"""
Axeuh Health Monitor - Launcher
多进程架构，启动 OpenCode + uvicorn 后端并监控自动重启
"""

import os
import sys
import time
import ssl
import socket
import signal
import subprocess
import urllib.request
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))
import argparse


def parse_args():
    parser = argparse.ArgumentParser(description='Axeuh Health Monitor Launcher')
    parser.add_argument('--config', help='自定义配置文件路径')
    parser.add_argument('--data-dir', help='自定义数据目录')
    return parser.parse_args()


def log(service, message):
    print(f'[{service}] {message}')


def probe_port(host: str, port: int, timeout: float = 1.0) -> bool:
    """TCP 端口探测，检查端口是否已开放（accepting connections）"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        return sock.connect_ex((host, port)) == 0
    finally:
        sock.close()


def find_opencode_cmd(cmd_path: str) -> str | None:
    """查找 OpenCode 可执行文件路径"""
    if os.path.exists(cmd_path):
        return cmd_path
    import shutil
    return shutil.which(cmd_path) or shutil.which('opencode')


class ServiceManager:
    """启动、监控和重启 OpenCode + 后端服务"""

    MAX_OPENCODE_OFFSET = 10  # 端口 +1 最大偏移量

    def __init__(self):
        self.backend_proc = None
        self.opencode_proc = None
        self.running = True
        self.base_dir = Path(__file__).parent
        self.backend_dir = self.base_dir / 'backend'

        args = parse_args()
        from config.config import get_config, set_config_path
        if args.config:
            set_config_path(args.config)
        cfg = get_config()
        if args.data_dir:
            cfg._data.setdefault('data', {})['dir'] = args.data_dir

        self.python_path = cfg.CONDAPYTHON_PATH
        self.ssl_enabled = cfg.SSL_ENABLED
        self.ssl_cert = cfg.SSL_CERT
        self.ssl_key = cfg.SSL_KEY
        self.backend_port = cfg.BACKEND_PORT
        self.backend_host = cfg.BACKEND_HOST

        # OpenCode 配置
        self.opencode_cmd_path = find_opencode_cmd(cfg.OPENCODE_CMD_PATH)
        self.opencode_port = cfg.OPENCODE_PORT
        self.opencode_host = cfg.OPENCODE_HOST or '127.0.0.1'
        self.opencode_mock = cfg.OPENCODE_MOCK_ENABLED
        # 实际使用的端口（可能因幽灵进程而 +1 偏移）
        self.opencode_actual_port: int | None = None

    # ── OpenCode 管理 ─────────────────────────────────

    def is_opencode_running(self, port: int | None = None) -> bool:
        """检查 OpenCode 端口是否已开放"""
        return probe_port(self.opencode_host, port or self.opencode_port, timeout=0.5)

    def _launch_opencode_on_port(self, port: int) -> bool:
        """在指定端口启动 OpenCode，等待就绪后返回 True"""
        if self.opencode_cmd_path is None:
            log('OPENCODE', f'命令不存在，跳过启动')
            return False

        # 只用 --port，hostname 默认 127.0.0.1（也是端口探测的目标）
        cmd = [self.opencode_cmd_path, 'serve',
               '--port', str(port)]
        log('OPENCODE', f'尝试启动 (端口 {port}): {" ".join(cmd)}')

        try:
            # stderr 重定向到日志文件供排查
            opencode_log_path = self.base_dir / 'logs' / f'opencode-{port}.log'
            opencode_log_path.parent.mkdir(parents=True, exist_ok=True)
            opencode_log = str(opencode_log_path)
            log('OPENCODE', f'stderr → {opencode_log}')

            with open(opencode_log, 'a', encoding='utf-8') as lf:
                proc = subprocess.Popen(
                    cmd,
                    cwd=str(self.base_dir),
                    stdout=subprocess.DEVNULL,
                    stderr=lf,
                    creationflags=0x08000000,  # CREATE_NO_WINDOW (Windows)
                )
            log('OPENCODE', f'已启动 (PID: {proc.pid})')

            # 等端口开放（最多 15 秒）
            for _ in range(30):
                if probe_port(self.opencode_host, port, timeout=0.5):
                    log('OPENCODE', f'端口 {port} 已开放')
                    self.opencode_proc = proc
                    self.opencode_actual_port = port
                    return True
                if proc.poll() is not None:
                    log('OPENCODE', f'进程已退出 (code: {proc.returncode})，端口 {port} 不可用')
                    return False
                time.sleep(0.5)

            log('OPENCODE', f'端口 {port} 超时未开放')
            proc.terminate()
            return False
        except Exception as e:
            log('OPENCODE', f'端口 {port} 启动失败: {e}')
            return False

    def start_opencode(self):
        """启动 OpenCode 服务，遇幽灵进程时自动 +1 偏移"""
        if self.opencode_mock:
            log('OPENCODE', 'Mock 模式已启用，跳过启动')
            return False

        # 配置端口已有服务 → 直接使用
        if self.is_opencode_running(self.opencode_port):
            log('OPENCODE', f'端口 {self.opencode_port} 已有服务，直接使用')
            self.opencode_actual_port = self.opencode_port
            return True

        # 逐个端口尝试（从配置端口到 配置端口+MAX_OFFSET）
        for offset in range(self.MAX_OPENCODE_OFFSET + 1):
            port = self.opencode_port + offset

            # 非首个端口先探一下是否已被占用（running service）
            if offset > 0 and self.is_opencode_running(port):
                log('OPENCODE', f'端口 {port} 已被其他服务占用，跳过')
                continue

            if self._launch_opencode_on_port(port):
                if offset > 0:
                    log('OPENCODE', f'配置端口 {self.opencode_port} 不可用，实际使用端口 {port}')
                return True

            # 进程退出后稍等再试下一个端口
            time.sleep(1)

        log('OPENCODE',
            f'端口 {self.opencode_port}~{self.opencode_port + self.MAX_OPENCODE_OFFSET} '
            f'均不可用，跳过 OpenCode 启动（AI 功能不可用）')
        self.opencode_actual_port = None
        return False

    def stop_opencode(self):
        """优雅停止 OpenCode 进程"""
        if self.opencode_proc and self.opencode_proc.poll() is None:
            log('OPENCODE', '正在停止...')
            self.opencode_proc.terminate()
            try:
                self.opencode_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.opencode_proc.kill()
            log('OPENCODE', '已停止')
        self.opencode_actual_port = None

    def ensure_opencode(self):
        """确保 OpenCode 在运行，若崩溃则重启（最多重试 3 次）"""
        if self.opencode_mock:
            return True
        # 检查当前实际端口
        if self.opencode_actual_port and self.is_opencode_running(self.opencode_actual_port):
            return True
        for attempt in range(3):
            if self.opencode_proc and self.opencode_proc.poll() is not None:
                log('OPENCODE', f'进程已退出 (code: {self.opencode_proc.returncode})')
            self.opencode_proc = None
            log('OPENCODE', f'尝试重启 (第 {attempt + 1} 次)...')
            if self.start_opencode():
                return True
            time.sleep(2)
        log('OPENCODE', '重启失败，后端继续运行（AI 功能不可用）')
        return False

    # ── 后端管理 ─────────────────────────────────────

    def start_backend(self):
        """启动后端 uvicorn 进程"""
        python = self.python_path if os.path.exists(self.python_path) else sys.executable
        cmd = [python, '-m', 'uvicorn', 'main:app',
               '--host', self.backend_host, '--port', str(self.backend_port)]

        if self.ssl_enabled and os.path.exists(self.ssl_cert) and os.path.exists(self.ssl_key):
            cmd += ['--ssl-certfile', self.ssl_cert, '--ssl-keyfile', self.ssl_key]
            log('BACKEND', 'HTTPS mode (SSL enabled)')
        else:
            log('BACKEND', 'HTTP mode (no SSL)')

        log('BACKEND', f'Starting on {self.backend_host}:{self.backend_port}...')
        self.backend_proc = subprocess.Popen(cmd, cwd=str(self.backend_dir))
        log('BACKEND', f'Started (PID: {self.backend_proc.pid})')

    def wait_health(self):
        """等待后端健康检查通过"""
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        protocol = 'https' if self.ssl_enabled and os.path.exists(self.ssl_cert) and os.path.exists(self.ssl_key) else 'http'
        url = f'{protocol}://127.0.0.1:{self.backend_port}/health'
        for i in range(10):
            try:
                with urllib.request.urlopen(url, timeout=2, context=ctx):
                    log('BACKEND', 'Health check passed')
                    return
            except Exception:
                time.sleep(0.5)
        log('BACKEND', 'Health check failed')

    def stop_backend(self):
        """优雅停止后端进程"""
        if self.backend_proc and self.backend_proc.poll() is None:
            log('SYSTEM', 'Stopping backend...')
            self.backend_proc.terminate()
            try:
                self.backend_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.backend_proc.kill()
            log('SYSTEM', 'Backend stopped')

    def run(self):
        """主循环：启动 OpenCode → 启动后端 → 监控自动重启"""
        log('SYSTEM', 'Axeuh Health Monitor Launcher')

        def handle_signal(signum, frame):
            self.running = False

        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)

        # 1. 启动 OpenCode（后端依赖它）
        self.start_opencode()

        # 2. 启动后端
        self.start_backend()
        self.wait_health()

        # 3. 监控循环
        while self.running:
            # 检查 OpenCode（异步重启，不阻塞后端）
            if self.opencode_proc is not None:
                if self.opencode_proc.poll() is not None:
                    log('OPENCODE', f'进程意外退出 (code: {self.opencode_proc.returncode})')
                    self.opencode_proc = None
                    self.ensure_opencode()

            # 检查后端
            if self.backend_proc and self.backend_proc.poll() is not None:
                log('BACKEND',
                    f'Process exited (code: {self.backend_proc.returncode}), restarting in 2s...')
                time.sleep(2)
                self.start_backend()
                self.wait_health()

            time.sleep(1)

        # 4. 停止
        self.stop_backend()
        self.stop_opencode()


if __name__ == '__main__':
    ServiceManager().run()
