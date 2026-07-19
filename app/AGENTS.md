# Axeuh健康监测 - Android App

**生成时间**: 2026-07-07（最后更新）
**框架**: Kotlin + Jetpack Compose + Gradle
**Android**: minSdk 26, targetSdk 36, compileSdk 36
**包名**: `com.axeuh.health.monitor`
**架构**: 分层模块化（网络层 → 状态层 → 采集层 → UI层）

## 概述

Axeuh 助手的 Android 端数据采集 + 远程管理 App。提供 SettingsActivity 配置面板、DataCollectorService 后台数据采集调度、MobileActivity WebView 远程管理、OTA 自更新等功能。

2026-06-23 重构：从单块架构（2956行DataCollectorService + 1925行SettingsActivity）重构为分层模块化架构（5个采集器 + 3个上传器 + ViewModel模式 + 6个独立Composable）。

## 启动流程

```
开机 → BootReceiver
  → 用户打开 App → MainActivity
     → 检查 token → 没有 → SettingsActivity（登录页）
     → 检查服务器 /health（AppHttpClient）
        → 在线 → MobileActivity（WebView 手机管理页）
        → 离线 → SettingsActivity
     → finish() 自身

SettingsActivity 内：
  → 账号密码登录 → token 保存到 SharedPreferences
  → 开启"感知数据上传" → 前台启动 DataCollectorService
  → 后续每次打开 App → 自动跳转 MobileActivity
```

## 目录结构

```
app/
├── src/main/
│   ├── java/com/axeuh/health/monitor/
│   │   ├── MainActivity.kt              # 启动入口：token→/health→跳转（~120行）
│   │   ├── SettingsActivity.kt           # 设置页 Activity（~435行，已精简）
│   │   ├── MobileActivity.kt             # WebView 手机管理页面
│   │   ├── network/                      # 统一网络层
    │   │   │   └── AppHttpClient.kt          # OkHttp 封装：get/post/postMultipart/download
    │   │   ├── config/                     # 服务器配置管理
    │   │   │   └── ServerConfig.kt         # ServerConfig 单例，统一管理服务器 URL
│   │   ├── service/                      # 系统服务
│   │   │   ├── DataCollectorService.kt   # 采集调度器（~234行，已精简，委托给Collector）
│   │   │   ├── KeepAliveService.kt       # 前台保活
│   │   │   ├── AccessibilityService.kt   # 输入内容感知（无障碍服务）
│   │   │   ├── NotificationListenerService.kt  # 通知监听
│   │   │   ├── state/                    # 状态管理层
│   │   │   │   └── SensorStateHolder.kt  # 统一 StateFlow 状态持有（11个状态）
│   │   │   ├── collectors/               # 数据采集器
│   │   │   │   ├── BaseCollector.kt      # 抽象采集器基类
│   │   │   │   ├── SystemStateCollector.kt   # WiFi/蓝牙/屏幕/前台应用/媒体
│   │   │   │   ├── NotificationCollector.kt  # 通知轮询
│   │   │   │   ├── GpsCollector.kt           # GPS 定位（5min间隔）
│   │   │   │   ├── HealthDataCollector.kt    # 手环健康数据（5min间隔）
│   │   │   │   └── AudioCollector.kt         # 录音 + VAD（连续循环）
│   │   │   └── uploader/                 # 数据上传器
│   │   │       ├── EventUploader.kt      # 通用事件推送
│   │   │       ├── HealthBatchUploader.kt    # 健康数据批量同步
│   │   │       └── AudioUploader.kt      # 音频 multipart 上传
│   │   ├── ota/                          # OTA 自更新
│   │   │   ├── UpdateInfo.kt
│   │   │   ├── UpdateSource.kt           # 本地/远程更新源
│   │   │   ├── ApkDownloader.kt          # APK 下载器（通过 AppHttpClient）
│   │   │   └── ApkInstaller.kt           # 系统安装器（ACTION_VIEW + FileProvider）
│   │   ├── ui/
│   │   │   ├── VoiceprintPanel.kt        # 声纹注册面板
│   │   │   ├── LogEntry.kt / LogCache.kt # 日志基础设施
│   │   │   └── settings/                 # 设置页模块化组件
│   │   │       ├── SettingsViewModel.kt  # ViewModel（40+ StateFlow状态）
│   │   │       ├── LoginSection.kt       # 登录区 Composable
│   │   │       ├── SensorControls.kt     # 传感器控制 Composable（11个开关）
│   │   │       ├── AiSettingsSection.kt  # AI设置 Composable（模型选择 + 声纹）
│   │   │       ├── OtaSection.kt         # OTA更新 Composable
│   │   │       └── PermissionDialogs.kt  # 权限引导弹窗（5个对话框）
│   │   └── receiver/
│   │       ├── BootReceiver.kt           # 开机自启
│   │       └── AdbCommandReceiver.kt     # ADB 命令广播
│   ├── res/
│   └── AndroidManifest.xml
├── build/
├── docs/
│   └── band_data_collection_guide.md     # 手环数据采集指南
└── AGENTS.md                             # 本文件
```

## 架构设计

### 分层依赖

```
网络层 (AppHttpClient) ← 采集器/上传器 ← DataCollectorService(调度器)
状态层 (SensorStateHolder) ← 采集器 → 上传器 → 网络层
UI层 (SettingsViewModel) ← SensorStateHolder + AppHttpClient
```

### DataCollectorService — 采集调度器 (~234行)

以前台 Service 运行，不再直接采集数据，而是启动/停止各 Collector：

```
DataCollectorService
├── CollectorManager
│   ├── SystemStateCollector → 5s 循环：前台应用/媒体/WiFi/蓝牙/屏幕
│   ├── NotificationCollector → 5s 循环：通知计数
│   ├── GpsCollector → 5min 循环：GPS定位
│   ├── HealthDataCollector → 5min 循环：手环心率/步数/压力/血氧
│   └── AudioCollector → 连续循环：PCM→VAD→WAV→上传
├── 30s 主循环：触发Gadgetbridge同步 + 电池读取 + 传感器事件上传
└── 5s 快循环：刷新debugStateJson
```

| 传感器 | 采集器 | 实现方式 | 间隔 |
|--------|--------|---------|------|
| 音频 | AudioCollector | AudioRecord + VAD（VOICE_RECOGNITION 音源，不降级） | 连续 |
| 前台应用 | SystemStateCollector | UsageStatsManager | 5s |
| 媒体播放 | SystemStateCollector | MediaSessionManager | 5s |
| WiFi/网络 | SystemStateCollector | WifiManager + ConnectivityManager | 5s |
| 蓝牙 | SystemStateCollector | BluetoothManager | 5s |
| 屏幕状态 | SystemStateCollector | PowerManager | 5s |
| 通知 | NotificationCollector | NotificationListenerService | 5s |
| GPS | GpsCollector | LocationManager | 5min |
| 健康 | HealthDataCollector | Gadgetbridge DB (SQLite) | 5min |
| 输入内容 | AccessibilityService | 无障碍服务 | 5s |

### 数据流

```
采集器 → SensorStateHolder.updateXxx() → UI层 collectAsState()
采集器 → AppHttpClient.post() → 后端 API
AudioCollector → AudioUploader → OkHttp Multipart → /api/screen/stt/voice-session-multipart
HealthDataCollector → HealthBatchUploader → AppHttpClient.post() → /api/health/sync
```

## SettingsActivity — 设置页 (~435行)

使用 ViewModel + 6 个独立 Composable 模块：

| 模块 | 文件 | 功能 |
|------|------|------|
| **SettingsViewModel** | `ui/settings/SettingsViewModel.kt` | 40+ StateFlow状态管理 |
| **LoginSection** | `ui/settings/LoginSection.kt` | 服务器地址、登录/退出 |
| **SensorControls** | `ui/settings/SensorControls.kt` | 11个传感器开关+间隔+预览 |
| **AiSettingsSection** | `ui/settings/AiSettingsSection.kt` | 模型选择+声纹管理 |
| **OtaSection** | `ui/settings/OtaSection.kt` | OTA检查/下载/安装 |
| **PermissionDialogs** | `ui/settings/PermissionDialogs.kt` | 5个权限引导弹窗 |

每个传感器开关点开启时自动检查对应权限，未授权弹窗引导。

## 键模块说明

### AppHttpClient（网络层）
- OkHttp 封装，系统默认 SSL 验证（服务器使用 Let's Encrypt 公共 CA）
- Token 自动注入（从 SharedPreferences 读取）
- ServerConfig.BASE_URL 作为服务器 URL 唯一来源
- 密码存储使用 EncryptedSharedPreferences（AES256-GCM 加密）
- 方法：`get()` / `post()` / `postMultipart()` / `download()` (Flow)
- 超时：connect 15s / read 30s

### ServerConfig（配置管理）
- `object ServerConfig` 全局单例
- `init(context)` 从 SharedPreferences 读取已保存的服务器 URL
- `update(url)` 在设置页保存 URL 时同步更新
- 所有采集器/上传器通过 `ServerConfig.BASE_URL` 获取地址，无需各自读取 Prefs

### SensorStateHolder（状态层）
- 纯 Kotlin + Coroutines，无 Android 依赖
- 11 个 StateFlow 状态，每个有 update/snapshot/observe 方法
- 状态：vadStatus, currentDbLevel, debugStateJson, lastSensorText, lastResponseText, lastGps, lastMediaText, lastHeartRate, lastSteps, lastStress, lastSpo2, lastNotificationCount

### BaseCollector（采集器基类）
```kotlin
abstract class BaseCollector(
    protected val context: Context,
    protected val stateHolder: SensorStateHolder,
    protected val httpClient: AppHttpClient
) {
    abstract fun start()
    abstract fun stop()
    open val isEnabled: Boolean get() = false
}
```

### AudioCollector（音频采集关键细节）

| 项目 | 说明 |
|------|------|
| 音源策略 | 仅 `VOICE_RECOGNITION`（绕过蓝牙 MIC），不降级到 `CAMCORDER`/`MIC` |
| 启动验证 | 后台线程中连续读 10 帧（300ms），任一帧非零则通过；全零则释放 1s 后重试 |
| 全零兜底 | 录音完成后检测 WAV 体是否全零，跳过无意义上传 |
| VAD | 仅用于 UI 状态显示，不阻断录音或上传 |
| 重试策略 | 指数退避 1s→2s→4s→...→30s 封顶 |
| 缓存 | 上传失败时按原始 `recordingStartMs` 时间戳缓存到 `upload_cache/` |

**MIUI 注意事项**:
- `VOICE_RECOGNITION` 在 MIUI 上 `startRecording()` 可能成功但麦克风未实际激活（返回全零 PCM）
- 必须声明 `foregroundServiceType="microphone"` 并在 `startForeground()` 显式传入类型
- 第 1 帧数据可能全零——是硬件延迟而非未激活，要多帧判断
- MIUI 无"始终允许"麦克风权限选项，前台服务 + 正确类型声明是唯一的后台录音途径

## OTA 自更新

```
OtaSection → SettingsViewModel.checkUpdate()
  → /api/ota/check?current_version=N
  → 有新版本 → 显示版本号和 changelog
  → SettingsViewModel.downloadUpdate()
  → ApkDownloader 下载 → otaProgress 更新
  → ApkInstaller 安装（系统安装器 FileProvider）
  → 用户点击安装
```

认证：使用登录 Bearer Token（与 API 认证相同），通过 Authorization 头或查询参数 `?token=` 传入。

## 构建与安装

```bash
# 编译
gradlew assembleDebug

# 安装到设备
adb install -r app/build/outputs/apk/debug/app-debug.apk

# 激活无障碍服务
adb shell settings put secure enabled_accessibility_services \
  com.axeuh.health.monitor/.service.AxeuhAccessibilityService

# 激活通知监听
adb shell settings put secure enabled_notification_listeners \
  com.axeuh.health.monitor/.service.NotificationListenerService
```

## 调试命令

```bash
# 直接打开设置页
adb shell am start -n com.axeuh.health.monitor/.SettingsActivity

# 查看 DataCollectorService 日志
adb logcat -s DataCollector

# 查看采集服务运行状态
adb shell dumpsys activity services com.axeuh.assistant.dev | findstr DataCollectorService

# 检查蓝牙权限
adb shell dumpsys package com.axeuh.assistant.dev | findstr BLUETOOTH_CONNECT
```

## 相关文档

- `docs/band_data_collection_guide.md` - 手环数据采集指南
