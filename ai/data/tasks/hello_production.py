"""
name: 生产测试脚本
enabled: false
note: 完整功能演示，仅注释了发送JSON的部分
prompt: |
  这是一个自定义脚本的完整功能演示。
  展示了 frontmatter、数据读取、条件判断、心跳等能力。
"""

import time
import json
from os.path import exists, getsize


def run(context):
    """生产测试 - 展示脚本的完整能力"""
    context.log("脚本启动成功")

    while True:
        # 1. 读取数据
        if exists("ai/data/perception.jsonl"):
            size = getsize("ai/data/perception.jsonl")
            context.log(f"感知数据文件大小: {size} bytes")
        else:
            context.log("暂无感知数据")

        if exists("ai/data/health.json"):
            data = context.read_file("ai/data/health.json")
            if data:
                context.log(f"取到健康数据，长度: {len(data)} 字符")
        else:
            context.log("暂无健康数据")

        # 2. 条件判断
        # if 某些条件满足:
        #     context.alert("发现异常")
        #     context.trigger_task("检查", "请分析数据")

        # 3. 打印日志
        context.log("本轮检查完成")

        # 4. 保活信号（必须）
        context.heartbeat()

        # 5. 控制频率
        time.sleep(60)
