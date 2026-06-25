"""
健康数据 API 路由

端点:
- POST /api/health/sync - App 上传健康数据
- POST /api/health/upload-db - 上传 Gadgetbridge DB 重新生成所有健康数据
- GET /api/health/query?date=YYYY-MM-DD - 查询某天数据
- GET /api/health/dates - 列出有数据的所有日期
"""

from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union
import logging
import json

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/health", tags=["health"])


# ============ 数据模型 ============

class SamplePoint(BaseModel):
    """单个采样点"""
    t: int = Field(..., description="Unix 时间戳(秒)")
    hr: Optional[int] = Field(None, ge=0, le=250)
    steps: Optional[int] = Field(None, ge=0)
    stress: Optional[int] = Field(None, ge=0, le=255)
    spo2: Optional[int] = Field(None, ge=0, le=100)


class BatteryPoint(BaseModel):
    t: int
    level: int = Field(..., ge=0, le=100)


class DailySummary(BaseModel):
    steps: Optional[int] = None
    hr_resting: Optional[int] = None
    hr_avg: Optional[int] = None
    hr_max: Optional[int] = None
    hr_min: Optional[int] = None
    stress_avg: Optional[int] = None
    spo2_avg: Optional[int] = None
    calories: Optional[int] = None
    training_load: Optional[int] = None


class StagePoint(BaseModel):
    t: str = Field(..., description="时间 HH:MM")
    stage: Union[int, str] = Field(..., description="阶段: deep/light/rem/awake，或数字兼容旧数据")

class SleepData(BaseModel):
    duration_min: Optional[int] = Field(None, description="总睡眠分钟")
    deep_min: Optional[int] = Field(None, description="深睡分钟")
    light_min: Optional[int] = Field(None, description="浅睡分钟")
    rem_min: Optional[int] = Field(None, description="REM 分钟")
    awake_min: Optional[int] = Field(None, description="清醒分钟")
    wakeup_time: Optional[int] = Field(None, description="起床时间戳")
    stages: Optional[List[StagePoint]] = Field(None, description="阶段时间线")


class HealthSyncRequest(BaseModel):
    """健康数据同步请求"""
    samples: List[SamplePoint] = []
    daily_summary: Optional[DailySummary] = None
    battery_levels: List[BatteryPoint] = []
    sleep_data: Optional[SleepData] = None
    client_time: Optional[str] = None


# ============ API 端点 ============


@router.post("/sync")
async def health_sync(req: HealthSyncRequest, fastapi_request: Request):
    """
    App 端定时上传健康数据。

    每 1 小时调用一次，上传期间累计的全部传感器数据。
    """
    from services.health_storage import save_health_data

    user_id = getattr(fastapi_request.state, 'user_id', None) or "default"

    samples = [s.model_dump(exclude_none=True) for s in req.samples]
    battery = [b.model_dump() for b in req.battery_levels]
    daily = req.daily_summary.model_dump(exclude_none=True) if req.daily_summary else None
    sleep = req.sleep_data.model_dump(exclude_none=True) if req.sleep_data else None

    # 构建日志摘要
    log_parts = [f"[HealthSync] user={user_id} samples={len(samples)}"]

    if samples:
        hr_vals = [s["hr"] for s in samples if "hr" in s and s["hr"] is not None]
        steps_vals = [s["steps"] for s in samples if "steps" in s and s["steps"] is not None]
        ts_min = min(s["t"] for s in samples) if samples else 0
        ts_max = max(s["t"] for s in samples) if samples else 0
        from datetime import datetime, timezone, timedelta
        cst = timezone(timedelta(hours=8))
        log_parts.append(f"period={datetime.fromtimestamp(ts_min, cst).strftime('%H:%M')}~{datetime.fromtimestamp(ts_max, cst).strftime('%H:%M')}")
        if hr_vals:
            log_parts.append(f"hr={min(hr_vals)}-{max(hr_vals)} ({len(hr_vals)}pts)")
        if steps_vals:
            log_parts.append(f"steps={steps_vals[-1]}")
    else:
        log_parts.append("(no samples)")

    if battery:
        levels = [b["level"] for b in battery]
        log_parts.append(f"battery={min(levels)}%-{max(levels)}% ({len(levels)}pts)")

    if daily:
        log_parts.append(f"daily: {json.dumps(daily, ensure_ascii=False)}")

    if sleep:
        log_parts.append(f"sleep: dur={sleep.get('duration_min','?')}min deep={sleep.get('deep_min','?')} light={sleep.get('light_min','?')} rem={sleep.get('rem_min','?')}")

    logger.info(" | ".join(log_parts))

    result = save_health_data(
        samples=samples,
        daily_summary=daily,
        battery_levels=battery,
        sleep_data=sleep,
        user_id=user_id,
    )

    return result


@router.get("/query")
async def health_query(date: Optional[str] = None, request: Request = None):
    """查询某天的健康数据"""
    from services.health_storage import query_health_data
    user_id = getattr(request.state, 'user_id', None) if request else None
    return query_health_data(date=date, user_id=user_id or "default")


@router.get("/dates")
async def health_dates(request: Request = None):
    """列出有健康数据的所有日期"""
    from services.health_storage import list_health_dates
    user_id = getattr(request.state, 'user_id', None) if request else None
    return {"dates": list_health_dates(user_id=user_id or "default")}


@router.post("/upload-db")
async def health_upload_db(file: UploadFile = File(...), request: Request = None):
    """
    接收完整的 Gadgetbridge SQLite 数据库，重新生成所有日期的 health.json
    """
    import os, time, sqlite3, tempfile
    from datetime import datetime, timezone, timedelta
    cst = timezone(timedelta(hours=8))

    user_id = getattr(request.state, 'user_id', None) if request else None
    user_id = user_id or "default"

    # 保存上传文件到临时位置
    tmp_path = os.path.join(tempfile.gettempdir(), f"gb_upload_{int(time.time())}.db")
    with open(tmp_path, "wb") as f:
        content = await file.read()
        f.write(content)

    try:
        # 解析数据库并重新生成健康数据
        conn = sqlite3.connect(tmp_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 读取所有传感器数据
        cursor.execute("""
            SELECT TIMESTAMP, HEART_RATE, STEPS, STRESS, SPO2,
                   BATTERY_LEVEL, ACTIVITY_TYPE, CALORIES
            FROM XIAOMI_ACTIVITY_SAMPLE
            WHERE TIMESTAMP > 0
            ORDER BY TIMESTAMP
        """)

        samples_by_date = {}
        for row in cursor.fetchall():
            ts = row["TIMESTAMP"]
            if ts < 1700000000:
                continue  # 合理性检查

            date_str = datetime.fromtimestamp(ts, cst).strftime("%Y-%m-%d")
            sample = {
                "t": ts,
                "t_iso": datetime.fromtimestamp(ts, cst).strftime("%Y-%m-%d %H:%M:%S")
            }
            if row["HEART_RATE"] and row["HEART_RATE"] > 0:
                sample["hr"] = row["HEART_RATE"]
            if row["STEPS"] and row["STEPS"] > 0:
                sample["steps"] = row["STEPS"]
            if row["STRESS"] and row["STRESS"] > 0:
                sample["stress"] = row["STRESS"]
            if row["SPO2"] and row["SPO2"] > 0:
                sample["spo2"] = row["SPO2"]
            if row["BATTERY_LEVEL"] and row["BATTERY_LEVEL"] > 0:
                sample["battery"] = row["BATTERY_LEVEL"]

            samples_by_date.setdefault(date_str, []).append(sample)

        # 读取睡眠数据
        sleep_by_date = {}
        cursor.execute("""
            SELECT TIMESTAMP, SLEEP_TYPE, DURATION
            FROM XIAOMI_SLEEP_TIME_SAMPLE
            WHERE TIMESTAMP > 0
            ORDER BY TIMESTAMP
        """)
        for row in cursor.fetchall():
            ts = row["TIMESTAMP"]
            date_str = datetime.fromtimestamp(ts, cst).strftime("%Y-%m-%d")
            sleep_by_date.setdefault(date_str, []).append(dict(row))

        conn.close()

        if not samples_by_date and not sleep_by_date:
            return {"status": "error", "message": "数据库中未找到有效数据"}

        # 按日期聚合睡眠数据
        sleep_summary = {}
        for date_str, sleep_rows in sleep_by_date.items():
            deep = sum(r["DURATION"] for r in sleep_rows if r["SLEEP_TYPE"] == 1)
            light = sum(r["DURATION"] for r in sleep_rows if r["SLEEP_TYPE"] == 2)
            rem = sum(r["DURATION"] for r in sleep_rows if r["SLEEP_TYPE"] == 3)
            awake = sum(r["DURATION"] for r in sleep_rows if r["SLEEP_TYPE"] == 4)
            total = deep + light + rem + awake
            if total > 0:
                sleep_summary[date_str] = {
                    "duration_min": total,
                    "deep_min": deep,
                    "light_min": light,
                    "rem_min": rem,
                    "awake_min": awake
                }

        # 从统一配置读取数据基础路径（与 health_storage.py 一致）
        from config.config import get_config
        _cfg_h = get_config()
        data_base = _cfg_h.DATA_DIR

        # 对每个有数据的日期生成并写入 health.json
        results = []
        for date_str, samples in sorted(samples_by_date.items()):
            hr_values = [s["hr"] for s in samples if "hr" in s]
            steps_values = [s["steps"] for s in samples if "steps" in s]
            spo2_values = [s["spo2"] for s in samples if "spo2" in s]
            stress_values = [s["stress"] for s in samples if "stress" in s]

            daily = {}
            if steps_values:
                daily["steps"] = steps_values[-1]  # 总步数取最后一条（累积值）
            if hr_values:
                daily["hr_resting"] = min(hr_values)
                daily["hr_avg"] = int(sum(hr_values) / len(hr_values))
                daily["hr_max"] = max(hr_values)
                daily["hr_min"] = min(hr_values)
            if stress_values:
                daily["stress_avg"] = int(sum(stress_values) / len(stress_values))
            if spo2_values:
                daily["spo2_avg"] = int(sum(spo2_values) / len(spo2_values))

            health_data = {
                "date": date_str,
                "updated_at": datetime.now(cst).isoformat(),
                "samples": samples,
                "daily_summary": daily if daily else None,
                "sleep_data": sleep_summary.get(date_str),
                "battery_levels": [],
            }

            # 写入文件（覆盖式，完全从 DB 重新生成）
            health_path = os.path.join(data_base, date_str, "health.json")
            os.makedirs(os.path.dirname(health_path), exist_ok=True)
            with open(health_path, "w", encoding="utf-8") as f:
                json.dump(health_data, f, ensure_ascii=False, indent=2)

            results.append({
                "date": date_str,
                "samples": len(samples),
                "has_sleep": date_str in sleep_summary
            })

        logger.info(f"[Health] 数据库重同步完成: {len(results)} 天")
        return {
            "status": "ok",
            "dates_processed": len(results),
            "details": results
        }

    except Exception as e:
        logger.error(f"数据库重同步失败: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except PermissionError:
            logger.warning(f"临时文件 {tmp_path} 被锁定，忽略清理")
