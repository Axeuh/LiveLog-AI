# 解决 OpenMP 库冲突问题 (libomp.dll vs libiomp5md.dll)
import os
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

"""Axeuh Health Monitor - FastAPI Main Entry"""
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from middleware.auth_middleware import AuthMiddleware
from contextlib import asynccontextmanager
import asyncio, logging
from core.logging import setup_logging
setup_logging(None)  # 配置 root logger，所有子模块继承 INFO 级别
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)  # 关掉 uvicorn 访问日志
# 静默模型加载器的重复日志（每次分析都重载打印）
for noisy in ("sound_scene", "vad_processor", "speaker_diarization", "audio_processor", "services.multimodal_audio_manager"):
    logging.getLogger(noisy).setLevel(logging.WARNING)
logger = logging.getLogger(__name__)
from config.config import get_config
from routers import tts, agents_remote, tasks, model_config, ota, session, ws_main, voice_assistant_ws, speakers as speakers_router, maintenance as maintenance_router, notifications as notifications_router, pc as pc_router, perception as perception_router, auth_api, events
from routers.model_config import router as model_config_router
from routers.health import router as health_router
from routers.mobile import router as mobile_router
from routers.scripts import router as scripts_router
from routers.agents_remote import ws_dl_router
from services.task_scheduler import TaskScheduler, init_task_scheduler
from services.task_executor import TaskExecutor, init_task_executor
from services.script_runner import ScriptRunner, init_script_runner


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle"""
    logger.info("[Axeuh Health Monitor] Starting...")
    import asyncio
    loop = asyncio.get_running_loop()
    from services.event_loop_manager import set_main_loop
    set_main_loop(loop)

    # 启动定时任务调度器
    try:
        executor = init_task_executor()
        scheduler = init_task_scheduler(execute_callback=executor.execute)
        await scheduler.start()
    except Exception as e:
        logger.exception(f"定时任务调度器启动失败: {e}")
        raise

    # 启动脚本任务管理器
    try:
        from services.opencode_gateway import get_opencode_gateway
        script_runner = init_script_runner(gateway=get_opencode_gateway())
        await script_runner.start()
    except Exception as e:
        logger.warning(f"脚本任务管理器启动失败: {e}")

    # 后台预加载声纹识别模型
    try:
        from services.voiceprint_service import preload_voiceprint_model
        asyncio.get_running_loop().run_in_executor(None, preload_voiceprint_model)
    except Exception as e:
        logger.warning(f"声纹模型预加载失败: {e}")

    # 后台预加载音频分析模型
    try:
        from services.multimodal_audio_manager import get_multimodal_audio_manager
        asyncio.get_running_loop().run_in_executor(None, get_multimodal_audio_manager().load_models)
    except Exception as e:
        logger.warning(f"音频分析模型预加载失败: {e}")

    # 启动音频压缩归档服务（每天凌晨自动压缩旧音频）
    try:
        from services.audio_compressor import init_compressor
        await init_compressor()
    except Exception as e:
        logger.warning(f"音频压缩服务启动失败: {e}")

    yield

    # shutdown
    try:
        from services.task_scheduler import get_task_scheduler
        s = get_task_scheduler()
        if s: await s.stop()
    except Exception as e:
        logger.error(f"调度器停止失败: {e}")
    # 停止脚本任务管理器
    try:
        from services.script_runner import get_script_runner
        sr = get_script_runner()
        if sr:
            import asyncio
            await sr.stop()
    except Exception as e:
        logger.error(f"脚本任务管理器停止失败: {e}")
    # 停止音频压缩服务
    try:
        from services.audio_compressor import get_compressor
        c = get_compressor()
        if c: await c.stop()
    except Exception as e:
        logger.error(f"音频压缩服务停止失败: {e}")
    logger.info("[Axeuh Health Monitor] Shutting down...")


app = FastAPI(title="Axeuh Health Monitor", description="AI Health Monitoring System API", version="1.0.0", lifespan=lifespan)

# 统一错误处理
from core.errors import http_exception_handler, validation_exception_handler, unhandled_exception_handler
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

# 中间件
app.add_middleware(AuthMiddleware)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# Routers
app.include_router(auth_api.router)
app.include_router(tts.router, prefix="/api/screen")
app.include_router(tasks.router, prefix="/api/screen")
app.include_router(agents_remote.router, prefix="/api/agents")
app.include_router(health_router)
app.include_router(model_config_router)
app.include_router(ota.router)
app.include_router(session.router, prefix="/api/screen")
app.include_router(ws_main.router)
app.include_router(voice_assistant_ws.router)
app.include_router(speakers_router.router)
app.include_router(maintenance_router.router)
app.include_router(mobile_router, prefix="/api/mobile")
app.include_router(notifications_router.router, prefix="/api")
app.include_router(pc_router.router)
app.include_router(perception_router.router)
app.include_router(ws_dl_router)
app.include_router(events.router, prefix="/api/screen")
app.include_router(scripts_router)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "axeuh-health-monitor"}


# 移动端页面服务（必须放在最后）
_NO_CACHE = {"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"}
# asset 文件扩展名列表 - 这些文件找不到时不走 SPA fallback, 避免 MIME 类型错误
_ASSET_EXTS = ('.js', '.css', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.woff', '.woff2', '.ttf', '.eot', '.json', '.wasm')
@app.api_route("/mobile", methods=["GET", "HEAD"])
@app.api_route("/mobile/", methods=["GET", "HEAD"])
@app.api_route("/mobile/{full_path:path}", methods=["GET", "HEAD"])
async def serve_mobile(full_path: str = "index.html"):
    from pathlib import Path
    mobile_dir = Path(__file__).parent.parent / "frontend" / "mobile" / "dist"
    fp = mobile_dir / full_path
    if fp.exists() and fp.is_file():
        return FileResponse(str(fp), headers=_NO_CACHE)
    # asset 文件不存在时不返回 index.html, 避免浏览器 MIME 类型检查失败
    if any(full_path.lower().endswith(ext) for ext in _ASSET_EXTS):
        return JSONResponse({"detail": "Not Found"}, status_code=404)
    idx = mobile_dir / "index.html"
    if idx.exists():
        return FileResponse(str(idx), headers=_NO_CACHE)
    return JSONResponse({"detail": "Not Found"}, status_code=404)

