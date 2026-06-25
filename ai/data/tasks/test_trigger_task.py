"""
name: trigger_task测试
enabled: false
note: 测试context.trigger_task功能
prompt: |
  这是一个trigger_task功能测试脚本。
  脚本启动后将立即触发一次测试任务，验证trigger_task是否正常工作。
"""

import time
import json
from datetime import datetime


def run(context):
    """测试 trigger_task 功能"""
    context.log("trigger_task测试脚本启动")

    try:
        # 触发测试任务
        now = datetime.now().strftime("%H:%M:%S")
        context.trigger_task(
            "trigger_task测试",
            f"【trigger_task测试】这是一个来自自定义脚本的测试任务。触发时间: {now}。如果收到此消息，说明trigger_task正常工作。"
        )
        context.log(f"trigger_task调用完成 ({now})")
    except Exception as e:
        context.log(f"trigger_task调用失败: {e}")
        context.alert(f"trigger_task异常: {e}")

    context.heartbeat()
    context.log("测试完成，脚本退出")
