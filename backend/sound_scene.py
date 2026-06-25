"""
PANNs 环境声/音频事件分类模块
基于 AudioSet 527 类预训练模型 (Cnn14_16k)
负责：环境声分类 ESC、补充音频事件检测 AED
"""
import os
import csv
import logging
import urllib.request
import hashlib
from typing import List, Dict, Any, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import librosa

logger = logging.getLogger(__name__)

# ============================================================
# AudioSet 527 类标签
# ============================================================
def _load_audioset_labels(labels_path: Optional[str] = None) -> List[str]:
    """加载 AudioSet 527 类标签列表"""
    if labels_path is None:
        labels_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "models", "class_labels_indices.csv"
        )
    labels = []
    if os.path.exists(labels_path):
        with open(labels_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader, None)  # 跳过 header
            for row in reader:
                if len(row) >= 3:
                    labels.append(row[2])
    return labels


# ============================================================
# AudioSet 场景 / 事件 分组（用于展示）
# ============================================================
# 将 527 类划分成便于展示的场景组
SCENE_GROUPS = {
    "office": ["Office", "Typing", "Computer keyboard", "Computer", "Printer",
               "Telephone", "Telephone ringing", "Fax", "Photocopier",
               "Mouse", "Clicking", "Keys jangling", "Writing", "Drawer open or close",
               "Door", "Door slam", "Mail", "Sewing machine"],
    "home": ["Inside, small room", "Room", "Home", "Kitchen", "Bathroom",
             "Bedroom", "Living room", "Dining room", "Closet",
             "Cupboard open or close", "Dishes, pots, and pans",
             "Refrigerator", "Microwave oven", "Blender", "Food processor",
             "Coffee maker", "Toaster", "Hair dryer", "Electric shaver",
             "Vacuum cleaner", "Washing machine", "Dryer", "Dishwasher",
             "Water tap", "Faucet", "Sink", "Shower", "Tap",
             "Toilet flush", "Zipper", "Sawing"],
    "cafe_restaurant": ["Restaurant", "Cafe, restaurant", "Bar", "Pub",
                        "Food", "Chewing", "Eating", "Cutlery",
                        "Spoon", "Fork", "Glass", "Drink", "Chink, clink",
                        "Speech", "Conversation", "Chatter", "Mumbling",
                        "Music", "Background music", "Belly laugh", "Laughter"],
    "outdoors_nature": ["Outside, rural or natural", "Outside, urban or manmade",
                        "Nature", "Forest", "Field", "Farm", "Park",
                        "Bird", "Bird vocalization, bird call, bird song",
                        "Pigeon, dove", "Crow", "Owl", "Rain",
                        "Raindrop", "Thunder", "Thunderstorm",
                        "Wind", "Wind noise", "Wind howl",
                        "Water", "Stream", "River", "Ocean",
                        "Sea waves", "Waterfall", "Gurgling",
                        "Creek", "Insects", "Cricket", "Mosquito",
                        "Frog", "Insect", "Fly", "Buzz", "Bee",
                        "Animal", "Dog", "Cat", "Meow", "Bark",
                        "Horse", "Cow", "Sheep", "Pig", "Rooster",
                        "Crickets", "Chirp", "Cicada"],
    "urban": ["Traffic noise, roadway noise", "Roadway", "Vehicle",
              "Car", "Truck", "Bus", "Motor vehicle", "Motorcycle",
              "Bicycle", "Skateboard", "Scooter", "Train",
              "Rail transport", "Railroad", "Train horn",
              "Subway, metro, underground", "Tram",
              "Aircraft", "Airplane", "Helicopter",
              "Engine", "Engine starting", "Engine idling",
              "Car passing by", "Tire squeal", "Brake squeak",
              "Siren", "Police car", "Ambulance", "Fire engine",
              "Alarm", "Alarm clock", "Smoke detector", "Fire alarm",
              "Car alarm", "Burglar alarm", "Horn", "Vehicle horn",
              "Car horn", "Honk", "Street music", "Busy signal",
              "Construction", "Hammer", "Jackhammer", "Saw",
              "Drill", "Explosion", "Gunshot"],
    "entertainment": ["Music", "Musical instrument", "Guitar", "Piano",
                      "Drum", "Bass guitar", "Violin", "Cello",
                      "Flute", "Trumpet", "Saxophone", "Singing",
                      "Choir", "Rapping", "Beatboxing",
                      "Television", "Radio", "Game", "Video game",
                      "Cinema", "Movie", "Concert", "Live concert",
                      "Stadium", "Sports", "Basketball", "Soccer",
                      "Tennis", "Baseball", "Swimming",
                      "Applause", "Cheering", "Whistle", "Clapping"],
    "quiet": ["Silence", "Inside, small room", "Ocean", "Water",
              "Wind", "Rain", "Stream", "River",
              "Sleep", "Snoring", "Breathing", "Heart sounds",
              "Heartbeat"],
}

# 常用 AudioSet 事件名 → 中文翻译
SCENE_CN = {
    "Office": "办公室", "Inside, small room": "室内小房间", "Room": "房间",
    "Home": "家", "Kitchen": "厨房", "Bathroom": "浴室",
    "Bedroom": "卧室", "Living room": "客厅", "Dining room": "餐厅",
    "Cafe, restaurant": "咖啡厅/餐厅", "Restaurant": "餐厅", "Bar": "酒吧",
    "Outside, rural or natural": "户外自然", "Outside, urban or manmade": "户外城市",
    "Forest": "森林", "Nature": "自然", "Park": "公园",
    "Traffic noise, roadway noise": "交通噪音", "Vehicle": "车辆",
    "Car": "汽车", "Bus": "公交车", "Train": "火车",
    "Subway, metro, underground": "地铁",
    "Silence": "安静", "Music": "音乐", "Speech": "说话声",
    "Conversation": "对话", "Laughter": "笑声",
    "Applause": "掌声", "Singing": "唱歌",
    "Rain": "下雨", "Wind": "刮风", "Thunder": "打雷",
    "Bird": "鸟叫", "Dog": "狗叫", "Cat": "猫叫",
    "Alarm": "警报", "Siren": "警笛",
    "Telephone ringing": "电话铃声", "Door": "门声",
    "Footsteps": "脚步声", "Keyboard": "键盘声",
}


# ============================================================
# PANNs 模型定义（裁剪版，只需推理）
# ============================================================
def init_layer(layer):
    nn.init.xavier_uniform_(layer.weight)
    if hasattr(layer, "bias") and layer.bias is not None:
        layer.bias.data.fill_(0.)


def init_bn(bn):
    bn.bias.data.fill_(0.)
    bn.weight.data.fill_(1.)


class ConvBlock(nn.Module):
    def __init__(self, in_channels: int, out_channels: int):
        super().__init__()
        self.conv1 = nn.Conv2d(in_channels, out_channels, (3, 3), stride=(1, 1),
                               padding=(1, 1), bias=False)
        self.conv2 = nn.Conv2d(out_channels, out_channels, (3, 3), stride=(1, 1),
                               padding=(1, 1), bias=False)
        self.bn1 = nn.BatchNorm2d(out_channels)
        self.bn2 = nn.BatchNorm2d(out_channels)
        self.init_weight()

    def init_weight(self):
        init_layer(self.conv1)
        init_layer(self.conv2)
        init_bn(self.bn1)
        init_bn(self.bn2)

    def forward(self, x, pool_size=(2, 2), pool_type="avg"):
        x = F.relu_(self.bn1(self.conv1(x)))
        x = F.relu_(self.bn2(self.conv2(x)))
        if pool_type == "max":
            x = F.max_pool2d(x, kernel_size=pool_size)
        elif pool_type == "avg":
            x = F.avg_pool2d(x, kernel_size=pool_size)
        elif pool_type == "avg+max":
            x = F.avg_pool2d(x, kernel_size=pool_size) + F.max_pool2d(x, kernel_size=pool_size)
        else:
            raise ValueError(f"Unknown pool_type: {pool_type}")
        return x


class Cnn14_16k(nn.Module):
    """PANNs CNN14 for 16kHz audio (Cnn14_16k)."""
    def __init__(self, classes_num: int = 527):
        super().__init__()
        self.bn0 = nn.BatchNorm2d(64)

        self.conv_block1 = ConvBlock(1, 64)
        self.conv_block2 = ConvBlock(64, 128)
        self.conv_block3 = ConvBlock(128, 256)
        self.conv_block4 = ConvBlock(256, 512)
        self.conv_block5 = ConvBlock(512, 1024)
        self.conv_block6 = ConvBlock(1024, 2048)

        self.fc1 = nn.Linear(2048, 2048, bias=True)
        self.fc_audioset = nn.Linear(2048, classes_num, bias=True)

        self.init_weight()

    def init_weight(self):
        init_bn(self.bn0)
        init_layer(self.fc1)
        init_layer(self.fc_audioset)

    def forward(self, x):
        """
        x: (batch, 1, T, mel) - log mel spectrogram (T=time frames, mel=64)
        """
        x = x.transpose(1, 3)      # (batch, mel, T, 1)
        x = self.bn0(x)            # bn over mel bands
        x = x.transpose(1, 3)      # (batch, 1, T, mel)

        x = self.conv_block1(x, pool_size=(2, 2), pool_type="avg")
        x = F.dropout(x, p=0.2, training=False)
        x = self.conv_block2(x, pool_size=(2, 2), pool_type="avg")
        x = F.dropout(x, p=0.2, training=False)
        x = self.conv_block3(x, pool_size=(2, 2), pool_type="avg")
        x = F.dropout(x, p=0.2, training=False)
        x = self.conv_block4(x, pool_size=(2, 2), pool_type="avg")
        x = F.dropout(x, p=0.2, training=False)
        x = self.conv_block5(x, pool_size=(2, 2), pool_type="avg")
        x = F.dropout(x, p=0.2, training=False)
        x = self.conv_block6(x, pool_size=(1, 1), pool_type="avg")
        x = F.dropout(x, p=0.2, training=False)
        x = torch.mean(x, dim=3)    # (batch, 2048, H')

        (x1, _) = torch.max(x, dim=2)  # (batch, 2048)
        x2 = torch.mean(x, dim=2)      # (batch, 2048)
        x = x1 + x2
        x = F.dropout(x, p=0.5, training=False)
        x = F.relu_(self.fc1(x))
        x = F.dropout(x, p=0.5, training=False)
        clipwise_output = torch.sigmoid(self.fc_audioset(x))
        return clipwise_output  # (batch, 527)


# ============================================================
# Mel 频谱计算
# ============================================================
def compute_logmel(audio: np.ndarray, sr: int = 16000) -> np.ndarray:
    """
    计算 log mel 频谱 (PANNs Cnn14_16k 格式)
    使用 power_to_db 匹配 torchlibrosa 的输出
    返回: (1, 1, T, 64) 形状的 numpy 数组
    """
    window_size = 512
    hop_size = 160
    mel_bins = 64
    fmin = 50
    fmax = 8000

    # STFT -> 功率谱
    S = librosa.stft(
        audio.astype(np.float64),
        n_fft=window_size,
        hop_length=hop_size,
        win_length=window_size,
        window="hann",
        center=True,
        pad_mode="reflect",
    )
    power = np.abs(S) ** 2  # (freq, time)

    # Mel filter
    mel_filter = librosa.filters.mel(
        sr=sr,
        n_fft=window_size,
        n_mels=mel_bins,
        fmin=fmin,
        fmax=fmax,
    )  # (mel_bins, freq)
    mel_spec = mel_filter @ power  # (mel_bins, time)

    # power_to_db (匹配 torchlibrosa LogmelFilterBank: ref=1.0, amin=1e-10, top_db=None)
    # 公式: 10 * log10(maximum(mel_spec, 1e-10))
    log_mel = librosa.power_to_db(mel_spec, ref=1.0, amin=1e-10, top_db=None)
    # log_mel: (64, T) - (mel_bins, time)

    # 添加 batch 和 channel 维度，并转成 (N, C, T, mel)
    log_mel = log_mel.T[np.newaxis, np.newaxis, :, :]  # (1, 1, T, 64)
    return log_mel.astype(np.float32)


# ============================================================
# 场景理解分类器
# ============================================================
CHECKPOINT_URL = "https://zenodo.org/api/records/3987831/files/Cnn14_16k_mAP%3D0.438.pth/content"
CHECKPOINT_MD5 = "362fc5ff18f1d6ad2f6d464b45893f2c"
CHECKPOINT_FILENAME = "Cnn14_16k_mAP=0.438.pth"


def _get_checkpoint_dir() -> str:
    """获取模型缓存目录"""
    return os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "models",
    )


def _download_checkpoint() -> str:
    """下载 PANNs 检查点（首次使用）"""
    save_dir = _get_checkpoint_dir()
    save_path = os.path.join(save_dir, CHECKPOINT_FILENAME)

    if os.path.exists(save_path):
        file_size = os.path.getsize(save_path)
        if file_size > 300_000_000:  # ~350MB
            logger.info(f"PANNs 检查点已存在: {save_path} ({file_size // 1024 // 1024}MB)")
            return save_path
        else:
            logger.warning(f"检查点文件不完整 ({file_size} bytes)，重新下载")

    logger.info(f"正在下载 PANNs 检查点 ({CHECKPOINT_FILENAME}) ~358MB...")
    logger.info(f"下载链接: {CHECKPOINT_URL}")

    # 下载
    req = urllib.request.Request(CHECKPOINT_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=600) as response:
        total_size = int(response.headers.get("Content-Length", 0))
        downloaded = 0
        chunk_size = 8192

        with open(save_path + ".tmp", "wb") as f:
            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if total_size > 0 and downloaded % (chunk_size * 128) == 0:
                    pct = downloaded / total_size * 100
                    logger.info(f"  下载进度: {pct:.0f}% ({downloaded // 1024 // 1024}MB / {total_size // 1024 // 1024}MB)")

    # 验证 MD5
    logger.info("验证文件完整性...")
    md5_hash = hashlib.md5()
    with open(save_path + ".tmp", "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            md5_hash.update(chunk)
    actual_md5 = md5_hash.hexdigest()

    if actual_md5 == CHECKPOINT_MD5:
        os.rename(save_path + ".tmp", save_path)
        logger.info(f"PANNs 检查点下载完成: {save_path}")
    else:
        os.remove(save_path + ".tmp")
        raise RuntimeError(
            f"检查点 MD5 不匹配: 期望 {CHECKPOINT_MD5}, 实际 {actual_md5}"
        )

    return save_path


class SceneAnalyzer:
    """
    场景/环境声分析器
    使用 PANNs Cnn14_16k 模型进行多标签音频分类
    """

    def __init__(self, device: str = "cuda:0", checkpoint_path: Optional[str] = None):
        self.device = device if torch.cuda.is_available() else "cpu"
        if device.startswith("cuda") and not torch.cuda.is_available():
            logger.warning(f"CUDA 不可用，回退到 CPU")
            self.device = "cpu"

        self._model = None
        self._labels = _load_audioset_labels()
        self._checkpoint_path = checkpoint_path

    def _load_model(self):
        """延迟加载模型和检查点"""
        if self._model is not None:
            return

        logger.info("加载 PANNs Cnn14_16k 模型...")
        model = Cnn14_16k(classes_num=len(self._labels))

        checkpoint_path = self._checkpoint_path or _download_checkpoint()
        logger.info(f"加载检查点: {checkpoint_path}")

        raw_state = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
        if "model" in raw_state:
            state_dict = raw_state["model"]
        else:
            state_dict = raw_state

        # 移除 spectrogram/logmel 模块的权重（训练时包含它们，但我们用手工计算的 mel）
        keys_to_remove = [k for k in state_dict.keys()
                          if k.startswith(("spectrogram_extractor.", "logmel_extractor.", "spec_augmenter."))]
        for k in keys_to_remove:
            del state_dict[k]

        model.load_state_dict(state_dict, strict=False)
        model.eval()
        model.to(self.device)

        self._model = model
        logger.info("PANNs 模型加载完成！")

    def classify_scene(self, audio_path: str, top_k: int = 5) -> Dict[str, Any]:
        """
        对整个音频进行场景/环境分类
        返回 top-K 标签及其概率
        """
        self._load_model()

        # 加载音频 (16kHz)
        audio, sr = librosa.load(audio_path, sr=16000, mono=True)

        # 处理长音频：分10秒窗口，取平均概率
        clip_duration = 10.0  # 秒
        clip_samples = int(clip_duration * sr)
        hop_samples = clip_samples // 2  # 50% 重叠

        all_probs = []
        for start in range(0, max(len(audio), 1), hop_samples):
            clip = audio[start:start + clip_samples]
            if len(clip) < sr:  # 最后一段不足1秒则跳过
                break
            # 补齐到 clip_samples
            if len(clip) < clip_samples:
                clip = np.pad(clip, (0, clip_samples - len(clip)))

            logmel = compute_logmel(clip, sr=16000)
            logmel_tensor = torch.from_numpy(logmel).to(self.device)

            with torch.no_grad():
                probs = self._model(logmel_tensor)  # (1, 527)
            all_probs.append(probs.cpu().numpy())

        if not all_probs:
            return {"scene_tags": [], "scene_groups": {}, "scene_primary": None,
                    "error": "音频过短（< 1秒）"}

        avg_probs = np.mean(all_probs, axis=0).flatten()  # (527,)

        # 获取 top-K
        top_indices = np.argsort(avg_probs)[::-1][:top_k]
        scene_tags = []
        for idx in top_indices:
            prob = float(avg_probs[idx])
            label = self._labels[idx] if idx < len(self._labels) else f"class_{idx}"
            scene_tags.append({
                "class_index": int(idx),
                "label": label,
                "label_cn": SCENE_CN.get(label, label),
                "probability": round(prob, 4),
                "probability_pct": f"{int(prob * 100)}%",
            })

        # 分组统计
        scene_groups = {}
        for group_name, group_labels in SCENE_GROUPS.items():
            group_score = 0.0
            matched = []
            for label in group_labels:
                if label in self._labels:
                    idx = self._labels.index(label)
                    score = float(avg_probs[idx])
                    if score > 0.05:  # 只计入 > 5% 的
                        group_score += score
                        matched.append({
                            "label": label,
                            "label_cn": SCENE_CN.get(label, label),
                            "probability": round(score, 4),
                        })
            if matched:
                scene_groups[group_name] = {
                    "group_name_cn": {
                        "office": "办公室", "home": "家居", "cafe_restaurant": "餐饮",
                        "outdoors_nature": "户外自然", "urban": "城市街道",
                        "entertainment": "娱乐", "quiet": "安静",
                    }.get(group_name, group_name),
                    "total_score": min(round(group_score, 4), 1.0),
                    "matches": matched,
                }

        # 按 total_score 排序
        scene_groups = dict(
            sorted(scene_groups.items(), key=lambda x: x[1]["total_score"], reverse=True)
        )

        return {
            "scene_tags": scene_tags,
            "scene_groups": scene_groups,
            "scene_primary": scene_tags[0] if scene_tags else None,
        }

    def classify_segments(self, audio_path: str, segment_duration: float = 2.0,
                          top_k: int = 3) -> List[Dict[str, Any]]:
        """
        对音频分段进行事件检测
        每 segment_duration 秒输出一段的 top-K 事件
        """
        self._load_model()

        audio, sr = librosa.load(audio_path, sr=16000, mono=True)
        segment_samples = int(segment_duration * sr)
        hop_samples = segment_samples // 2  # 50% 重叠

        segments = []
        total_segments = (len(audio) - segment_samples) // hop_samples + 1 if len(audio) >= segment_samples else 1

        for seg_idx in range(total_segments):
            start_sample = seg_idx * hop_samples
            clip = audio[start_sample:start_sample + segment_samples]
            if len(clip) < segment_samples:
                clip = np.pad(clip, (0, segment_samples - len(clip)))

            time_sec = start_sample / sr
            time_str = f"{int(time_sec // 60):02d}:{int(time_sec % 60):02d}"

            logmel = compute_logmel(clip, sr=16000)
            logmel_tensor = torch.from_numpy(logmel).to(self.device)

            with torch.no_grad():
                probs = self._model(logmel_tensor)

            probs_np = probs.cpu().numpy().flatten()
            top_indices = np.argsort(probs_np)[::-1][:top_k]

            events = []
            for idx in top_indices:
                prob = float(probs_np[idx])
                if prob < 0.1:  # 阈值过滤
                    continue
                label = self._labels[idx] if idx < len(self._labels) else f"class_{idx}"
                events.append({
                    "class_index": int(idx),
                    "label": label,
                    "label_cn": SCENE_CN.get(label, label),
                    "probability": round(prob, 4),
                    "probability_pct": f"{int(prob * 100)}%",
                })

            if events:
                segments.append({
                    "time": round(time_sec, 1),
                    "time_str": time_str,
                    "duration": segment_duration,
                    "events": events,
                })

        return segments

    def classify_scene_timeline(
        self, audio_path: str, time_segments: List[Dict[str, float]], top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """
        按指定时间段对音频进行分类，返回每个时间段的场景标签。

        Args:
            audio_path: 16kHz WAV 路径
            time_segments: [{"start": float, "end": float}, ...]
            top_k: 每段返回 top-K 标签

        Returns:
            [{"start": float, "end": float, "primary": dict, "tags": [...], "groups": {...}}, ...]
        """
        self._load_model()
        audio, sr = librosa.load(audio_path, sr=16000, mono=True)
        total_samples = len(audio)

        results = []
        for seg in time_segments:
            start_s = seg["start"]
            end_s = seg.get("end", start_s + 3.0)
            if end_s - start_s < 0.5:
                end_s = start_s + 0.5  # 最少 0.5 秒

            start_sample = int(start_s * sr)
            end_sample = min(int(end_s * sr), total_samples)
            clip = audio[start_sample:end_sample]

            if len(clip) < sr // 2:  # 不足 0.5 秒
                continue

            # PANNs 需要固定长度（取整段），不足则 pad
            clip_duration = max(len(clip) / sr, 1.0)
            n_samples = int(clip_duration * sr)
            if len(clip) < n_samples:
                clip = np.pad(clip, (0, n_samples - len(clip)))
            else:
                clip = clip[:n_samples]

            logmel = compute_logmel(clip, sr=16000)
            logmel_tensor = torch.from_numpy(logmel).to(self.device)

            with torch.no_grad():
                probs = self._model(logmel_tensor)  # (1, 527)

            probs_np = probs.cpu().numpy().flatten()

            # top-K
            top_indices = np.argsort(probs_np)[::-1][:top_k]
            tags = []
            for idx in top_indices:
                prob = float(probs_np[idx])
                label = self._labels[idx] if idx < len(self._labels) else f"class_{idx}"
                tags.append({
                    "class_index": int(idx),
                    "label": label,
                    "label_cn": SCENE_CN.get(label, label),
                    "probability": round(prob, 4),
                    "probability_pct": f"{int(prob * 100)}%",
                })

            # 分组统计
            groups = {}
            for group_name, group_labels in SCENE_GROUPS.items():
                group_score = 0.0
                matched = []
                for label in group_labels:
                    if label in self._labels:
                        idx = self._labels.index(label)
                        score = float(probs_np[idx])
                        if score > 0.05:
                            group_score += score
                            matched.append({
                                "label": label,
                                "label_cn": SCENE_CN.get(label, label),
                                "probability": round(score, 4),
                            })
                if matched:
                    groups[group_name] = {
                        "group_name_cn": {
                            "office": "办公室", "home": "家居", "cafe_restaurant": "餐饮",
                            "outdoors_nature": "户外自然", "urban": "城市街道",
                            "entertainment": "娱乐", "quiet": "安静",
                        }.get(group_name, group_name),
                        "total_score": min(round(group_score, 4), 1.0),
                        "matches": matched,
                    }
            groups = dict(sorted(groups.items(), key=lambda x: x[1]["total_score"], reverse=True))

            results.append({
                "start": round(start_s, 1),
                "end": round(end_s, 1),
                "primary": tags[0] if tags else None,
                "tags": tags,
                "groups": groups,
            })

        return results
