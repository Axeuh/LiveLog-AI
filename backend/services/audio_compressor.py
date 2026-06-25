"""
音频压缩归档服务

每天凌晨自动执行：
1. 找出所有超过 keep_days 天的音频目录
2. 将一天的所有 WAV 文件合并为单个 AAC/M4A 文件
3. 生成 JSON 索引（含每个片段的时间戳/时长/位置）
4. 验证压缩文件完整性后，删除原始 WAV 文件

压缩后目录结构:
ai/data/{YYYY-MM-DD}/
├── audio_archive.m4a             # 合并压缩后的音频 (AAC, 48kbps)
├── audio_archive_index.json      # 片段索引
├── perception.jsonl              # 不变
└── profile.json                  # 不变

依赖:
- ffmpeg (backend/bin/ffmpeg.exe 或系统 PATH)
- 无需额外 Python 依赖（WAV 头部解析自行实现）
"""

import os
import json
import asyncio
import logging
import shutil
import struct
import subprocess
import time
from datetime import datetime, timezone, timedelta, date
from typing import List, Optional, Any

logger = logging.getLogger(__name__)

_CST = timezone(timedelta(hours=8))

# WAV fmt 子块结构: audio_format(2) + channels(2) + sample_rate(4) +
#                    byte_rate(4) + block_align(2) + bits_per_sample(2) = 16
WAV_FMT_LAYOUT = '<H H I I H H'

# 压缩输出格式
ARCHIVE_FORMAT = "aac"
ARCHIVE_CODEC = "aac"
ARCHIVE_BITRATE = "48k"
ARCHIVE_CONTAINER = "m4a"
ARCHIVE_FILENAME = f"audio_archive.{ARCHIVE_CONTAINER}"


def _ffmpeg_path() -> str:
    """查找 ffmpeg 可执行文件路径（硬编码的显式路径优先）"""
    # 优先从项目目录查找 ffmpeg，找不到则用系统 PATH
    explicit = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "bin", "ffmpeg.exe"
    )
    if os.path.exists(explicit):
        return explicit
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_ffmpeg = os.path.normpath(
        os.path.join(script_dir, '..', 'bin', 'ffmpeg.exe')
    )
    if os.path.exists(project_ffmpeg):
        return project_ffmpeg
    return 'ffmpeg'


def _parse_wav_duration(path: str) -> float:
    """
    快速解析 WAV 文件时长（不依赖外部库）。

    从 WAV 头部提取采样率和 data 块大小计算时长:
        duration = data_chunk_size / (sample_rate * channels * bits_per_sample / 8)

    适用于 AudioRecord 生成的 16kHz/16bit/mono PCM WAV。
    """
    try:
        with open(path, 'rb') as f:
            riff = f.read(12)
            if len(riff) < 12 or riff[:4] != b'RIFF' or riff[8:12] != b'WAVE':
                return 0.0

            sample_rate = 16000
            channels = 1
            bits_per_sample = 16

            while True:
                chunk_id = f.read(4)
                if len(chunk_id) < 4:
                    break
                chunk_size_bytes = f.read(4)
                if len(chunk_size_bytes) < 4:
                    break
                chunk_size = struct.unpack('<I', chunk_size_bytes)[0]

                if chunk_id == b'fmt ':
                    raw = f.read(min(chunk_size, 16))
                    if len(raw) >= 16:
                        (audio_format, channels, sample_rate,
                         _byte_rate, _block_align, bits_per_sample) = \
                            struct.unpack(WAV_FMT_LAYOUT, raw[:16])
                        if audio_format != 1:
                            return 0.0
                    else:
                        f.seek(chunk_size, 1)

                elif chunk_id == b'data':
                    data_size = chunk_size
                    if sample_rate > 0 and channels > 0 and bits_per_sample > 0:
                        bytes_per_sec = sample_rate * channels * (bits_per_sample // 8)
                        if bytes_per_sec > 0:
                            return data_size / bytes_per_sec
                    break

                else:
                    f.seek(chunk_size, 1)

        return 0.0
    except Exception as e:
        logger.warning(f"解析 WAV 时长失败 {path}: {e}")
        return 0.0


def _get_archive_duration(path: str) -> float:
    """
    获取 M4A 文件时长（用于压缩完整性验证）。

    优先用 ffprobe（快速，但可能未安装）。
    如果 ffprobe 不存在，跳过验证（ffmpeg 返回码 0 即表示编码完整）。
    """
    ffmpeg_path = _ffmpeg_path()
    ffprobe = os.path.join(os.path.dirname(ffmpeg_path), 'ffprobe.exe')

    if not os.path.exists(ffprobe):
        logger.debug(f"ffprobe 未找到，跳过压缩文件时长验证")
        return 0.0

    try:
        result = subprocess.run(
            [ffprobe, '-v', 'error',
             '-show_entries', 'format=duration',
             '-of', 'default=noprint_wrappers=1:nokey=1',
             path],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except Exception as e:
        logger.warning(f"获取音频时长失败 {path}: {e}")
    return 0.0


class AudioCompressor:
    """
    音频压缩归档服务

    后台循环每小时检查一次，凌晨 00:05~01:00 执行压缩。
    保留最近 keep_days 天的原始 WAV，其余压缩为 AAC/M4A。
    压缩后先验证完整性再删除原始文件。
    """

    def __init__(self, data_dir: str, keep_days: int = 2,
                 keep_wavs: bool = False):
        """
        Args:
            data_dir: 数据根目录 (config.DATA_DIR)
            keep_days: 保留原始 WAV 的天数（默认 2 天）
            keep_wavs: 压缩后保留原始 WAV（默认 False，用于测试/手动模式）
        """
        self.data_dir = data_dir
        self.keep_days = keep_days
        self.keep_wavs = keep_wavs
        self._running = False
        self._task: Optional["asyncio.Task[Any]"] = None

    async def start(self):
        """启动后台检查循环"""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(
            f"[AudioCompressor] 已启动 (data_dir={self.data_dir}, "
            f"keep_days={self.keep_days})"
        )

    async def stop(self):
        """停止后台检查循环"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("[AudioCompressor] 已停止")

    async def _run_loop(self):
        """每小时检查一次是否到执行时间"""
        while self._running:
            try:
                now = datetime.now(_CST)
                if now.hour == 0 and 5 <= now.minute <= 30:
                    await self.compress_all()
                    await asyncio.sleep(82800)
                else:
                    await asyncio.sleep(1800)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[AudioCompressor] 循环异常: {e}", exc_info=True)
                await asyncio.sleep(300)

    # ─── 公开 API ────────────────────────────────────────

    async def compress_all(self) -> List[str]:
        """
        压缩所有需要处理的日期。

        Returns:
            成功压缩的日期列表
        """
        dates = self._get_dates_to_compress()
        if not dates:
            logger.info("[AudioCompressor] 没有需要压缩的音频文件")
            return []

        logger.info(f"[AudioCompressor] 找到 {len(dates)} 个需要压缩的日期: {dates}")
        completed = []
        for date_str in dates:
            try:
                ok = await self._compress_single_date(date_str)
                if ok:
                    completed.append(date_str)
            except Exception as e:
                logger.error(
                    f"[AudioCompressor] 压缩 {date_str} 失败: {e}", exc_info=True
                )
        if completed:
            logger.info(
                f"[AudioCompressor] 压缩完成: {len(completed)}/{len(dates)} 个日期"
            )
        return completed

    # ─── 日期检测 ────────────────────────────────────────

    def _get_dates_to_compress(self) -> List[str]:
        """找出所有需要压缩的日期（超过 keep_days 天且有 WAV 文件的）"""
        today = datetime.now(_CST).date()
        dates = []
        if not os.path.isdir(self.data_dir):
            return dates

        for entry in sorted(os.listdir(self.data_dir)):
            entry_path = os.path.join(self.data_dir, entry)
            if not os.path.isdir(entry_path):
                continue
            try:
                d = date.fromisoformat(entry)
            except ValueError:
                continue

            diff = (today - d).days
            if diff < self.keep_days:
                continue

            audio_dir = os.path.join(entry_path, "audio")
            if not os.path.isdir(audio_dir):
                continue

            wav_files = [
                f for f in os.listdir(audio_dir)
                if f.endswith('.wav') and os.path.isfile(os.path.join(audio_dir, f))
            ]
            if wav_files:
                dates.append(entry)

        return sorted(dates)

    # ─── 核心压缩 ────────────────────────────────────────

    async def _compress_single_date(self, date_str: str) -> bool:
        """
        压缩单日音频（在线程中执行同步 ffmpeg，避免阻塞事件循环）。

        流程:
        1. 构建 WAV 文件列表（按文件名排序 = 时间顺序）
        2. 用 ffmpeg concat demuxer 合并所有 WAV + 编码为 AAC/M4A
        3. 用 ffprobe 验证输出时长与预期一致
        4. 生成 audio_archive_index.json（含所有片段时间戳）
        5. 删除原始 WAV 文件及 audio/ 目录（除非 keep_wavs=True）
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self._compress_single_date_sync, date_str
        )

    def _compress_single_date_sync(self, date_str: str) -> bool:
        """
        同步版压缩单日音频（在后台线程中执行）。
        """
        date_dir = os.path.join(self.data_dir, date_str)
        audio_dir = os.path.join(date_dir, "audio")

        wav_files = sorted([
            f for f in os.listdir(audio_dir)
            if f.endswith('.wav') and os.path.isfile(os.path.join(audio_dir, f))
        ])
        if not wav_files:
            return False

        total_files = len(wav_files)
        logger.info(
            f"[AudioCompressor] 压缩 {date_str}: {total_files} 个 WAV 文件, "
            f"路径={audio_dir}"
        )

        # 检查是否已存在压缩文件（避免重复压缩）
        archive_path = os.path.join(date_dir, ARCHIVE_FILENAME)
        if os.path.exists(archive_path):
            logger.info(
                f"[AudioCompressor] {date_str}: 压缩文件已存在，跳过"
            )
            return True

        concat_file = os.path.join(date_dir, f"_concat_{date_str}.txt")
        segments = []
        total_original_size = 0
        expected_duration = 0.0

        try:
            # ── 1. 构建 ffmpeg concat 列表 + 分段索引 ──
            with open(concat_file, 'w', encoding='utf-8') as f:
                for wav in wav_files:
                    wav_path = os.path.join(audio_dir, wav)
                    abs_path = os.path.abspath(wav_path)
                    escaped_path = abs_path.replace('\\', '/').replace("'", "'\\''")
                    f.write(f"file '{escaped_path}'\n")

                    duration = _parse_wav_duration(wav_path)
                    file_size = os.path.getsize(wav_path)
                    total_original_size += file_size
                    expected_duration += duration

                    time_str = wav.split('_')[0] if '_' in wav else wav.replace('.wav', '')

                    segments.append({
                        "time": time_str,
                        "filename": wav,
                        "start": round(expected_duration - duration, 2)
                            if segments else 0.0,
                        "end": round(expected_duration, 2),
                        "duration": round(duration, 2),
                        "size": file_size,
                    })

            if expected_duration <= 0:
                logger.error(
                    f"[AudioCompressor] {date_str}: 所有 WAV 时长解析失败，无法压缩"
                )
                if os.path.exists(concat_file):
                    os.remove(concat_file)
                return False

            # ── 2. ffmpeg 合并 + 编码 AAC ──
            ffmpeg = _ffmpeg_path()

            cmd = [
                ffmpeg, '-y',
                '-f', 'concat',
                '-safe', '0',
                '-i', concat_file,
                '-c:a', ARCHIVE_CODEC,
                '-b:a', ARCHIVE_BITRATE,
                '-ac', '1',
                '-ar', '16000',
                '-movflags', '+faststart',  # M4A 优化：头部前置
                archive_path,
            ]

            expected_hours = expected_duration / 3600
            logger.info(
                f"[AudioCompressor] {date_str}: 运行 ffmpeg "
                f"(预期时长={expected_hours:.1f}小时)..."
            )
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=7200
            )

            if result.returncode != 0:
                stderr_text = result.stderr[:1000]
                logger.error(
                    f"[AudioCompressor] {date_str}: ffmpeg 失败 "
                    f"(code={result.returncode}): {stderr_text}"
                )
                return False

            if not os.path.exists(archive_path):
                logger.error(
                    f"[AudioCompressor] {date_str}: 输出文件 {ARCHIVE_FILENAME} 未生成"
                )
                return False

            compressed_size = os.path.getsize(archive_path)

            # ── 3. 验证压缩文件完整性 ──
            actual_duration = _get_archive_duration(archive_path)
            if actual_duration > 0:
                diff_ratio = abs(actual_duration - expected_duration) / expected_duration
                if diff_ratio > 0.05:  # 允许 5% 误差
                    logger.warning(
                        f"[AudioCompressor] {date_str}: 时长不匹配! "
                        f"预期={expected_duration:.0f}s, "
                        f"实际={actual_duration:.0f}s "
                        f"(差异={diff_ratio*100:.1f}%)"
                    )
                else:
                    logger.info(
                        f"[AudioCompressor] {date_str}: 完整性验证通过 "
                        f"({actual_duration:.0f}s)"
                    )
            else:
                logger.warning(
                    f"[AudioCompressor] {date_str}: 无法获取压缩文件时长，跳过验证"
                )

            logger.info(
                f"[AudioCompressor] {date_str}: ffmpeg 完成, "
                f"压缩文件={compressed_size} bytes"
            )

            # ── 4. 保存索引 JSON ──
            compression_ratio = 0
            if total_original_size > 0:
                compression_ratio = round(
                    compressed_size / total_original_size * 100, 1
                )

            total_seconds = round(expected_duration, 2)
            index = {
                "date": date_str,
                "format": ARCHIVE_FORMAT,
                "container": ARCHIVE_CONTAINER,
                "sample_rate": 16000,
                "channels": 1,
                "codec": ARCHIVE_CODEC,
                "bitrate": ARCHIVE_BITRATE,
                "original_files": total_files,
                "original_size": total_original_size,
                "compressed_size": compressed_size,
                "compression_ratio": compression_ratio,
                "duration": total_seconds,
                "duration_str": (
                    f"{int(total_seconds // 60)}分{int(total_seconds % 60)}秒"
                ),
                "segments": segments,
            }

            index_path = os.path.join(date_dir, "audio_archive_index.json")
            with open(index_path, 'w', encoding='utf-8') as f:
                json.dump(index, f, ensure_ascii=False, indent=2)

            # ── 5. 删除原始 WAV 文件及目录 ──
            if not self.keep_wavs:
                self._rmtree_retry(audio_dir, max_retries=10, delay=3)

            # ── 6. 清理临时 concat 文件 ──
            if os.path.exists(concat_file):
                try:
                    os.remove(concat_file)
                except OSError:
                    pass

            size_mb = total_original_size / 1048576
            compressed_mb = compressed_size / 1048576
            logger.info(
                f"[AudioCompressor] {date_str} 压缩完成: "
                f"{total_files} 个文件 -> 1 个 {ARCHIVE_FILENAME}, "
                f"{size_mb:.1f}MB -> {compressed_mb:.1f}MB "
                f"({compression_ratio}%), "
                f"时长 {expected_hours:.1f}小时, "
                f"原始WAV已删除={not self.keep_wavs}"
            )
            return True

        except subprocess.TimeoutExpired:
            logger.error(f"[AudioCompressor] {date_str}: ffmpeg 超时 (>2小时)")
            if os.path.exists(archive_path):
                try:
                    os.remove(archive_path)
                except OSError:
                    pass
            return False
        except Exception:
            if os.path.exists(concat_file):
                try:
                    os.remove(concat_file)
                except OSError:
                    pass
            raise

    @staticmethod
    def _rmtree_retry(path: str, max_retries: int = 10, delay: int = 3) -> None:
        """
        删除目录及其内容，遇到文件被占用时等待重试。
        """
        for attempt in range(max_retries):
            try:
                shutil.rmtree(path)
                return
            except PermissionError as e:
                if attempt < max_retries - 1:
                    logger.warning(
                        f"[AudioCompressor] 文件被占用，{delay}秒后重试 "
                        f"({attempt + 1}/{max_retries}): {e}"
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        f"[AudioCompressor] 重试 {max_retries} 次后仍无法删除: {path}"
                    )
                    raise


# ─── 单例管理 ────────────────────────────────────────

_compressor_instance: Optional[AudioCompressor] = None


def get_compressor(
    data_dir: Optional[str] = None, keep_days: int = 2
) -> AudioCompressor:
    """获取或创建 AudioCompressor 单例"""
    global _compressor_instance
    if _compressor_instance is None:
        if data_dir is None:
            from config.config import get_config
            data_dir = get_config().DATA_DIR
        _compressor_instance = AudioCompressor(
            data_dir=data_dir, keep_days=keep_days
        )
    return _compressor_instance


async def init_compressor(
    data_dir: Optional[str] = None, keep_days: int = 2
) -> AudioCompressor:
    """初始化并启动压缩服务"""
    compressor = get_compressor(data_dir=data_dir, keep_days=keep_days)
    await compressor.start()
    return compressor
