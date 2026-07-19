"""
叹气/深呼吸检测器
基于频谱特征：叹气在 2-8kHz 有能量突增，低频谐波弱（区别于说话）。
与 VAD 配合使用：只在非语音区域检测（减少误报）。
"""
import numpy as np
import logging

logger = logging.getLogger(__name__)


def detect_breaths(audio: np.ndarray, sr: int = 16000,
                   vad_timeline: list = None) -> list:
    """
    检测音频中的叹气/深呼吸事件。

    Args:
        audio: 音频波形 (numpy array)
        sr: 采样率
        vad_timeline: VAD 语音段 [{"start": float, "end": float}, ...]，
                      用于跳过说话区域减少误报

    Returns:
        [{"start": float, "end": float, "type": str, "type_cn": str, "confidence": float}, ...]
    """
    import librosa

    duration = len(audio) / sr
    if duration < 0.5:
        return []

    hop_length = int(0.010 * sr)   # 10ms
    total_frames = int(duration / 0.010)

    # 1. 计算频谱
    stft = np.abs(librosa.stft(audio, n_fft=512, hop_length=hop_length))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=512)

    # 2. 各频段能量
    low_mask = freqs <= 500       # 低频 - 说话谐波
    mid_mask = (freqs > 500) & (freqs <= 2000)  # 中频 - 说话
    high_mask = (freqs > 2000) & (freqs <= 8000) # 高频 - 气流声

    low_energy = np.sum(stft[low_mask] ** 2, axis=0)
    mid_energy = np.sum(stft[mid_mask] ** 2, axis=0)
    high_energy = np.sum(stft[high_mask] ** 2, axis=0)
    total_energy = low_energy + mid_energy + high_energy + 1e-10

    # 3. 特征
    hf_ratio = high_energy / total_energy  # 高频占比
    lf_ratio = low_energy / total_energy   # 低频占比
    mf_ratio = mid_energy / total_energy   # 中频占比

    # 频谱质心
    spectral_centroid = np.sum(freqs.reshape(-1, 1) * stft, axis=0) / (np.sum(stft, axis=0) + 1e-10)

    # 4. VAD 掩码
    speech_mask = np.ones(total_frames, dtype=bool)
    if vad_timeline:
        speech_mask[:] = True
        for seg in vad_timeline:
            s = int(seg["start"] / 0.010)
            e = int(min(seg["end"] / 0.010, total_frames - 1))
            speech_mask[s:e] = False

    # 5. 检测
    energy_norm = total_energy / (total_energy.max() + 1e-10)
    noise_floor = np.percentile(energy_norm, 20)

    # 对齐数组长度
    n_frames = min(len(hf_ratio), total_frames, len(spectral_centroid), len(energy_norm))
    hf_ratio = hf_ratio[:n_frames]
    lf_ratio = lf_ratio[:n_frames]
    mf_ratio = mf_ratio[:n_frames]
    spectral_centroid = spectral_centroid[:n_frames]
    energy_norm = energy_norm[:n_frames]

    score = np.zeros(n_frames)
    for i in range(n_frames):
        if not speech_mask[i]:
            continue
        if energy_norm[i] < noise_floor * 1.5:
            continue
        # 叹气：高频多、中频少（不像说话）、低频少、质心高
        s = (
            hf_ratio[i] * 0.35 +
            (1 - min(mf_ratio[i] * 2, 1)) * 0.25 +
            np.clip((spectral_centroid[i] - 2000) / 6000, 0, 1) * 0.25 +
            np.clip(energy_norm[i] - noise_floor, 0, 1) * 0.15
        )
        score[i] = s

    threshold = max(np.percentile(score, 90), 0.2)

    # 6. 合并
    events = []
    in_ev = False
    ev_start = 0
    for i in range(n_frames):
        time_s = i * 0.010
        if score[i] > threshold and not in_ev:
            in_ev = True
            ev_start = time_s
        elif score[i] <= threshold and in_ev:
            in_ev = False
            seg_dur = time_s - ev_start
            if 0.3 <= seg_dur <= 3.0:
                idx_s = max(0, int(ev_start / 0.010))
                idx_e = min(n_frames, i)
                avg_score = float(score[idx_s:idx_e].mean()) if idx_e > idx_s else 0
                ev_type = "sigh" if avg_score > 0.35 and seg_dur < 1.2 else "breath"
                events.append({
                    "start": round(ev_start, 2),
                    "end": round(time_s, 2),
                    "type": ev_type,
                    "type_cn": "叹气" if ev_type == "sigh" else "深呼吸",
                    "confidence": round(min(avg_score, 1.0), 2),
                })

    if events:
        logger.info(f"呼吸/叹气检测: {len(events)} 个事件")

    return events
