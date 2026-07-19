"""
Axeuh Home System - Mobile API Router
手机端 API：文件浏览、报告列表、看板数据
"""
import os
import re
import json
import logging
import uuid
from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Request
from fastapi.responses import Response
from datetime import datetime

logger = logging.getLogger(__name__)

# 双根目录 — 从统一配置读取
from config.config import get_config
_cfg_m = get_config()
_AI_ROOT = _cfg_m.AI_ROOT
_DATA_ROOT = _cfg_m.DATA_DIR

router = APIRouter(tags=["mobile"])

# ── 工具函数 ──────────────────────────────────────

def _get_file_type(abs_path: str) -> str:
    """根据路径和扩展名判断文件类型"""
    if os.path.isdir(abs_path):
        return "dir"
    ext = os.path.splitext(abs_path)[1].lower()
    type_map = {
        ".json": "json", ".jsonl": "json",
        ".txt": "txt", ".md": "md",
        ".wav": "wav",
        ".jpg": "jpg", ".jpeg": "jpg", ".png": "png",
    }
    return type_map.get(ext, "file")


def _safe_resolve(relative_path: str, scope: str = "data") -> str:
    """安全解析路径，防止目录穿越

    Args:
        relative_path: 相对于 scope 根目录的路径
        scope: "data" → ai/data/, "root" → ai/

    Returns:
        解析后的绝对路径
    """
    root = _DATA_ROOT if scope == "data" else _AI_ROOT
    clean = relative_path.lstrip('/\\')
    abs_path = os.path.normpath(os.path.join(root, clean))
    if not abs_path.startswith(os.path.normpath(root)):
        raise HTTPException(status_code=403, detail="路径访问被拒绝：禁止目录穿越")
    return abs_path


def _parse_frontmatter(content: str) -> dict:
    """解析 Markdown YAML frontmatter，返回 {date, tags, title}"""
    meta = {"date": None, "tags": [], "title": ""}
    m = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
    if not m:
        return meta
    yaml_block = m.group(1)
    meta["title"] = content[m.end():].strip().split('\n')[0].lstrip('# ').strip()

    for line in yaml_block.split('\n'):
        line = line.strip()
        if line.startswith('date:'):
            val = line.split(':', 1)[1].strip().strip('"\'')
            meta["date"] = val
        elif line.startswith('tags:'):
            # tags: [tag1, tag2] 或 tags: [日志, 数据检查]
            bracket_m = re.search(r'\[(.*?)\]', line)
            if bracket_m:
                meta["tags"] = [t.strip().strip('"\'') for t in bracket_m.group(1).split(',') if t.strip()]
    return meta


def _walk_md_files(root_dir: str, max_depth: int = 5) -> list:
    """递归扫描目录下的所有 .md 文件，返回 [{path, mtime, size}]"""
    results = []
    root_dir = os.path.normpath(root_dir)
    try:
        for root, dirs, files in os.walk(root_dir):
            # 跳过 node_modules / .opencode / _template
            rel = os.path.relpath(root, root_dir).replace('\\', '/')
            skip_dirs = {'node_modules', '.opencode', '_template', '.obsidian'}
            if any(part in skip_dirs for part in rel.split('/')):
                continue

            for f in files:
                if not f.endswith('.md'):
                    continue
                full = os.path.join(root, f)
                try:
                    st = os.stat(full)
                    results.append({
                        "path": os.path.relpath(full, root_dir).replace('\\', '/'),
                        "mtime": datetime.fromtimestamp(st.st_mtime).isoformat(),
                        "size": st.st_size,
                    })
                except OSError:
                    continue
    except OSError:
        pass
    return results


# ── 文件浏览 API ─────────────────────────────────

@router.get("/files")
async def list_files(
    path: str = Query("", description="路径，空字符串表示根目录"),
    scope: str = Query("data", description='作用域: "data"(ai/data/) 或 "root"(ai/)'),
):
    """列出目录内容"""
    abs_path = _safe_resolve(path, scope)
    if not os.path.exists(abs_path):
        # 根目录不存在不是错误，返回空列表，前端显示"无数据"
        return {"entries": []}
    if not os.path.isdir(abs_path):
        raise HTTPException(status_code=400, detail="指定路径不是目录")

    try:
        entries = []
        for name in os.listdir(abs_path):
            full_path = os.path.join(abs_path, name)
            if name.startswith("."):
                continue
            file_type = _get_file_type(full_path)
            stat = os.stat(full_path)
            mtime_dt = datetime.fromtimestamp(stat.st_mtime)
            entries.append({
                "name": name,
                "type": file_type,
                "size": stat.st_size if file_type != "dir" else 0,
                "mtime": mtime_dt.isoformat(),
            })
        entries.sort(key=lambda e: (0 if e["type"] == "dir" else 1, e["name"].lower()))
        return {"entries": entries}
    except PermissionError:
        raise HTTPException(status_code=403, detail="无权限访问此路径")
    except OSError as e:
        logger.error(f"列出目录失败 {abs_path}: {e}")
        raise HTTPException(status_code=500, detail=f"读取目录失败: {str(e)}")


@router.get("/files/content")
async def read_file(
    path: str = Query(..., description="文件路径"),
    scope: str = Query("data", description='作用域: "data"(ai/data/) 或 "root"(ai/)'),
):
    """读取文件内容"""
    abs_path = _safe_resolve(path, scope)
    if not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail="文件不存在")
    if not os.path.isfile(abs_path):
        raise HTTPException(status_code=400, detail="指定路径不是文件")

    file_type = _get_file_type(abs_path)
    stat = os.stat(abs_path)

    try:
        if file_type == "json":
            with open(abs_path, "r", encoding="utf-8") as f:
                raw = f.read()
            if abs_path.endswith(".jsonl"):
                lines = [line.strip() for line in raw.split("\n") if line.strip()]
                objects = []
                parse_errors = 0
                for line in lines:
                    try:
                        objects.append(json.loads(line))
                    except json.JSONDecodeError:
                        parse_errors += 1
                return {"objects": objects, "total_lines": len(lines), "parse_errors": parse_errors}
            else:
                # 始终返回 {content: raw} 包裹原始文本，让前端 extractTextContent 统一提取
                # 此前直接 return json.loads(raw) 导致前端收到 plain object 无法提取
                return {"content": raw, "type": file_type, "size": stat.st_size}
        elif file_type in ("txt", "md"):
            with open(abs_path, "r", encoding="utf-8") as f:
                content = f.read()
            return Response(content=content, media_type="text/plain; charset=utf-8")
        else:
            try:
                with open(abs_path, "r", encoding="utf-8") as f:
                    content = f.read()
                return {"content": content, "type": file_type, "size": stat.st_size}
            except UnicodeDecodeError:
                return {"content": f"[二进制文件，大小: {stat.st_size} 字节]", "type": file_type, "size": stat.st_size, "binary": True}
    except PermissionError:
        raise HTTPException(status_code=403, detail="无权限读取此文件")
    except OSError as e:
        logger.error(f"读取文件失败 {abs_path}: {e}")
        raise HTTPException(status_code=500, detail=f"读取文件失败: {str(e)}")


# ── 原始文件直出 API (音频/图片) ──────────────────

@router.get("/files/raw")
async def read_file_raw(
    path: str = Query(..., description="文件路径"),
    scope: str = Query("data", description='作用域: "data"(ai/data/) 或 "root"(ai/)'),
):
    """直接返回二进制文件内容，支持音频/图片的正确 MIME 类型。

    用于前端 <audio> / <img> 标签的 src 直接加载。
    """
    abs_path = _safe_resolve(path, scope)
    if not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail="文件不存在")
    if not os.path.isfile(abs_path):
        raise HTTPException(status_code=400, detail="指定路径不是文件")

    ext = os.path.splitext(abs_path)[1].lower()
    media_type_map = {
        ".wav": "audio/wav",
        ".mp3": "audio/mpeg",
        ".ogg": "audio/ogg",
        ".flac": "audio/flac",
        ".aac": "audio/aac",
        ".m4a": "audio/mp4",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".svg": "image/svg+xml",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
    }
    media_type = media_type_map.get(ext, "application/octet-stream")

    try:
        with open(abs_path, "rb") as f:
            content = f.read()
        return Response(content=content, media_type=media_type)
    except PermissionError:
        raise HTTPException(status_code=403, detail="无权限读取此文件")
    except OSError as e:
        logger.error(f"读取原始文件失败 {abs_path}: {e}")
        raise HTTPException(status_code=500, detail=f"读取文件失败: {str(e)}")


# ── 文件上传 API ──────────────────────────────────

@router.post("/upload")
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
):
    """接收用户上传的文件，保存到用户专属上传目录。

    返回文件路径和访问 URL，前端可将其附加到消息中发送给 AI。
    """
    # 获取上传目录配置
    cfg = get_config()
    upload_root = cfg.UPLOAD_DIR

    # 获取用户 ID（由 AuthMiddleware 注入）
    user_id = getattr(request.state, 'user_id', 'anonymous')
    # 清理 user_id 中的非法字符（防止路径穿越）
    safe_user_id = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', str(user_id))
    if not safe_user_id or safe_user_id == 'anonymous':
        safe_user_id = 'anonymous'

    # 用户上传目录
    user_dir = os.path.join(upload_root, safe_user_id)
    os.makedirs(user_dir, exist_ok=True)

    # 生成唯一文件名：保留原始扩展名，前缀加时间戳防冲突
    original_name = file.filename or 'unknown'
    name, ext = os.path.splitext(original_name)
    if not ext:
        ext = '.bin'
    safe_name = re.sub(r'[<>:"/\\|?*]', '_', name)[:100]
    unique_name = f"{safe_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}{ext}"

    file_path = os.path.join(user_dir, unique_name)

    # 写入文件
    try:
        content = await file.read()
        with open(file_path, 'wb') as f:
            f.write(content)
    except OSError as e:
        logger.error(f"文件写入失败 {file_path}: {e}")
        raise HTTPException(status_code=500, detail=f"文件保存失败: {str(e)}")

    # 相对路径（相对于 AI_ROOT，方便 AI 访问）
    rel_path = os.path.relpath(file_path, cfg.AI_ROOT).replace('\\', '/')

    # 文件大小
    file_size = os.path.getsize(file_path)

    logger.info(f"[UPLOAD] 用户 {safe_user_id} 上传文件: {original_name} -> {rel_path} ({file_size} bytes)")

    return {
        "status": "ok",
        "file_name": original_name,
        "file_path": file_path,        # 绝对路径
        "file_rel_path": rel_path,      # 相对 AI_ROOT 的路径
        "file_size": file_size,
        "user_id": safe_user_id,
    }


# ── 报告列表 API ──────────────────────────────────

@router.get("/reports")
async def list_reports(
    tag: str = Query(None, description="按标签筛选，如 '日常理解'"),
    date_from: str = Query(None, description="起始日期（含），YYYY-MM-DD"),
    date_to: str = Query(None, description="结束日期（含），YYYY-MM-DD"),
):
    """列出所有 AI 写的 Markdown 报告。

    扫描 ai/ 下全部 .md 文件，解析 frontmatter 提取 date/tags/title。
    按日期倒序排列，支持按标签和日期范围筛选。
    """
    files = _walk_md_files(_AI_ROOT)
    reports = []

    for f in files:
        full_path = os.path.join(_AI_ROOT, f["path"])
        try:
            content = open(full_path, "r", encoding="utf-8").read(2048)  # 只读前 2KB 解析 frontmatter
        except Exception:
            continue

        meta = _parse_frontmatter(content)

        # 无 frontmatter 的文件用文件名作为标题和日期，仍然显示
        if not meta["date"] and not meta["tags"]:
            meta["title"] = meta["title"] or os.path.splitext(os.path.basename(f["path"]))[0]
            meta["date"] = f["mtime"][:10]

        # 日期：优先 frontmatter date，否则 mtime
        report_date = meta["date"] or f["mtime"][:10]

        # 筛选
        if tag and tag not in meta["tags"]:
            continue
        if date_from and report_date < date_from:
            continue
        if date_to and report_date > date_to:
            continue

        reports.append({
            "path": f["path"],
            "title": meta["title"],
            "date": report_date,
            "mtime": f["mtime"],
            "tags": meta["tags"],
        })

    # 按日期倒序
    reports.sort(key=lambda r: r["date"], reverse=True)
    return {"reports": reports}


# ── 看板聚合 API ─────────────────────────────────

@router.get("/dashboard")
async def get_dashboard(
    date: str = Query(None, description="日期 YYYY-MM-DD，默认今天"),
):
    """聚合健康 + 感知数据，返回看板所需的统计数据。

    实时计算，不依赖预生成文件。
    """
    from services.health_storage import query_health_data

    target_date = date or datetime.now().strftime("%Y-%m-%d")

    # 1. 健康数据
    health = {}
    try:
        health_data = query_health_data(target_date)
        if health_data:
            samples = health_data.get("samples", [])
            daily = health_data.get("daily_summary", {})
            sleep = health_data.get("sleep_data", {})

            hr_vals = [s.get("hr") for s in samples if s.get("hr")]
            spo2_vals = [s.get("spo2") for s in samples if s.get("spo2")]
            stress_vals = [s.get("stress") for s in samples if s.get("stress")]
            step_vals = [s.get("steps") for s in samples if s.get("steps")]

            # 步数：样本中的 steps 是区间增量值，求和得到全天总步数
            total_steps = daily.get("total_steps")
            if not total_steps and step_vals:
                # 累加增量（考虑手环重启复位的情况：下降时从头加）
                total_steps = 0
                prev = 0
                for v in step_vals:
                    if v >= prev:
                        total_steps += v - prev
                    else:
                        total_steps += v  # 复位，从头算
                    prev = v

            # 睡眠：用 stages 计算实际时长（避免跨天累计导致 duration_min 虚高）
            sleep_data = None
            if sleep:
                stages = sleep.get("stages", [])
                if stages:
                    # 从 stages 时间戳计算：第一个 stage 到最后一个 stage
                    first_t = stages[0].get("t", "00:00")
                    last_t = stages[-1].get("t", "00:00")
                    def _to_min(t_str):
                        try:
                            parts = t_str.split(":")
                            return int(parts[0]) * 60 + int(parts[1])
                        except:
                            return 0
                    f_min = _to_min(first_t)
                    l_min = _to_min(last_t)
                    if l_min >= f_min:
                        calc_dur = l_min - f_min
                    else:
                        calc_dur = (24*60 - f_min) + l_min  # 跨午夜
                    if 180 < calc_dur < 1440:  # 3h~24h 合理范围
                        sleep_data = {
                            "duration_min": calc_dur,
                            "deep_min": sleep.get("deep_min", 0),
                            "light_min": sleep.get("light_min", 0),
                            "rem_min": sleep.get("rem_min", 0),
                        }
                # stages 不可用时，用上报值（但不超过24h）
                if not sleep_data and sleep.get("duration_min", 0) < 1440:
                    sleep_data = {
                        "duration_min": sleep.get("duration_min", 0),
                        "deep_min": sleep.get("deep_min", 0),
                        "light_min": sleep.get("light_min", 0),
                        "rem_min": sleep.get("rem_min", 0),
                    }

            health = {
                "heart_rate": {
                    "avg": round(sum(hr_vals) / len(hr_vals)) if hr_vals else None,
                    "min": min(hr_vals) if hr_vals else None,
                    "max": max(hr_vals) if hr_vals else None,
                    "samples": len(hr_vals),
                },
                "spo2": {
                    "avg": round(sum(spo2_vals) / len(spo2_vals), 1) if spo2_vals else None,
                    "min": min(spo2_vals) if spo2_vals else None,
                },
                "stress": {
                    "avg": round(sum(stress_vals) / len(stress_vals)) if stress_vals else None,
                },
                "steps": total_steps,
                "sleep": sleep_data,
            }
    except Exception as e:
        logger.warning(f"看板健康数据加载失败: {e}")

    # 2. 感知数据摘要（含 GPS 和电量）
    perception_summary = {}
    gps_count = 0
    latest_battery = None
    battery_timeline = []  # [{ts, level}]
    try:
        perception_path = os.path.join(_DATA_ROOT, target_date, "perception.jsonl")
        if os.path.exists(perception_path):
            voice_count = 0
            sensor_count = 0
            app_count = 0
            with open(perception_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        t = entry.get("type", "")
                        if t == "voice":
                            voice_count += 1
                        elif t == "sensor":
                            sensor_count += 1
                            if entry.get("gps"):
                                gps_count += 1
                            batt = entry.get("phone_battery") or entry.get("battery")
                            if batt:
                                latest_battery = batt
                                t_raw = entry.get("t") or entry.get("ts") or entry.get("client_time")
                                if t_raw:
                                    battery_timeline.append({"t": t_raw, "level": batt})
                        elif t in ("app", "media", "notify"):
                            app_count += 1
                    except json.JSONDecodeError:
                        pass
            perception_summary = {
                "voice_sessions": voice_count,
                "sensor_events": sensor_count,
                "app_media_events": app_count,
                "gps_records": gps_count if gps_count > 0 else None,
                "battery": latest_battery,
                "battery_timeline": battery_timeline if battery_timeline else None,
            }
    except Exception as e:
        logger.warning(f"看板感知数据加载失败: {e}")

    return {
        "date": target_date,
        "health": health,
        "perception": perception_summary,
    }
