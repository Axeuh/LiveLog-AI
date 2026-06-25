"""
健康数据存储服务

按天存储用户健康数据（心率、步数、压力、血氧、睡眠等）。
数据以 JSON 格式按天分文件存储。

目录结构:
    backend/data/health/{user_id}/{YYYY-MM-DD}.json
"""

import os
import json
import time
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

# 东八区
_CST = timezone(timedelta(hours=8))
from config.config import get_config
_cfg_hs = get_config()
_DATA_BASE = _cfg_hs.HEALTH_DIR


def _date_dir(date_str: str) -> str:
    """确保某天的数据目录存在"""
    path = os.path.join(_DATA_BASE, date_str)
    os.makedirs(path, exist_ok=True)
    return path


def _today_str() -> str:
    """获取今天的日期字符串（东八区）"""
    return datetime.now(_CST).strftime("%Y-%m-%d")


def _date_to_path(date_str: str, user_id: str = "default") -> str:
    """获取某天的健康数据文件路径"""
    return os.path.join(_date_dir(date_str), "health.json")


def save_health_data(
    samples: List[Dict],
    daily_summary: Optional[Dict] = None,
    battery_levels: Optional[List] = None,
    sleep_data: Optional[Dict] = None,
    user_id: str = "default",
) -> Dict:
    """
    保存健康数据到对应日期的文件（按样本时间戳归属日期）。

    Args:
        samples: 时间序列数据点列表 [{t, hr, steps, stress, spo2}, ...]
        daily_summary: 每日汇总 {steps, hr_resting, hr_avg, hr_max, ...}
        battery_levels: 电量记录 [{t, level}, ...]
        sleep_data: 睡眠数据 {duration, deep, light, rem, ...}
        user_id: 用户标识

    Returns:
        {"status": "ok", "dates": [...], "stats": {...}}
    """
    # 为每个样本添加可读时间戳 + 确定归属日期
    def _ts_to_date(ts_val) -> str:
        """从时间戳获取日期字符串"""
        try:
            return datetime.fromtimestamp(ts_val if isinstance(ts_val, (int, float)) else int(ts_val), _CST).strftime("%Y-%m-%d")
        except (ValueError, OSError):
            return _today_str()

    def _add_t_iso(s: dict, ts_val):
        if "t_iso" not in s:
            try:
                s["t_iso"] = datetime.fromtimestamp(ts_val if isinstance(ts_val, (int, float)) else int(ts_val), _CST).strftime("%Y-%m-%d %H:%M:%S")
            except (ValueError, OSError):
                s["t_iso"] = str(ts_val)

    # 1. samples 按日期分组
    samples_by_date: Dict[str, List[Dict]] = {}
    for s in samples:
        ts = s.get("t")
        if ts is None:
            continue
        _add_t_iso(s, ts)
        d = _ts_to_date(ts)
        samples_by_date.setdefault(d, []).append(s)

    # 2. battery_levels 并入 samples
    for b in (battery_levels or []):
        bt = b.get("t")
        if bt is None:
            continue
        d = _ts_to_date(bt)
        entry = {"t": bt}
        _add_t_iso(entry, bt)
        lv = b.get("level")
        if lv is not None:
            entry["battery"] = lv
        samples_by_date.setdefault(d, []).append(entry)

    # 3. daily_summary / sleep_data 取时间戳确定归属日期
    def _pick_date(*dicts) -> str:
        for dd in dicts:
            if dd:
                ts = dd.get("t") or dd.get("timestamp")
                if ts:
                    return _ts_to_date(ts)
        return _today_str()

    main_date = _pick_date(daily_summary, sleep_data) or _today_str()
    if not samples_by_date:
        samples_by_date[main_date] = []

    # 4. 写入每个日期的文件
    stats = {"samples": 0, "dates_updated": []}
    for date_str, date_samples in samples_by_date.items():
        path = _date_to_path(date_str, user_id)
        os.makedirs(os.path.dirname(path), exist_ok=True)

        # 读取该日已有的数据
        existing = {}
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    existing = json.load(f)
            except (json.JSONDecodeError, OSError):
                existing = {}

        # 合并 samples（去重：同 t 保留新值）
        existing_samples = existing.get("samples", [])
        seen_ts = {s["t"] for s in existing_samples}
        for s in date_samples:
            ts_val = s.get("t")
            if ts_val not in seen_ts:
                existing_samples.append(s)
                seen_ts.add(ts_val)
            else:
                for i, es in enumerate(existing_samples):
                    if es.get("t") == ts_val:
                        existing_samples[i] = s
                        break
        existing_samples.sort(key=lambda x: x.get("t", 0))

        # daily_summary / sleep_data 只写主日期
        final_daily = existing.get("daily_summary", {})
        final_sleep = existing.get("sleep_data", {})
        if date_str == main_date:
            if daily_summary:
                final_daily.update(daily_summary)
            if sleep_data:
                final_sleep.update(sleep_data)

        data = {
            "date": date_str,
            "updated_at": datetime.now(_CST).isoformat(),
            "samples": existing_samples,
            "daily_summary": final_daily,
            "sleep_data": final_sleep,
        }

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        stats["samples"] += len(date_samples)
        stats["dates_updated"].append(date_str)

        # 构建详细日志：HR 范围、步数、睡眠、电量
        log_detail = f"[Health] 已保存 {date_str}: {len(date_samples)} 条样本"
        hr_vals = [s["hr"] for s in date_samples if "hr" in s and s["hr"] is not None]
        steps_vals = [s["steps"] for s in date_samples if "steps" in s and s["steps"] is not None]
        if hr_vals:
            log_detail += f" hr={min(hr_vals)}-{max(hr_vals)} ({len(hr_vals)}pts)"
        if steps_vals:
            log_detail += f" steps={steps_vals[-1]}"
        if final_daily:
            log_detail += f" daily: {json.dumps(final_daily, ensure_ascii=False)}"
        if final_sleep:
            log_detail += f" sleep: dur={final_sleep.get('duration_min','?')}min deep={final_sleep.get('deep_min','?')} light={final_sleep.get('light_min','?')} rem={final_sleep.get('rem_min','?')}"

        logger.info(log_detail)

    stats["dates"] = stats["dates_updated"]
    return {"status": "ok", "dates": stats["dates_updated"], "stats": stats}


def query_health_data(
    date: Optional[str] = None,
    user_id: str = "default",
) -> Dict:
    """
    查询某天的健康数据。

    Args:
        date: 日期 YYYY-MM-DD，默认今天
        user_id: 用户标识

    Returns:
        当日健康数据，或 error
    """
    if date is None:
        date = _today_str()

    path = _date_to_path(date, user_id)
    if not os.path.exists(path):
        return {"status": "empty", "date": date, "message": "无数据"}

    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        data["status"] = "ok"
        return data
    except Exception as e:
        return {"status": "error", "date": date, "message": str(e)}


def list_health_dates(user_id: str = "default") -> List[str]:
    """列出有数据的所有日期"""
    if not os.path.exists(_DATA_BASE):
        return []
    dirs = [d for d in os.listdir(_DATA_BASE) if os.path.isdir(os.path.join(_DATA_BASE, d))]
    # 过滤出包含 health.json 的目录
    dates = []
    for d in sorted(dirs):
        health_file = os.path.join(_DATA_BASE, d, "health.json")
        if os.path.exists(health_file):
            dates.append(d)
    return dates
