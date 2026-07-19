"""
name: 会话压缩器
enabled: true
model: deepseek-v4-flash
note: 每天 01:00 对当前主会话执行一次上下文压缩，清理过期的工具输出和对话历史。
prompt: |-
  会话压缩器，每天凌晨1点自动压缩主会话上下文。
"""

import time
import requests
from datetime import datetime


def run(context):
    """每天 01:00 触发一次会话压缩"""
    last_compacted = ""

    context.log("会话压缩器已启动，每天 01:00 执行")

    while True:
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")

        # 每天 01:00~01:05 之间执行一次
        if now.hour == 1 and today != last_compacted:
            info = context.backend_info()
            session_id = info.get("opencode_session_id", "")
            port = info.get("opencode_port", "5096")

            if not session_id:
                context.log("未找到主会话ID，跳过压缩")
            else:
                url = f"http://127.0.0.1:{port}/session/{session_id}/summarize"
                context.log(f"开始压缩会话: {session_id}")

                try:
                    resp = requests.post(url, timeout=120)
                    if resp.status_code == 200:
                        context.log(f"会话压缩完成 (状态码: {resp.status_code})")
                    else:
                        context.log(f"会话压缩失败 (状态码: {resp.status_code}, 响应: {resp.text[:100]})")
                except Exception as e:
                    context.alert(f"会话压缩异常: {e}")

            last_compacted = today

        context.heartbeat()
        time.sleep(300)
