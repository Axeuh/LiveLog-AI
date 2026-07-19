"""
会话历史保存器
每次消息发送后 / 每30分钟定时，将 OpenCode 会话历史保存为 Markdown 文件
到 ai/data/{date}/，供 AI 复盘自检和溯源。

消息转 MD 规则：
- text -> 完整保留
- reasoning -> 跳过
- step-start/step-finish -> 跳过
- bash -> `bash` 参数 + 输出截取 <=300字
- task -> 替换为 [[会话-xxx]] 指针（前台）或 (后台, ses_id)（后台）
- look_at -> 完整保留
- 其他工具 -> `工具名` 参数 + 输出截取 <=200字
"""
import asyncio
import json
import logging
import os
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional, Callable, Dict, List, Any, Tuple

from config.config import get_config
from services.opencode_gateway import get_opencode_gateway

logger = logging.getLogger(__name__)

_DEDUP_SECONDS = 3600  # 消息触发时1小时内去重
_LOOP_INTERVAL = 1800
_BASH_OUTPUT_MAX = 300
_TOOL_OUTPUT_MAX = 200
_TASK_PROMPT_MAX = 100
_LOOKAT_OUTPUT_MAX = 5000

_loop_task: Optional[asyncio.Task] = None
_last_save_times: Dict[str, float] = {}  # session_id -> last_save_time


def _ts_to_dt(ms_epoch: float) -> datetime:
    return datetime.fromtimestamp(ms_epoch / 1000, tz=timezone(timedelta(hours=8)))


def _ts_to_date(ms_epoch: float) -> str:
    return _ts_to_dt(ms_epoch).strftime("%Y-%m-%d")


def _ts_to_time(ms_epoch: float) -> str:
    return _ts_to_dt(ms_epoch).strftime("%H:%M")


def _trim(text: str, max_len: int) -> str:
    if not text:
        return ""
    text = text.strip()
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


def _quote_block(text: str) -> str:
    """给每行加 > 前缀，防止 AI 回复中的 MD 语法破坏文档结构"""
    if not text:
        return text
    lines = text.split("\n")
    quoted = []
    for line in lines:
        if line.strip():
            quoted.append("> " + line)
        else:
            quoted.append(">")
    return "\n".join(quoted)


def _data_dir(date_str: str) -> Path:
    cfg = get_config()
    return Path(cfg.AI_ROOT) / "data" / date_str

def _session_dir(date_str: str) -> Path:
    return _data_dir(date_str) / "会话"


def _extract_text(parts: List[Dict]) -> str:
    texts = []
    for p in parts:
        if p.get("type") == "text" and not p.get("synthetic") and not p.get("ignored"):
            texts.append(p.get("text", ""))
    return "".join(texts)


def _format_tool_line(tool: str, part: Dict) -> str:
    state = part.get("state", {})
    output = state.get("output", "")
    inp = part.get("input", {})
    inp_str = str(inp) if isinstance(inp, dict) else str(inp)

    if tool == "bash":
        return "`bash` %s -> %s" % (_trim(inp_str, 100), _trim(output, _BASH_OUTPUT_MAX))

    elif tool == "task":
        prompt = ""
        try:
            inp_dict = json.loads(inp_str) if isinstance(inp_str, str) else inp_str
            if isinstance(inp_dict, dict):
                prompt = inp_dict.get("prompt", inp_dict.get("description", ""))
        except (json.JSONDecodeError, TypeError):
            prompt = _trim(inp_str, _TASK_PROMPT_MAX)
        is_bg = "run_in_background" in inp_str and "true" in inp_str
        sid = ""
        for w in output.split():
            if w.startswith("ses_") and len(w) > 10:
                sid = w[:30]
                break
            if w.startswith("bg_") and len(w) > 6:
                sid = w[:20]
                break
        agent_title = _trim(prompt, _TASK_PROMPT_MAX) or "子智能体"
        suffix = " (后台, %s)" % sid if is_bg and sid else ""
        return "`task` %s -> [[会话-%s]]%s" % (agent_title, _trim(agent_title, 20), suffix)

    elif tool == "look_at":
        return "`look_at` %s -> %s" % (_trim(inp_str, 100), _trim(output, _LOOKAT_OUTPUT_MAX))

    elif tool in ("step-start", "step-finish"):
        return ""

    else:
        return "`%s` %s -> %s" % (tool, _trim(inp_str, 80), _trim(output, _TOOL_OUTPUT_MAX))


def messages_to_markdown(messages: List[Dict], header_title: str) -> Dict[str, str]:
    """将消息按日期分组后转 MD，返回 {date: md_text}"""
    if not messages:
        return {}

    # 按日期分组
    groups: Dict[str, List[Dict]] = {}
    for msg in messages:
        ts = msg.get("info", {}).get("time", {}).get("created", 0)
        if not ts:
            continue
        date = _ts_to_date(ts)
        groups.setdefault(date, []).append(msg)

    result = {}
    for date, msgs in sorted(groups.items()):
        lines = ["# %s - %s" % (header_title, date), ""]
        for msg in msgs:
            info = msg.get("info", {})
            parts = msg.get("parts", [])
            role = info.get("role")
            time_ms = info.get("time", {}).get("created", 0)
            time_str = _ts_to_time(time_ms)

            if role == "user":
                text = _extract_text(parts)
                if not text:
                    continue
                lines.append("## %s" % time_str)
                lines.append("**用户**: %s" % text)
                lines.append("")

            elif role == "assistant":
                text = _extract_text(parts)
                if not text and not any(p.get("type") == "tool" for p in parts):
                    continue
                lines.append("## %s" % time_str)
                lines.append("**AI**:")
                quote_lines = []
                if text:
                    for line in text.split("\n"):
                        quote_lines.append("> " + line if line.strip() else ">")
                for p in parts:
                    if p.get("type") == "tool":
                        tl = _format_tool_line(p.get("tool", ""), p)
                        if tl:
                            quote_lines.append("> " + tl)
                lines.extend(quote_lines)
                lines.append("")

        result[date] = "\n".join(lines)

    return result


async def save_session_history(
    session_id: str,
    header_title: str = "会话",
    gateway=None,
) -> int:
    """
    获取会话消息，按日期分组保存。
    只保存今天和昨天的数据，文件已存在则跳过。
    返回保存的文件数量
    """
    gw = gateway or get_opencode_gateway()

    # 1小时消息触发去重
    now = time.time()
    last = _last_save_times.get(session_id, 0)
    if now - last < _DEDUP_SECONDS:
        return 0
    _last_save_times[session_id] = now

    # 只处理今天和昨天
    tz = timezone(timedelta(hours=8))
    today_dt = datetime.now(tz)
    today = today_dt.strftime("%Y-%m-%d")
    yesterday = (today_dt - timedelta(days=1)).strftime("%Y-%m-%d")

    result = await gw.get_session_messages(session_id, limit=500)
    if not result["ok"]:
        logger.warning("[SessionSaver] 获取消息失败 %s: %s", session_id, result.get("error", {}))
        return 0

    messages = result["data"].get("messages", [])
    if not messages:
        return 0

    by_date = messages_to_markdown(messages, header_title)
    if not by_date:
        return 0

    saved = 0
    safe_name = header_title.replace(" ", "_").replace("/", "-")[:40]

    for date_str, md_text in sorted(by_date.items()):
        # 跳过非今天/昨天的日期
        if date_str not in (today, yesterday):
            continue

        data_dir = _session_dir(date_str)
        data_dir.mkdir(parents=True, exist_ok=True)
        filepath = data_dir / ("会话-%s.md" % safe_name)

        # 文件已存在则跳过
        if filepath.exists():
            continue

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(md_text)
        saved += 1

    if saved:
        logger.info("[SessionSaver] 已保存: 会话-%s.md (%d条, %d天)", safe_name, len(messages), saved)
    return saved


async def save_child_sessions(parent_session_id: str, gateway=None) -> int:
    gw = gateway or get_opencode_gateway()
    saved_count = 0

    try:
        result = await gw.get_session_children(parent_session_id)
        if not result["ok"]:
            return 0

        children = result["data"].get("children", [])
        for child in children:
            child_id = child.get("id") or child.get("session_id")
            if not child_id:
                continue
            child_title = child.get("title") or child.get("slug") or "子智能体"
            title = _trim(child_title.split(" (@")[0], 30)
            await save_session_history(child_id, title, gateway=gw)
            saved_count += 1

    except Exception as e:
        logger.error("[SessionSaver] 子会话保存异常: %s", e)

    return saved_count
