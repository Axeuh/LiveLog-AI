# LiveLog-AI 数据格式

> [English](DATA_FORMAT.en.md) | **中文**

系统将所有数据以 JSON 格式存储在 `ai/data/{YYYY-MM-DD}/` 目录中，按日期组织。

---

## 目录

- [1. 感知数据 (perception.jsonl)](#1-感知数据-perceptionjsonl)
- [2. 每日概览 (profile.json)](#2-每日概览-profilejson)
- [3. 健康数据 (health.json)](#3-健康数据-healthjson)
- [4. 健康上传 API](#4-健康上传-api)
- [5. 数据类型汇总](#5-数据类型汇总)

---

## 1. 感知数据 (perception.jsonl)

**路径**: `ai/data/{YYYY-MM-DD}/perception.jsonl`  
**格式**: 每行一个 JSON 对象（`\n` 分隔，增量追加）

### 公共字段

所有事件条目都有以下字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `type` | string | 事件类型 |
| `t` | string | 时间 `HH:mm:ss`（北京时间） |
| `t_iso` | string | ISO 时间戳（部分事件） |

### 1.1 voice -- 语音事件

由语音对话触发。包含 ASR 识别结果、声纹、情绪、场景分析。

```json
{
  "type": "voice",
  "t": "14:30:25",
  "hasSpeech": true,
  "asr_text": "今天天气怎么样",
  "audio": "2026-06-25/audio/143025_default.wav",
  "scene": "家里",
  "segments": [
    {
      "start": 0.0, "end": 2.5,
      "text": "今天天气怎么样",
      "avg_db": -28.5, "peak_db": -12.0,
      "speech_prob": 0.98,
      "emotion_tag": "neutral", "emotion_prob": 0.85,
      "voiceprint_speaker": "Axeuh",
      "voiceprint_sim": 0.9234
    }
  ],
  "audio_events": [{ "label_cn": "人声", "label": "speech" }],
  "speaker": { "name": "Axeuh", "similarity": 0.9234 },
  "emotion": { "tag": "neutral", "probability": 0.85 }
}
```

### 1.2 app -- 前台应用切换

```json
{ "type": "app", "payload": { "app": "Chrome" } }
```

### 1.3 media -- 媒体播放状态

```json
{
  "type": "media",
  "payload": {
    "media_app": "Spotify",
    "media_title": "歌曲名",
    "media_artist": "歌手名",
    "media_duration": 240000,
    "media_state": "playing"
  }
}
```

`media_state` 取值: `playing` / `paused` / `buffering` / `stopped` / `skipping`

### 1.4 sensor -- 传感器快照

```json
{
  "type": "sensor",
  "payload": {
    "gps": "39.9042,116.4074",
    "phone_battery": 85
  }
}
```

### 1.5 screen -- 屏幕锁定/解锁

```json
{ "type": "screen", "payload": { "locked": true } }
```

### 1.6 device_env -- 设备环境

WiFi 状态：

```json
{ "type": "device_env", "payload": { "wifi": { "ssid": "MyWiFi", "rssi": -65, "linkSpeed": 866, "connected": true } } }
```

蓝牙设备列表：

```json
{ "type": "device_env", "payload": { "bluetooth": [{ "name": "Hand Ring", "address": "AA:BB:CC:DD:EE:FF", "profile": 1 }] } }
```

网络类型：

```json
{ "type": "device_env", "payload": { "network": { "type": "wifi", "mobileData": false } } }
```

屏幕锁屏状态：

```json
{ "type": "device_env", "payload": { "screen": { "locked": false } } }
```

### 1.7 notify -- 通知事件

```json
{ "type": "notify", "payload": { "app": "微信", "count": 3 }, "t": "14:30:25" }
```

### 1.8 web_message -- Web/AI 消息

```json
{
  "type": "web_message",
  "t": "14:30:25",
  "content": "[任务触发] 健康检查报告生成",
  "source": "task_trigger",
  "user_qq": "123456789"
}
```

### 1.9 PC 事件 (pc_window / pc_idle / pc_screen)

由 Windows Agent 上报，均有 `_source: "pc_sensor"` 和 `_agent_id` 字段。

**前台窗口**：

```json
{
  "type": "pc_window",
  "t": "14:30:25", "t_iso": "2026-06-25T14:30:25",
  "payload": { "process": "chrome.exe", "title": "GitHub", "pid": 12345 },
  "_source": "pc_sensor", "_agent_id": "desktop-pc-01"
}
```

**用户空闲**：

```json
{ "type": "pc_idle", "payload": { "state": "idle", "idle_seconds": 345 } }
{ "type": "pc_idle", "payload": { "state": "active", "idle_seconds": 0 } }
```

**屏幕锁定**：

```json
{ "type": "pc_screen", "payload": { "state": "lock" } }
```

---

## 2. 每日概览 (profile.json)

**路径**: `ai/data/{YYYY-MM-DD}/profile.json`  
**格式**: 单 JSON 对象，每天覆盖写入。

```json
{
  "date": "2026-06-25",
  "steps": 8542,
  "sleep_hours": 7.5,
  "app_usage_min": 180
}
```

其他字段由调用方按需写入，无固定 schema。

---

## 3. 健康数据 (health.json)

**路径**: `ai/data/{YYYY-MM-DD}/health.json`  
**格式**: 单 JSON 对象，每天一条。

```json
{
  "date": "2026-06-25",
  "updated_at": "2026-06-25T14:30:25+08:00",
  "samples": [
    {
      "t": 1719300000,
      "t_iso": "2026-06-25 14:20:00",
      "hr": 72,
      "steps": 1245,
      "stress": 25,
      "spo2": 98,
      "battery": 85
    }
  ],
  "daily_summary": {
    "steps": 8542,
    "hr_resting": 62,
    "hr_avg": 78,
    "hr_max": 145,
    "hr_min": 58,
    "stress_avg": 28,
    "spo2_avg": 97,
    "calories": 1850,
    "training_load": 120
  },
  "sleep_data": {
    "duration_min": 450,
    "deep_min": 120,
    "light_min": 210,
    "rem_min": 90,
    "awake_min": 30,
    "wakeup_time": 1719264000,
    "stages": [
      { "t": "23:00", "stage": "deep" },
      { "t": "00:30", "stage": "light" },
      { "t": "02:00", "stage": "rem" },
      { "t": "06:30", "stage": "light" }
    ]
  }
}
```

### samples 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `t` | int | Unix 时间戳（秒，必填） |
| `t_iso` | string | 可读时间（自动添加） |
| `hr` | int | 心率 0-250 |
| `steps` | int | 步数（累积值） |
| `stress` | int | 压力 0-255 |
| `spo2` | int | 血氧 0-100 |
| `battery` | int | 电量 0-100 |

### daily_summary 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `steps` | int | 总步数 |
| `hr_resting` | int | 静息心率（当日最低） |
| `hr_avg` | int | 平均心率 |
| `hr_max` / `hr_min` | int | 最高/最小心率 |
| `stress_avg` | int | 平均压力 |
| `spo2_avg` | int | 平均血氧 |
| `calories` | int | 卡路里 |
| `training_load` | int | 训练负荷 |

### sleep_data 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `duration_min` | int | 总睡眠分钟数 |
| `deep_min` / `light_min` / `rem_min` / `awake_min` | int | 各阶段分钟 |
| `wakeup_time` | int | 起床 Unix 时间戳 |
| `stages` | array | 阶段时间线 `{t: "HH:mm", stage: "deep"}` |

`stage` 取值: `"deep"` / `"light"` / `"rem"` / `"awake"`（也兼容旧版数字 1-5）

---

## 4. 健康上传 API

### POST /api/health/sync

请求体：

```json
{
  "samples": [
    { "t": 1719300000, "hr": 72, "steps": 1245, "stress": 25, "spo2": 98 }
  ],
  "daily_summary": { "steps": 8542, "hr_resting": 62 },
  "battery_levels": [ { "t": 1719300000, "level": 85 } ],
  "sleep_data": { "duration_min": 450, "stages": [...] },
  "client_time": "2026-06-25T14:30:25+08:00"
}
```

响应：

```json
{ "status": "ok", "dates": ["2026-06-25"], "stats": { "samples": 12, "dates_updated": ["2026-06-25"] } }
```

### POST /api/health/upload-db

上传 Gadgetbridge SQLite 数据库文件（multipart/form-data），后端解析 `XIAOMI_ACTIVITY_SAMPLE` 和 `XIAOMI_SLEEP_TIME_SAMPLE` 表，重新生成所有日期的 health.json。

### GET /api/health/query?date=YYYY-MM-DD

返回指定日期的 health.json 完整内容。

### GET /api/health/dates

```json
["2026-06-25", "2026-06-24", "2026-06-23"]
```

---

## 5. 数据类型汇总

```mermaid
graph TD
    subgraph "Android 采集"
        A1[DataCollectorService] -->|screen/sensor| P[perception.jsonl]
        A2[SystemStateCollector] -->|app/media/device_env| P
        A3[NotificationCollector] -->|notify| P
        A4[HealthDataCollector] -->|POST /health/sync| H[health.json]
    end

    subgraph "Windows Agent"
        W1[WindowTracker] -->|pc_window| P
        W2[IdleTracker] -->|pc_idle/pc_screen| P
    end

    subgraph "后端"
        B1[voice-session API] -->|voice| P
        B2[session.py] -->|web_message| P
    end

    subgraph "存储"
        P --> D[ai/data/{date}/perception.jsonl]
        H --> D
    end
```

所有数据均在 `ai/data/{YYYY-MM-DD}/` 目录下按日期组织。AI 分析系统以此为基础进行数据检查和报告生成。
