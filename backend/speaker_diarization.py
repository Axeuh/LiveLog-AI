"""
说话人日志模块 (Speaker Diarization)
使用 MFCC 特征 + 层次聚类区分不同说话人。

零外部依赖：只使用 librosa + sklearn + numpy。
对短音频(5s以下)和长音频(30s以上)都做适配，自动估计说话人数。
"""

import logging
import numpy as np
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

# 默认参数
WINDOW_SEC = 1.5       # 滑窗长度（秒）
HOP_SEC = 0.75         # 滑窗步进（秒）
MIN_SPEECH_FRAMES = 5  # 最少有效帧数才进行聚类
SPEAKER_COLORS = ["#4A90D9", "#E57272", "#50B86C", "#F5A623",
                  "#7B68EE", "#2ECC71", "#E74C3C", "#3498DB"]


class SpeakerDiarizer:
    """
    说话人日志处理器。
    使用 MFCC 39维特征（13 MFCC + 13 delta + 13 delta-delta）+ 层次聚类。
    自动估计说话人数，短音频降为1个说话人。
    """

    def __init__(self, device: str = "cpu"):
        self.device = device  # MFCC 方案实际只用 CPU

    def diarize(self, audio_path: str) -> Dict[str, Any]:
        """
        对音频文件进行说话人日志分析。

        Args:
            audio_path: 16kHz 单声道 WAV 文件路径

        Returns:
            {
                "success": bool,
                "n_speakers": int,
                "segments": [{"start": float, "end": float, "speaker": int}],
                "timeline": [{"start": float, "end": float, "speaker": int,
                              "speaker_label": str, "color": str}],
            }
        """
        try:
            import librosa
        except ImportError:
            return {"success": False, "error": "librosa not installed"}

        # 1. 加载音频
        y, sr = librosa.load(audio_path, sr=16000)
        duration = len(y) / sr

        if duration < 1.0:
            return {
                "success": True,
                "n_speakers": 1,
                "segments": [{"start": 0.0, "end": duration, "speaker": 0}],
                "timeline": [],
            }

        # 2. 提取 MFCC 特征
        mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13,
                                     hop_length=int(sr * 0.025))
        mfcc_delta = librosa.feature.delta(mfcc)
        mfcc_delta2 = librosa.feature.delta(mfcc, order=2)
        mfcc_full = np.concatenate([mfcc, mfcc_delta, mfcc_delta2], axis=0)

        # 3. 计算每帧能量（用于过滤非语音帧）
        energy = librosa.feature.rms(y=y, hop_length=int(sr * 0.025))[0]  # (n_frames,)
        energy_min = energy.min()
        energy_max = energy.max()
        if energy_max > energy_min:
            energy_norm = (energy - energy_min) / (energy_max - energy_min)
        else:
            energy_norm = np.ones_like(energy)

        # 4. 滑窗聚合 -> 帧嵌入（带能量过滤）
        win_frame = int(WINDOW_SEC / 0.025)
        hop_frame = int(HOP_SEC / 0.025)
        n_frames = mfcc_full.shape[1]

        embeddings = []
        frame_timestamps = []
        frame_energies = []

        for start in range(0, n_frames - win_frame + 1, hop_frame):
            end = start + win_frame

            # 窗口内的平均能量
            win_energy = float(energy_norm[start:end].mean())
            # 噪声环境下仅保留中等以上能量窗口（过滤静音+纯噪声）
            if win_energy < 0.3:
                continue

            seg = mfcc_full[:, start:end]
            emb = np.mean(seg, axis=1)
            embeddings.append(emb)
            frame_timestamps.append((start * 0.025, end * 0.025))
            frame_energies.append(win_energy)

        if len(embeddings) < 3:  # 太少语音帧，直接判定 1 人
            return {
                "success": True,
                "n_speakers": 1,
                "segments": [{"start": 0.0, "end": duration, "speaker": 0}],
                "timeline": [],
            }

        embeddings = np.array(embeddings)  # (N, 39)

        # 4. 估计说话人数
        n_speakers = self._estimate_n_speakers(embeddings, duration)

        # 5. 聚类
        from sklearn.cluster import AgglomerativeClustering
        clustering = AgglomerativeClustering(
            n_clusters=n_speakers,
            metric="cosine",
            linkage="average",
        )
        labels = clustering.fit_predict(embeddings)

        # 6. 合并相邻同说话人段
        segments = []
        current_label = int(labels[0])
        current_start = frame_timestamps[0][0]
        current_end = frame_timestamps[0][1]

        for i in range(1, len(labels)):
            label = int(labels[i])
            if label == current_label:
                current_end = frame_timestamps[i][1]
            else:
                segments.append({
                    "start": round(current_start, 2),
                    "end": round(current_end, 2),
                    "speaker": current_label,
                })
                current_label = label
                current_start = frame_timestamps[i][0]
                current_end = frame_timestamps[i][1]

        segments.append({
            "start": round(current_start, 2),
            "end": round(current_end, 2),
            "speaker": current_label,
        })

        # 7. 合并距离太近的段（<0.5s 间隔的同说话人段合并）
        segments = self._merge_close_segments(segments)

        # 8. 为每个说话人分配稳定标签（按首次出现排序）
        segments, n_speakers = self._reorder_speaker_labels(segments)

        # 9. 生成时间线（前端友好格式）
        timeline = []
        for seg in segments:
            timeline.append({
                **seg,
                "speaker_label": f"说话人 {seg['speaker'] + 1}",
                "color": SPEAKER_COLORS[seg['speaker'] % len(SPEAKER_COLORS)],
            })

        logger.info(
            f"说话人日志完成: {n_speakers} 个说话人, "
            f"{len(segments)} 个片段"
        )

        return {
            "success": True,
            "n_speakers": n_speakers,
            "segments": segments,
            "timeline": timeline,
        }

    def _estimate_n_speakers(
        self, embeddings: np.ndarray, duration: float
    ) -> int:
        """自动估计说话人数。"""
        if duration < 5.0 or len(embeddings) < MIN_SPEECH_FRAMES:
            return 1

        n_windows = len(embeddings)
        # 最多不超过 5 个说话人（家庭/聚会场景可有多人）
        max_speakers = min(5, max(1, n_windows // 3))

        if max_speakers <= 1:
            return 1

        # 用肘部法则（简化版）：计算不同 K 值的聚类内距离
        from sklearn.metrics import pairwise_distances
        from sklearn.cluster import AgglomerativeClustering

        best_k = 1
        best_score = float("inf")
        dist_matrix = pairwise_distances(embeddings, metric="cosine")

        for k in range(1, max_speakers + 1):
            clustering = AgglomerativeClustering(
                n_clusters=k, metric="cosine", linkage="average"
            )
            labels = clustering.fit_predict(embeddings)

            # 计算 Davies-Bouldin 类分数（越小越好）
            # 简化：计算每个点到其聚类中心的平均距离
            score = 0
            for c in range(k):
                mask = labels == c
                if mask.sum() == 0:
                    continue
                cluster_pts = embeddings[mask]
                center = cluster_pts.mean(axis=0)
                dists = pairwise_distances(cluster_pts, center.reshape(1, -1),
                                           metric="cosine")
                score += dists.mean()

            score /= k

            # 选择第一个肘部：分数有明显下降
            if score < best_score * 0.85:  # 显著改善
                best_score = score
                best_k = k
            elif k > 1:
                # 不再显著改善 -> 肘部
                break

        return best_k

    def _merge_close_segments(
        self, segments: List[Dict], gap_threshold: float = 0.5
    ) -> List[Dict]:
        """合并间隔小于阈值的同说话人段。"""
        if not segments:
            return segments

        merged = [segments[0]]
        for seg in segments[1:]:
            last = merged[-1]
            if (seg["speaker"] == last["speaker"]
                    and seg["start"] - last["end"] < gap_threshold):
                # 合并
                last["end"] = max(last["end"], seg["end"])
            else:
                merged.append(seg)

        return merged

    def _reorder_speaker_labels(
        self, segments: List[Dict]
    ) -> Tuple[List[Dict], int]:
        """按首次出现顺序重新分配说话人标签。"""
        seen = {}
        next_label = 0
        for seg in segments:
            spk = seg["speaker"]
            if spk not in seen:
                seen[spk] = next_label
                next_label += 1
            seg["speaker"] = seen[spk]

        return segments, next_label

    def align_with_segments(
        self,
        diarization_result: Dict[str, Any],
        asr_segments: List[Dict],
    ) -> List[Dict]:
        """
        将说话人标签对齐到 ASR 文本段。
        每个 ASR segment 分配在时间上重叠最多的说话人。

        Args:
            diarization_result: diarize() 返回的结果
            asr_segments: AudioProcessor.process() 返回的 segments

        Returns:
            新增 speaker 字段的 asr_segments
        """
        timeline = diarization_result.get("timeline", [])
        if not timeline:
            return asr_segments

        enriched = []
        for seg in asr_segments:
            seg_start = seg.get("start", 0)
            seg_end = seg.get("end", 0)
            seg_mid = (seg_start + seg_end) / 2

            # 找到覆盖 segment 中点的说话人
            assigned_speaker = None
            for tl in timeline:
                if tl["start"] <= seg_mid <= tl["end"]:
                    assigned_speaker = tl
                    break

            # 如果没找到，找最近的
            if assigned_speaker is None:
                min_dist = float("inf")
                for tl in timeline:
                    dist = min(abs(seg_mid - tl["start"]),
                               abs(seg_mid - tl["end"]))
                    if dist < min_dist:
                        min_dist = dist
                        assigned_speaker = tl

            enriched.append({
                **seg,
                "speaker": assigned_speaker["speaker"] if assigned_speaker else 0,
                "speaker_label": assigned_speaker["speaker_label"]
                if assigned_speaker else "说话人 1",
                "speaker_color": assigned_speaker["color"]
                if assigned_speaker else SPEAKER_COLORS[0],
            })

        return enriched


# 便捷函数
def create_diarizer(device: str = "cpu") -> SpeakerDiarizer:
    """创建说话人日志处理器。"""
    return SpeakerDiarizer(device=device)
