"""
OTA 更新路由 — 为 Axeuh 助手提供 APK 下载服务

安全措施：
- 走主后端 HTTPS 通道
- Token 认证（通过查询参数或 Authorization 头传递登录 token）
- 文件校验（Content-MD5 / 文件大小验证）
- CORS 限制
"""

import os
import hashlib
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from auth import verify_token as verify_auth_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ota", tags=["ota"])

# === 路径常量 ===
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
_GRADLE_FILE = os.path.join(_PROJECT_ROOT, "app", "build.gradle.kts")

# === 配置（从统一配置读取） ===
from config.config import get_config
_ota_cfg = get_config()
OTA_FILE_DIR = os.environ.get("OTA_FILE_DIR", _ota_cfg.OTA_APK_DIR)


def _get_allowed_origins():
    """动态生成允许的来源列表，端口从配置读取"""
    from config.config import get_config
    cfg = get_config()
    port = cfg.BACKEND_HTTPS_PORT
    return [
        f"http://localhost:{port}",
        f"https://localhost:{port}",
    ]


def get_apk_path() -> Optional[str]:
    """获取最新的 APK 文件路径"""
    if not os.path.isdir(OTA_FILE_DIR):
        logger.warning(f"OTA 目录不存在: {OTA_FILE_DIR}")
        return None
    
    apk_files = [f for f in os.listdir(OTA_FILE_DIR) if f.endswith(".apk")]
    if not apk_files:
        logger.warning(f"OTA 目录中没有 APK 文件: {OTA_FILE_DIR}")
        return None
    
    # 取最新修改的 APK
    latest = max(apk_files, key=lambda f: os.path.getmtime(os.path.join(OTA_FILE_DIR, f)))
    return os.path.join(OTA_FILE_DIR, latest)


def _read_build_version() -> tuple:
    """从 app/build.gradle.kts 读取 versionCode 和 versionName"""
    import re
    try:
        with open(_GRADLE_FILE, "r") as f:
            content = f.read()
        vc = re.search(r'versionCode\s*=\s*(\d+)', content)
        vn = re.search(r'versionName\s*=\s*"([^"]+)"', content)
        code = int(vc.group(1)) if vc else 1
        name = vn.group(1) if vn else "1.0.0"
        return code, name
    except Exception as e:
        logger.warning(f"读取 build.gradle.kts 版本号失败: {e}")
        return 1, "1.0.0"


def get_deployed_version() -> int:
    """获取已部署 APK 的 versionCode"""
    return _read_build_version()[0]


def get_deployed_version_name() -> str:
    """获取已部署 APK 的 versionName"""
    return _read_build_version()[1]


def verify_token(token: Optional[str]) -> Optional[str]:
    """验证登录 token — 支持查询参数或 Authorization 头传入"""
    if not token:
        return None
    ok, uid = verify_auth_token(token)
    return uid if ok else None


@router.get("/check")
async def check_update(
    current_version: Optional[int] = Query(None, description="当前 App versionCode"),
):
    """
    检查更新 — 返回最新 APK 的版本信息
    
    客户端可以轮询此接口判断是否有新版本。
    """
    apk_path = get_apk_path()
    if not apk_path:
        return JSONResponse(
            content={"hasUpdate": False, "error": "服务器暂无更新文件"},
            status_code=200
        )
    
    file_size = os.path.getsize(apk_path)
    file_mtime = os.path.getmtime(apk_path)
    
    # 简单版本检测：从 ota-server 目录读取已部署的 APK 版本
    latest_version = get_deployed_version()
    
    return {
        "hasUpdate": current_version is None or latest_version > current_version,
        "latestVersionCode": latest_version,
        "latestVersionName": get_deployed_version_name(),
        "fileSize": file_size,
        "releaseDate": os.path.getmtime(apk_path),
        "changelog": "· Phase1 OTA 测试版本\n· 修复无障碍服务类名问题\n· 修复能力列表不显示问题",
    }


@router.get("/download")
async def download_apk(
    request: Request,
    token: Optional[str] = Query(None, description="登录 Bearer Token（可从 Authorization 头传入）"),
):
    """
    下载最新 APK

    认证方式（二选一）：
    1. 查询参数: ?token=xxx（兼容 App 当前实现）
    2. Authorization: Bearer xxx 头
    """
    # --- 尝试从 Authorization 头获取 token ---
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = token or auth_header[7:]
    
    # --- 验证 token ---
    user_id = verify_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="未授权：请先登录")
    logger.info(f"OTA 下载: user={user_id}")
    
    # --- 获取 APK ---
    apk_path = get_apk_path()
    if not apk_path or not os.path.isfile(apk_path):
        raise HTTPException(status_code=404, detail="更新文件不存在")
    
    # --- 计算 MD5（用于客户端校验） ---
    md5_hash = hashlib.md5()
    with open(apk_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            md5_hash.update(chunk)
    content_md5 = md5_hash.hexdigest()
    
    file_size = os.path.getsize(apk_path)
    file_name = "Axeuh助手-v1.1.0.apk"
    
    logger.info(f"OTA 下载: {apk_path} ({file_size} bytes), client: {request.client.host if request.client else 'unknown'}")
    
    return FileResponse(
        path=apk_path,
        filename=file_name,
        media_type="application/vnd.android.package-archive",
        headers={
            "Content-MD5": content_md5,
            "X-File-Size": str(file_size),
            "X-Package-Name": "com.axeuh.assistant",
        }
    )


@router.get("/info")
async def ota_info():
    """OTA 服务器信息"""
    apk_path = get_apk_path()
    if apk_path:
        file_size = os.path.getsize(apk_path)
        file_mtime = os.path.getmtime(apk_path)
        return {
            "status": "active",
            "apkFile": os.path.basename(apk_path),
            "fileSize": file_size,
            "lastModified": file_mtime,
        }
    else:
        return {"status": "no_apk"}
