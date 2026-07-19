"""
统一日志配置

控制台输出：带颜色/时间/级别/消息
文件日志：完整格式（含时间/模块/级别，供调试）
"""

import os
import logging
from logging.handlers import TimedRotatingFileHandler

# ANSI 颜色
_CYAN = "\033[36m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_RED = "\033[31m"
_RESET = "\033[0m"
_BOLD = "\033[1m"

_LEVEL_COLORS = {
    logging.DEBUG: _CYAN,
    logging.INFO: _GREEN,
    logging.WARNING: _YELLOW,
    logging.ERROR: _RED,
    logging.CRITICAL: _RED + _BOLD,
}


class ColorFormatter(logging.Formatter):
    """控制台彩色格式化器"""

    def __init__(self, fmt: str):
        super().__init__(fmt)

    def format(self, record: logging.LogRecord) -> str:
        color = _LEVEL_COLORS.get(record.levelno, _RESET)
        prefix = f"{color}[{record.levelname[0]}]{_RESET}"
        time_str = self.formatTime(record, "%H:%M:%S")
        msg = super().format(record)
        # 消息本身如果带 [xxx] 标签也上色
        return f"{time_str} {prefix} {msg}"


class WindowsSafeTimedRotatingFileHandler(TimedRotatingFileHandler):
    """Windows 安全的时间轮转 Handler — 轮转失败时不抛异常，继续写原文件。"""
    _rollover_failed_logged = False  # 类级别：防止重复日志

    def doRollover(self):
        try:
            super().doRollover()
            self.__class__._rollover_failed_logged = False
        except PermissionError:
            # Windows: 文件被占用无法重命名
            # 关闭当前流，让 emit() 重新 _open() 写新内容
            if self.stream:
                self.stream.close()
                self.stream = None
            # 推进到下一个轮转时间点，避免每条日志都重复触发 shouldRollover
            import time as _time
            self.rolloverAt = self.computeRollover(int(_time.time()))
            if not self.__class__._rollover_failed_logged:
                self.__class__._rollover_failed_logged = True
                import sys
                print("[Log] 日志轮转失败（文件被占用），已跳过本次轮转", file=sys.stderr)


def setup_logging(name: str = None, log_dir: str = None, level: str = "INFO") -> logging.Logger:
    """
    配置统一日志系统。

    Args:
        name: Logger 名称，默认 None（root logger）
        log_dir: 日志目录，默认 backend/logs/
        level: 日志级别，默认 INFO

    Returns:
        配置好的 Logger 实例
    """
    if log_dir is None:
        log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
    os.makedirs(log_dir, exist_ok=True)

    # 控制台：彩色 + 时间 + 级别缩写 + 消息
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(ColorFormatter("%(message)s"))

    # 文件：完整格式（供调试）
    file_fmt = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler = WindowsSafeTimedRotatingFileHandler(
        os.path.join(log_dir, "backend.log"),
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
    )
    file_handler.setFormatter(file_fmt)

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # 避免重复添加 handler
    if not logger.handlers:
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)

    return logger
