"""
声纹管理路由 — Speaker Registration & Identification API

端點:
- POST /api/screen/speakers/enroll — 注册声纹（上传音频 + 姓名）
- GET  /api/screen/speakers — 列出所有已注册声纹
- GET  /api/screen/speakers/{speaker_id} — 查询单个声纹
- DELETE /api/screen/speakers/{speaker_id} — 删除声纹
- POST /api/screen/speakers/identify — 识别音频中的说话人
- POST /api/screen/speakers/{speaker_id}/verify — 验证是否为指定说话人
"""

import os
import uuid
import tempfile
import logging
from typing import Optional, List
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import FileResponse

from services.voiceprint_service import get_voiceprint_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/screen/speakers", tags=["speakers"])


@router.post("/enroll")
async def enroll_speaker(
    file: UploadFile = File(...),
    name: str = Form(..., description="说话人姓名"),
    remark: Optional[str] = Form(None, description='备注（如客厅环境等）'),
):
    """
    注册声纹。

    上传一段清晰语音（3-10 秒），后端提取声纹特征并存储。
    支持格式: wav/mp3/m4a/ogg/webm。
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="未选择文件")

    if not name or not name.strip():
        raise HTTPException(status_code=400, detail="姓名不能为空")

    tmp_path = None
    try:
        ext = os.path.splitext(file.filename or "audio.wav")[1] or ".wav"
        suffix = ext if ext.startswith(".") else f".{ext}"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        # 非 WAV 用 ffmpeg 解码（兼容 AAC/MP3 等）
        _FFMPEG = os.path.join(os.path.dirname(os.path.dirname(__file__)), "bin", "ffmpeg.exe")
        if ext.lower() not in ('.wav', '.wave') and os.path.exists(_FFMPEG):
            import subprocess
            wav_path = tmp_path + '.wav'
            try:
                subprocess.run(
                    [_FFMPEG, '-y', '-i', tmp_path,
                     '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1', wav_path],
                    capture_output=True, timeout=30, check=True
                )
                os.unlink(tmp_path)
                tmp_path = wav_path
            except Exception as e:
                logger.warning(f"[Speakers] ffmpeg 解码失败，回退原始文件: {e}")

        # AAC 通道模拟：编码 AAC 64kbps → 解码回 WAV（与 DataCollector 链路对齐）
        if os.path.exists(_FFMPEG):
            import subprocess
            aac_path = tmp_path + '.aac'
            aac_wav_path = tmp_path + '_aac.wav'
            try:
                subprocess.run(
                    [_FFMPEG, '-y', '-i', tmp_path,
                     '-c:a', 'aac', '-b:a', '64k', '-ar', '16000', '-ac', '1', aac_path],
                    capture_output=True, timeout=30, check=True
                )
                subprocess.run(
                    [_FFMPEG, '-y', '-i', aac_path,
                     '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1', aac_wav_path],
                    capture_output=True, timeout=30, check=True
                )
                os.unlink(aac_path)
                os.unlink(tmp_path)
                tmp_path = aac_wav_path
                logger.info(f"[Speakers] AAC 通道声纹注册: {name}")
            except Exception as e:
                logger.warning(f"[Speakers] AAC 编码失败，回退原始 WAV: {e}")
                if os.path.exists(aac_path): os.unlink(aac_path)
                if os.path.exists(aac_wav_path): os.unlink(aac_wav_path)

        svc = get_voiceprint_service()
        result = svc.enroll(name.strip(), tmp_path, remark=remark or "")

        if result is None:
            raise HTTPException(status_code=500, detail="声纹注册失败（模型未加载或音频无效）")

        return {
            "status": "ok",
            "message": f"声纹注册成功: {name}",
            "speaker": result,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Speakers] 注册失败: {e}")
        raise HTTPException(status_code=500, detail=f"声纹注册失败: {str(e)}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


@router.get("")
async def list_speakers():
    """列出所有已注册声纹。"""
    svc = get_voiceprint_service()
    speakers = svc.list_speakers()
    return {
        "status": "ok",
        "count": len(speakers),
        "speakers": speakers,
    }


@router.get("/{speaker_id}/audio")
async def get_speaker_audio(speaker_id: str):
    """获取注册声纹的音频文件。"""
    svc = get_voiceprint_service()
    audio_path = svc.get_audio_path(speaker_id)
    if not audio_path:
        raise HTTPException(status_code=404, detail="声纹音频不存在")
    return FileResponse(audio_path, media_type="audio/wav",
                        filename=f"{speaker_id}.wav")
async def get_speaker(speaker_id: str):
    """查询单个声纹详情。"""
    svc = get_voiceprint_service()
    speakers = svc.list_speakers()
    for spk in speakers:
        if spk["speaker_id"] == speaker_id:
            return {"status": "ok", "speaker": spk}
    raise HTTPException(status_code=404, detail="声纹不存在")


@router.delete("/{speaker_id}")
async def delete_speaker(speaker_id: str):
    """删除声纹。"""
    svc = get_voiceprint_service()
    if svc.delete_speaker(speaker_id):
        return {"status": "ok", "message": "声纹已删除"}
    raise HTTPException(status_code=404, detail="声纹不存在")


@router.post("/identify")
async def identify_speaker(
    file: UploadFile = File(...),
    threshold: float = Form(0.50, description="相似度阈值 (0-1)"),
    top_k: int = Form(3, description="返回前 N 个匹配"),
):
    """
    识别音频中的说话人。

    返回相似度 >= threshold 的匹配结果（按相似度降序）。
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="未选择文件")

    tmp_path = None
    try:
        ext = os.path.splitext(file.filename or "audio.wav")[1] or ".wav"
        suffix = ext if ext.startswith(".") else f".{ext}"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        # 非 WAV 用 ffmpeg 解码
        _FFMPEG = os.path.join(os.path.dirname(os.path.dirname(__file__)), "bin", "ffmpeg.exe")
        if ext.lower() not in ('.wav', '.wave') and os.path.exists(_FFMPEG):
            import subprocess
            wav_path = tmp_path + '.wav'
            try:
                subprocess.run(
                    [_FFMPEG, '-y', '-i', tmp_path,
                     '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1', wav_path],
                    capture_output=True, timeout=30, check=True
                )
                os.unlink(tmp_path)
                tmp_path = wav_path
            except Exception as e:
                logger.warning(f"[Speakers] ffmpeg 解码失败，回退原始文件: {e}")

        svc = get_voiceprint_service()

        if not svc.is_ready():
            raise HTTPException(status_code=503, detail="声纹模型未加载")

        results = svc.identify(tmp_path, threshold=threshold, top_k=top_k)

        return {
            "status": "ok",
            "count": len(results),
            "matches": results,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Speakers] 识别失败: {e}")
        raise HTTPException(status_code=500, detail=f"声纹识别失败: {str(e)}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


@router.post("/{speaker_id}/verify")
async def verify_speaker(
    speaker_id: str,
    file: UploadFile = File(...),
    threshold: float = Form(0.55, description="判定为同一人的阈值 (0-1)"),
):
    """
    验证音频是否属于指定说话人。
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="未选择文件")

    tmp_path = None
    try:
        ext = os.path.splitext(file.filename or "audio.wav")[1] or ".wav"
        suffix = ext if ext.startswith(".") else f".{ext}"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        svc = get_voiceprint_service()

        if not svc.is_ready():
            raise HTTPException(status_code=503, detail="声纹模型未加载")

        result = svc.verify(tmp_path, speaker_id, threshold=threshold)

        return {
            "status": "ok",
            **result,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Speakers] 验证失败: {e}")
        raise HTTPException(status_code=500, detail=f"声纹验证失败: {str(e)}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
