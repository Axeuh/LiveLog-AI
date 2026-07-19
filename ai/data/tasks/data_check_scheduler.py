"""
name: 数据检查调度器
enabled: true
model: deepseek-v4-flash
note: 合并替代原来的11个数据检查YAML（01~11-data-check-*.yaml）。每2小时触发一次数据检查流程。
  00点窗口覆盖前一天22:00~00:00（跨日），04点覆盖当天00:00~04:00（夜间4小时），其余每2小时。
  08:00~22:00时段额外启动反馈子智能体。
prompt: |-
  数据检查调度器，每2小时自动触发数据检查流水线。
"""
import json
import time
from datetime import datetime, timedelta
from pathlib import Path

# 持久化状态文件路径（wrapper exec环境下__file__不可用，使用cwd相对路径）
STATE_FILE = "ai/data/tasks/.data_check_state.json"


def _load_state():
    """从磁盘加载上次触发记录"""
    try:
        return json.loads(Path(STATE_FILE).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _save_state(state):
    """将触发记录持久化到磁盘"""
    try:
        Path(STATE_FILE).write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    except (OSError, IOError):
        pass

# 时间窗口定义: {触发小时: (开始时间, 结束时间)}
# 00点特殊：覆盖前一天22:00~00:00
# 04点：覆盖当天00:00~04:00（夜间数据少，合并4小时）
WINDOWS = {
    0:  ("22:00", "00:00"),
    4:  ("00:00", "04:00"),
    6:  ("04:00", "06:00"),
    8:  ("06:00", "08:00"),
    10: ("08:00", "10:00"),
    12: ("10:00", "12:00"),
    14: ("12:00", "14:00"),
    16: ("14:00", "16:00"),
    18: ("16:00", "18:00"),
    20: ("18:00", "20:00"),
    22: ("20:00", "22:00"),
}

# 启动反馈子智能体的时段（08:00~22:00）
FEEDBACK_HOURS = {8, 10, 12, 14, 16, 18, 20, 22}


def _build_prompt(trigger_hour, date_str, start, end):
    """构建发给AI的完整提示词"""
    time_label = f"{trigger_hour:02d}点"
    window = f"{start}~{end}"
    name = f"数据检查_{time_label}"

    lines = [
        f"【数据检查 - {name}】 按子智能体调度流程执行, 覆盖时段: {window}。",
        "",
        "不要自己写理解, 按以下流程执行：",
        f"1. 运行: python ai/analysis/fact_extractor.py {date_str} --hours {window}",
        f"2. 启动子智能体: task(subagent_type=\"general\", load_skills=[], prompt=\""
        f"请阅读 ai/agents/01-data-check.md 执行。参数: date={date_str}, start={start}, end={end})",
        "3. 子智能体自行运行 check_coverage.py",
        "4. 漏时段自行补充",
        "5. 自行 git add/commit",
        "6. 主智能体验收（不需要发通知；子智能体也不发送通知）",
    ]

    if trigger_hour in FEEDBACK_HOURS:
        lines.append(
            "7. 启动反馈子智能体: task(subagent_type=\"general\", load_skills=[], prompt=\""
            f"请阅读 ai/agents/05-feedback-agent.md 执行。参数: date={date_str}, period={window}\")"
        )

    return "\n".join(lines)


def run(context):
    """自循环调度：每30秒检查当前时间，在对应整点触发数据检查"""
    # {小时: 上次触发日期}，用于同一天不重复触发（持久化到磁盘防重启丢失）
    last_triggered = _load_state()
    if last_triggered:
        context.log(f"从磁盘恢复调度状态: {last_triggered}")

    context.log("数据检查调度器已启动，覆盖时段: " + ", ".join(f"{h:02d}:00" for h in sorted(WINDOWS)))

    while True:
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        hour = now.hour

        if hour in WINDOWS and last_triggered.get(str(hour)) != today:
            start, end = WINDOWS[hour]

            # 00点算前一天的日期（跨日窗口）
            if hour == 0:
                target_date = (now - timedelta(days=1)).strftime("%Y-%m-%d")
            else:
                target_date = today

            prompt = _build_prompt(hour, target_date, start, end)
            task_name = f"数据检查_{hour:02d}点"
            context.trigger_task(task_name, prompt)
            context.log(f"已触发 {task_name} (日期={target_date}, 窗口={start}~{end})")
            last_triggered[str(hour)] = today
            _save_state(last_triggered)

        context.heartbeat()
        time.sleep(300)
