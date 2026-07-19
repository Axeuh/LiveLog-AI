"""
脚本任务管理 API

提供脚本的查看、启停、日志查看功能。
AI 通过直接写文件创建/编辑脚本，FileWatcher 自动加载。
"""

import os
import logging
from pathlib import Path
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, Request, HTTPException, Query

from services.script_runner import get_script_runner
from config.config import get_config

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/scripts")


@router.get("")
async def list_scripts(request: Request):
    """列出所有脚本任务"""
    runner = get_script_runner()
    if runner is None:
        return {"scripts": [], "total": 0}
    
    # 从 ScriptRunner 获取运行状态
    running = runner.get_all()
    running_names = {s["name"] for s in running}
    
    # 扫描 scripts 目录获取所有脚本文件
    cfg = get_config()
    scripts_dir = Path(cfg.SCRIPTS_DIR)
    scripts = []
    
    if scripts_dir.exists():
        for f in sorted(scripts_dir.glob("*.py")):
            try:
                source = f.read_text(encoding="utf-8")
                from services.script_runner import _get_script_info
                info = _get_script_info(source)
                
                script_entry = {
                    "name": info.get("name") or f.stem,
                    "filename": f.name,
                    "enabled": info.get("enabled", False),
                    "has_frontmatter": info.get("has_frontmatter", False),
                    "note": info.get("note", ""),
                    "prompt": info.get("prompt", "")[:200],  # 截断太长
                    "file_path": str(f),
                    "status": "running" if (info.get("name") or f.stem) in running_names else "stopped",
                }
                
                # 补充运行时信息
                run_info = runner.get_status(script_entry["name"])
                if run_info.get("status") == "running":
                    script_entry["pid"] = run_info.get("pid")
                    script_entry["uptime"] = run_info.get("running_for")
                    script_entry["restart_count"] = run_info.get("restart_count", 0)
                
                scripts.append(script_entry)
            except Exception as e:
                logger.debug("读取脚本 %s 失败: %s", f.name, e)
    
    return {"scripts": scripts, "total": len(scripts)}


@router.get("/{name}")
async def get_script(name: str, request: Request):
    """获取单个脚本的详细信息"""
    runner = get_script_runner()
    if runner is None:
        raise HTTPException(503, "ScriptRunner 不可用")
    
    status = runner.get_status(name)
    if status.get("status") == "not_found":
        # 从文件系统找
        cfg = get_config()
        scripts_dir = Path(cfg.SCRIPTS_DIR)
        for f in scripts_dir.glob("*.py"):
            try:
                source = f.read_text(encoding="utf-8")
                from services.script_runner import _get_script_info
                info = _get_script_info(source)
                if info.get("name") == name or f.stem == name:
                    return {
                        "name": info.get("name") or f.stem,
                        "filename": f.name,
                        "source": source,
                        "info": info,
                        "status": "stopped",
                    }
            except Exception:
                continue
        raise HTTPException(404, f"脚本 '{name}' 不存在")
    
    # 返回完整状态
    return status


@router.post("/{name}/start")
async def start_script(name: str, request: Request):
    """启动脚本"""
    cfg = get_config()
    scripts_dir = Path(cfg.SCRIPTS_DIR)
    
    # 查找脚本文件
    script_path = None
    for f in scripts_dir.glob("*.py"):
        if f.stem == name:
            script_path = f
            break
    
    if script_path is None:
        raise HTTPException(404, f"脚本 '{name}' 未找到")
    
    runner = get_script_runner()
    if runner is None:
        raise HTTPException(503, "ScriptRunner 不可用")
    
    success = runner.start_script(str(script_path), name=name)
    if not success:
        raise HTTPException(500, f"启动脚本 '{name}' 失败")
    
    return {"message": f"脚本 '{name}' 已启动", "name": name}


@router.post("/{name}/stop")
async def stop_script(name: str, request: Request):
    """停止脚本"""
    runner = get_script_runner()
    if runner is None:
        raise HTTPException(503, "ScriptRunner 不可用")
    
    success = runner.stop_script(name)
    if not success:
        raise HTTPException(404, f"脚本 '{name}' 不存在或未运行")
    
    return {"message": f"脚本 '{name}' 已停止", "name": name}
