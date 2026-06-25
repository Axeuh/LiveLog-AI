package com.axeuh.health.monitor.service.state

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * 统一传感器状态持有者。
 *
 * 管理 DataCollectorService 中所有传感器状态，使用 Kotlin StateFlow 提供可观察的数据流。
 * 设计为普通类（非单例），由 DataCollectorService 实例化。
 *
 * 纯 Kotlin + Coroutines，无 Android 依赖。
 */
class SensorStateHolder {

    // ── VAD 状态 ──
    private val _vadStatus = MutableStateFlow("idle")
    val vadStatus: StateFlow<String> = _vadStatus.asStateFlow()

    // ── 当前麦克风音量 dBFS ──
    private val _currentDbLevel = MutableStateFlow(-80f)
    val currentDbLevel: StateFlow<Float> = _currentDbLevel.asStateFlow()

    // ── 调试快照 JSON ──
    private val _debugStateJson = MutableStateFlow("{}")
    val debugStateJson: StateFlow<String> = _debugStateJson.asStateFlow()

    // ── 最近一次传感器文本 ──
    private val _lastSensorText = MutableStateFlow("")
    val lastSensorText: StateFlow<String> = _lastSensorText.asStateFlow()

    // ── 最近一次响应文本 ──
    private val _lastResponseText = MutableStateFlow("")
    val lastResponseText: StateFlow<String> = _lastResponseText.asStateFlow()

    // ── GPS 位置 ──
    private val _lastGps = MutableStateFlow("")
    val lastGps: StateFlow<String> = _lastGps.asStateFlow()

    // ── 媒体播放状态文本 ──
    private val _lastMediaText = MutableStateFlow("")
    val lastMediaText: StateFlow<String> = _lastMediaText.asStateFlow()

    // ── 心率 (bpm) ──
    private val _lastHeartRate = MutableStateFlow(-1)
    val lastHeartRate: StateFlow<Int> = _lastHeartRate.asStateFlow()

    // ── 步数 ──
    private val _lastSteps = MutableStateFlow(-1)
    val lastSteps: StateFlow<Int> = _lastSteps.asStateFlow()

    // ── 压力 ──
    private val _lastStress = MutableStateFlow(-1)
    val lastStress: StateFlow<Int> = _lastStress.asStateFlow()

    // ── 血氧饱和度 (%) ──
    private val _lastSpo2 = MutableStateFlow(-1)
    val lastSpo2: StateFlow<Int> = _lastSpo2.asStateFlow()

    // ── 活跃通知数量 ──
    private val _lastNotificationCount = MutableStateFlow(0)
    val lastNotificationCount: StateFlow<Int> = _lastNotificationCount.asStateFlow()

    // ── Update 方法 ──

    fun updateVadStatus(value: String) { _vadStatus.value = value }
    fun updateDbLevel(value: Float) { _currentDbLevel.value = value }
    fun updateDebugState(json: String) { _debugStateJson.value = json }
    fun updateLastSensorText(value: String) { _lastSensorText.value = value }
    fun updateLastResponseText(value: String) { _lastResponseText.value = value }
    fun updateLastGps(value: String) { _lastGps.value = value }
    fun updateLastMediaText(value: String) { _lastMediaText.value = value }
    fun updateHeartRate(value: Int) { _lastHeartRate.value = value }
    fun updateSteps(value: Int) { _lastSteps.value = value }
    fun updateStress(value: Int) { _lastStress.value = value }
    fun updateSpo2(value: Int) { _lastSpo2.value = value }
    fun updateNotificationCount(value: Int) { _lastNotificationCount.value = value }

    // ── Snapshot 方法（非 suspend 获取当前值） ──

    fun snapshotVadStatus(): String = _vadStatus.value
    fun snapshotDbLevel(): Float = _currentDbLevel.value
    fun snapshotDebugState(): String = _debugStateJson.value
    fun snapshotLastSensorText(): String = _lastSensorText.value
    fun snapshotLastResponseText(): String = _lastResponseText.value
    fun snapshotLastGps(): String = _lastGps.value
    fun snapshotLastMediaText(): String = _lastMediaText.value
    fun snapshotHeartRate(): Int = _lastHeartRate.value
    fun snapshotSteps(): Int = _lastSteps.value
    fun snapshotStress(): Int = _lastStress.value
    fun snapshotSpo2(): Int = _lastSpo2.value
    fun snapshotNotificationCount(): Int = _lastNotificationCount.value
}
