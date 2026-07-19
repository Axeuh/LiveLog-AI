package com.axeuh.health.monitor.ui.settings

import android.content.Context
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import com.axeuh.health.monitor.network.AppHttpClient
import com.axeuh.health.monitor.ota.ApkDownloader
import com.axeuh.health.monitor.ota.ApkInstaller
import com.axeuh.health.monitor.ota.DownloadProgress as OtaDownloadProgress
import com.axeuh.health.monitor.ota.InstallResult
import com.axeuh.health.monitor.service.DataCollectorService
import com.axeuh.health.monitor.service.state.SensorStateHolder
import com.axeuh.health.monitor.config.ServerConfig
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.File

// ─── Data Models ───────────────────────────────────────────────────

/** AI 模型项 -- 与 SettingsActivity 中的 private data class 一致 */
data class ApiModelItem(
    val id: String,
    val name: String
)

/** AI 供应商项 -- 与 SettingsActivity 中的 private data class 一致 */
data class ApiProviderItem(
    val id: String,
    val name: String,
    val models: List<ApiModelItem>
)

/**
 * 传感器预览状态 -- 由 SensorStateHolder 的快照值 + debugStateJson 解析得到
 */
data class SensorPreviewState(
    val vadText: String = "",
    val dbText: String = "",
    val healthText: String = "",
    val responseText: String = "",
    val foregroundText: String = "",
    val notifText: String = "",
    val mediaText: String = "",
    val gpsText: String = "",
    val wifiText: String = "",
    val btText: String = "",
    val screenText: String = ""
)

/**
 * SettingsActivity 的 ViewModel -- 提取所有状态管理和网络操作
 *
 * 使用 ViewModelProvider.Factory 模式（无 Hilt）。
 * 所有状态通过 StateFlow 暴露，Activity 通过 collect 观察。
 *
 * @param appContext Application Context，用于 SharedPreferences 和系统服务
 * @param httpClient 统一 HTTP 客户端
 * @param sensorStateHolder 传感器状态持有者（由 Activity 创建并注入）
 */
class SettingsViewModel(
    private val appContext: Context,
    private val httpClient: AppHttpClient,
    val sensorStateHolder: SensorStateHolder
) : ViewModel() {

    // ─── Factory ───────────────────────────────────────────────────

    class Factory(
        private val appContext: Context,
        private val httpClient: AppHttpClient,
        private val sensorStateHolder: SensorStateHolder
    ) : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            if (modelClass.isAssignableFrom(SettingsViewModel::class.java)) {
                return SettingsViewModel(appContext, httpClient, sensorStateHolder) as T
            }
            throw IllegalArgumentException("Unknown ViewModel class: ${modelClass.name}")
        }
    }

    // ─── Constants ─────────────────────────────────────────────────

    companion object {
        const val PREFS_NAME = "axeuh_prefs"
        const val PREFS_SENSORS = "sensor_toggles"
        const val PREFS_DATA_COLLECTOR = "data_collector"
        const val KEY_SERVER_URL = "server_url"
        const val KEY_TOKEN = "auth_token"
        const val KEY_USERNAME = "auth_username"
        const val KEY_PASSWORD = "auth_password"
        private const val LOOP_MS_DEFAULT = 30000L
        private const val NOTIFY_MS_DEFAULT = 5000L
    }

    private fun encryptedPrefs(): android.content.SharedPreferences {
        val masterKey = MasterKey.Builder(appContext)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build()
        return EncryptedSharedPreferences.create(
            appContext,
            "axeuh_secure_prefs",
            masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
        )
    }

    // ═══════════════════════════════════════════════════════════════
    //  Login State
    // ═══════════════════════════════════════════════════════════════

    private val _serverUrl = MutableStateFlow(ServerConfig.BASE_URL)
    val serverUrl: StateFlow<String> = _serverUrl.asStateFlow()

    private val _username = MutableStateFlow("")
    val username: StateFlow<String> = _username.asStateFlow()

    private val _password = MutableStateFlow("")
    val password: StateFlow<String> = _password.asStateFlow()

    private val _isLoggedIn = MutableStateFlow(false)
    val isLoggedIn: StateFlow<Boolean> = _isLoggedIn.asStateFlow()

    private val _loginStatus = MutableStateFlow("未连接")
    val loginStatus: StateFlow<String> = _loginStatus.asStateFlow()

    private val _loginError = MutableStateFlow("")
    val loginError: StateFlow<String> = _loginError.asStateFlow()

    private val _savedUsername = MutableStateFlow("")
    val savedUsername: StateFlow<String> = _savedUsername.asStateFlow()

    // ═══════════════════════════════════════════════════════════════
    //  Sensor Toggles (11 boolean toggles)
    // ═══════════════════════════════════════════════════════════════

    private val _audioEnabled = MutableStateFlow(false)
    val audioEnabled: StateFlow<Boolean> = _audioEnabled.asStateFlow()

    private val _foregroundEnabled = MutableStateFlow(false)
    val foregroundEnabled: StateFlow<Boolean> = _foregroundEnabled.asStateFlow()

    private val _notificationEnabled = MutableStateFlow(false)
    val notificationEnabled: StateFlow<Boolean> = _notificationEnabled.asStateFlow()

    private val _healthEnabled = MutableStateFlow(false)
    val healthEnabled: StateFlow<Boolean> = _healthEnabled.asStateFlow()

    private val _gpsEnabled = MutableStateFlow(false)
    val gpsEnabled: StateFlow<Boolean> = _gpsEnabled.asStateFlow()

    private val _wifiEnabled = MutableStateFlow(false)
    val wifiEnabled: StateFlow<Boolean> = _wifiEnabled.asStateFlow()

    private val _bluetoothEnabled = MutableStateFlow(false)
    val bluetoothEnabled: StateFlow<Boolean> = _bluetoothEnabled.asStateFlow()

    private val _screenStateEnabled = MutableStateFlow(false)
    val screenStateEnabled: StateFlow<Boolean> = _screenStateEnabled.asStateFlow()

    private val _inputContentEnabled = MutableStateFlow(false)
    val inputContentEnabled: StateFlow<Boolean> = _inputContentEnabled.asStateFlow()

    private val _uploadEnabled = MutableStateFlow(true)
    val uploadEnabled: StateFlow<Boolean> = _uploadEnabled.asStateFlow()

    // ═══════════════════════════════════════════════════════════════
    //  Sensor Intervals
    // ═══════════════════════════════════════════════════════════════

    private val _collectionInterval = MutableStateFlow(LOOP_MS_DEFAULT.toInt())
    val collectionInterval: StateFlow<Int> = _collectionInterval.asStateFlow()

    private val _notifyInterval = MutableStateFlow(NOTIFY_MS_DEFAULT.toInt())
    val notifyInterval: StateFlow<Int> = _notifyInterval.asStateFlow()

    // ═══════════════════════════════════════════════════════════════
    //  Hardware DB Path
    // ═══════════════════════════════════════════════════════════════

    private val _dbFilePath = MutableStateFlow("")
    val dbFilePath: StateFlow<String> = _dbFilePath.asStateFlow()

    // ═══════════════════════════════════════════════════════════════
    //  AI Settings
    // ═══════════════════════════════════════════════════════════════

    private val _providers = MutableStateFlow<List<ApiProviderItem>>(emptyList())
    val providers: StateFlow<List<ApiProviderItem>> = _providers.asStateFlow()

    private val _currentModelName = MutableStateFlow("")
    val currentModelName: StateFlow<String> = _currentModelName.asStateFlow()

    private val _currentProviderName = MutableStateFlow("")
    val currentProviderName: StateFlow<String> = _currentProviderName.asStateFlow()

    private val _modelLoading = MutableStateFlow(true)
    val modelLoading: StateFlow<Boolean> = _modelLoading.asStateFlow()

    private val _showVoiceprintPanel = MutableStateFlow(false)
    val showVoiceprintPanel: StateFlow<Boolean> = _showVoiceprintPanel.asStateFlow()

    // ═══════════════════════════════════════════════════════════════
    //  OTA State
    // ═══════════════════════════════════════════════════════════════

    private val _otaStatusText = MutableStateFlow("点击检查更新")
    val otaStatusText: StateFlow<String> = _otaStatusText.asStateFlow()

    private val _otaChecking = MutableStateFlow(false)
    val otaChecking: StateFlow<Boolean> = _otaChecking.asStateFlow()

    private val _otaChangelog = MutableStateFlow("")
    val otaChangelog: StateFlow<String> = _otaChangelog.asStateFlow()

    private val _otaDownloadUrl = MutableStateFlow("")
    val otaDownloadUrl: StateFlow<String> = _otaDownloadUrl.asStateFlow()

    private val _otaProgress = MutableStateFlow(0)
    val otaProgress: StateFlow<Int> = _otaProgress.asStateFlow()

    // ═══════════════════════════════════════════════════════════════
    //  System
    // ═══════════════════════════════════════════════════════════════

    private val _serverUrlText = MutableStateFlow(ServerConfig.BASE_URL)
    val serverUrlText: StateFlow<String> = _serverUrlText.asStateFlow()

    private val _syncStatusText = MutableStateFlow("")
    val syncStatusText: StateFlow<String> = _syncStatusText.asStateFlow()

    // ═══════════════════════════════════════════════════════════════
    //  Sensor Preview (computed from SensorStateHolder + debug JSON)
    // ═══════════════════════════════════════════════════════════════

    private val _sensorPreviewState = MutableStateFlow(SensorPreviewState())
    val sensorPreviewState: StateFlow<SensorPreviewState> = _sensorPreviewState.asStateFlow()

    // ═══════════════════════════════════════════════════════════════
    //  Dialog/Drawer State
    // ═══════════════════════════════════════════════════════════════

    private val _showUsageStatsDialog = MutableStateFlow(false)
    val showUsageStatsDialog: StateFlow<Boolean> = _showUsageStatsDialog.asStateFlow()

    private val _showNotificationListenerDialog = MutableStateFlow(false)
    val showNotificationListenerDialog: StateFlow<Boolean> = _showNotificationListenerDialog.asStateFlow()

    private val _showAccessibilityDialog = MutableStateFlow(false)
    val showAccessibilityDialog: StateFlow<Boolean> = _showAccessibilityDialog.asStateFlow()

    private val _showStoragePermissionDialog = MutableStateFlow(false)
    val showStoragePermissionDialog: StateFlow<Boolean> = _showStoragePermissionDialog.asStateFlow()

    private val _showBandKeyDialog = MutableStateFlow(false)
    val showBandKeyDialog: StateFlow<Boolean> = _showBandKeyDialog.asStateFlow()

    // ═══════════════════════════════════════════════════════════════
    //  Init
    // ═══════════════════════════════════════════════════════════════

    init {
        loadInitialState()
    }

    // ═══════════════════════════════════════════════════════════════
    //  Public Methods
    // ═══════════════════════════════════════════════════════════════

    // ── Login ─────────────────────────────────────────────────────

    /**
     * 执行登录 -- POST /login 获取 token
     */
    fun login() {
        val u = _username.value.trim()
        val p = _password.value
        if (u.isBlank() || p.isBlank()) {
            _loginError.value = "请输入账号和密码"
            return
        }
        viewModelScope.launch {
            _loginStatus.value = "登录中..."
            _loginError.value = ""
            try {
                val result = performLogin(u, p)
                if (result != null) {
                    val prefs = appContext.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                    prefs.edit()
                        .putString(KEY_TOKEN, result)
                        .putString(KEY_USERNAME, u)
                        .apply()
                    encryptedPrefs().edit()
                        .putString(KEY_PASSWORD, p)
                        .apply()
                    _isLoggedIn.value = true
                    _savedUsername.value = u
                    _loginStatus.value = "已连接"
                    com.axeuh.health.monitor.network.AppHttpClient.resetAuthFailureFlag()
                    // 登录成功后加载模型列表
                    loadModels()
                } else {
                    _loginError.value = "账号或密码错误"
                    _loginStatus.value = "未连接"
                }
            } catch (e: Exception) {
                _loginError.value = "网络连接失败: ${e.message}"
                _loginStatus.value = "未连接"
            }
        }
    }

    /**
     * 退出登录 -- 清除 token 和 username
     */
    fun logout() {
        val prefs = appContext.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        prefs.edit()
            .remove(KEY_TOKEN)
            .remove(KEY_USERNAME)
            .apply()
        encryptedPrefs().edit()
            .remove(KEY_PASSWORD)
            .apply()
        _isLoggedIn.value = false
        _savedUsername.value = ""
        _loginStatus.value = "未连接"
        _username.value = ""
        _password.value = ""
    }

    // ── Sensor Toggles ────────────────────────────────────────────

    /**
     * 切换传感器开关，并持久化到 SharedPreferences
     *
     * @param key  传感器标识（audio, foreground, notification, health, gps,
     *             wifi, bluetooth, screen, inputContent, upload）
     * @param enabled 新状态
     */
    fun toggleSensor(key: String, enabled: Boolean) {
        when (key) {
            "audio" -> {
                _audioEnabled.value = enabled
                DataCollectorService.setAudioEnabled(appContext, enabled)
            }
            "foreground" -> {
                _foregroundEnabled.value = enabled
                DataCollectorService.setForegroundEnabled(appContext, enabled)
            }
            "notification" -> {
                _notificationEnabled.value = enabled
                DataCollectorService.setNotificationEnabled(appContext, enabled)
            }
            "health" -> {
                _healthEnabled.value = enabled
                DataCollectorService.setHealthEnabled(appContext, enabled)
            }
            "gps" -> {
                _gpsEnabled.value = enabled
                DataCollectorService.setGpsEnabled(appContext, enabled)
            }
            "wifi" -> {
                _wifiEnabled.value = enabled
                DataCollectorService.setWifiEnabled(appContext, enabled)
            }
            "bluetooth" -> {
                _bluetoothEnabled.value = enabled
                DataCollectorService.setBluetoothEnabled(appContext, enabled)
            }
            "screen" -> {
                _screenStateEnabled.value = enabled
                DataCollectorService.setScreenStateEnabled(appContext, enabled)
            }
            "inputContent" -> {
                _inputContentEnabled.value = enabled
                DataCollectorService.setInputContentEnabled(appContext, enabled)
            }
            "upload" -> {
                _uploadEnabled.value = enabled
                DataCollectorService.setUploadEnabled(appContext, enabled)
            }
        }
    }

    // ── Intervals ─────────────────────────────────────────────────

    /** 设置采集间隔（毫秒） */
    fun setCollectionInterval(ms: Int) {
        _collectionInterval.value = ms
        DataCollectorService.setLoopInterval(appContext, ms.toLong())
    }

    /** 设置通知轮询间隔（毫秒） */
    fun setNotifyInterval(ms: Int) {
        _notifyInterval.value = ms
        DataCollectorService.setNotifyInterval(appContext, ms.toLong())
    }

    // ── DB Path ───────────────────────────────────────────────────

    /** 设置 Gadgetbridge 数据库路径 */
    fun setDbPath(path: String) {
        _dbFilePath.value = path
        DataCollectorService.setDbPath(appContext, path)
    }

    /** 设置 Gadgetbridge 数据库 content URI（SAF 持久化） */
    fun setDbUri(uri: String) {
        DataCollectorService.setDbUri(appContext, uri)
    }

    // ── AI Settings ───────────────────────────────────────────────

    /** 从服务器加载 AI 模型列表 */
    fun loadModels() {
        viewModelScope.launch {
            _modelLoading.value = true
            try {
                val url = "${_serverUrl.value}/api/screen/model"
                val token = appContext.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                    .getString(KEY_TOKEN, "") ?: ""
                val jsonStr = withContext(Dispatchers.IO) {
                    httpClient.get("$url?token=$token")
                }
                val json = JSONObject(jsonStr)
                if (json.optBoolean("success", false)) {
                    val current = json.optJSONObject("current")
                    _currentModelName.value = current?.optString("model", "") ?: ""
                    _currentProviderName.value = current?.optString("provider", "") ?: ""
                    val provs = json.optJSONArray("providers")
                    if (provs != null) {
                        val list = mutableListOf<ApiProviderItem>()
                        for (i in 0 until provs.length()) {
                            val p = provs.getJSONObject(i)
                            val modelsArr = p.optJSONArray("models")
                            val models = mutableListOf<ApiModelItem>()
                            if (modelsArr != null) {
                                for (j in 0 until modelsArr.length()) {
                                    val m = modelsArr.getJSONObject(j)
                                    models.add(
                                        ApiModelItem(
                                            id = m.getString("id"),
                                            name = m.optString("name", m.getString("id"))
                                        )
                                    )
                                }
                            }
                            list.add(
                                ApiProviderItem(
                                    id = p.getString("id"),
                                    name = p.optString("name", p.getString("id")),
                                    models = models
                                )
                            )
                        }
                        _providers.value = list
                    }
                }
            } catch (_: Exception) {
                // 静默失败，保持空列表
            }
            _modelLoading.value = false
        }
    }

    /** 选择 AI 模型 */
    fun selectModel(providerId: String, modelId: String) {
        viewModelScope.launch {
            _currentModelName.value = modelId
            _currentProviderName.value = providerId
            try {
                val url = "${_serverUrl.value}/api/screen/model"
                val token = appContext.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                    .getString(KEY_TOKEN, "") ?: ""
                val body = JSONObject().apply {
                    put("model", modelId)
                    put("provider", providerId)
                }
                withContext(Dispatchers.IO) {
                    httpClient.post(url, body.toString())
                }
            } catch (_: Exception) {
                // 静默失败
            }
        }
    }

    // ── OTA ───────────────────────────────────────────────────────

    /** 检查 OTA 更新 */
    fun checkUpdate() {
        viewModelScope.launch {
            _otaChecking.value = true
            _otaStatusText.value = "检查中..."
            try {
                val baseUrl = _serverUrl.value
                val token = appContext.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                    .getString(KEY_TOKEN, "") ?: ""
                val response = withContext(Dispatchers.IO) {
                    httpClient.get("$baseUrl/api/ota/info?token=$token")
                }
                val json = JSONObject(response)
                if (json.optString("status") == "active") {
                    val fileSize = json.optLong("fileSize", 0L)
                    val sizeMb = fileSize / (1024 * 1024)
                    _otaStatusText.value = "发现更新 (${sizeMb}MB)"
                    _otaDownloadUrl.value = "$baseUrl/api/ota/download?token=$token"
                    _otaChangelog.value = json.optString("changelog", "")
                } else {
                    _otaStatusText.value = "已是最新版本"
                    _otaChangelog.value = ""
                    _otaDownloadUrl.value = ""
                }
            } catch (e: Exception) {
                _otaStatusText.value = "检查失败: ${e.message}"
            }
            _otaChecking.value = false
        }
    }

    /** 下载并安装 OTA 更新 */
    fun downloadUpdate() {
        viewModelScope.launch {
            _otaStatusText.value = "下载中..."
            try {
                val token = appContext.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                    .getString(KEY_TOKEN, "") ?: ""
                val downloader = ApkDownloader(httpClient, authToken = token)
                val targetFile = File(appContext.cacheDir, "axeuh_update.apk")
                downloader.download(_otaDownloadUrl.value, targetFile).collect { p ->
                    when (p) {
                        is OtaDownloadProgress.Started -> {
                            _otaStatusText.value = "下载中..."
                        }
                        is OtaDownloadProgress.InProgress -> {
                            _otaProgress.value = p.progressPercent
                        }
                        is OtaDownloadProgress.Completed -> {
                            _otaStatusText.value = "安装中..."
                            val installer = ApkInstaller(appContext)
                            val result = installer.install(p.file)
                            _otaStatusText.value = if (result is InstallResult.Success) {
                                "更新完成"
                            } else {
                                "安装失败"
                            }
                        }
                    }
                }
            } catch (e: Exception) {
                _otaStatusText.value = "更新失败: ${e.message}"
            }
        }
    }

    // ── Sync ──────────────────────────────────────────────────────

    /** 立即同步数据 */
    fun syncNow() {
        _syncStatusText.value = "同步中..."
        DataCollectorService.triggerSync(appContext)
        viewModelScope.launch {
            kotlinx.coroutines.delay(3000)
            _syncStatusText.value = "同步完成"
        }
    }

    // ── Server URL ────────────────────────────────────────────────

    /** 更新服务器地址并持久化 */
    fun saveServerUrl(url: String) {
        _serverUrlText.value = url
        _serverUrl.value = url
        appContext.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            .edit()
            .putString(KEY_SERVER_URL, url)
            .apply()
        ServerConfig.update(url)
    }

    // ── Sensor Preview ────────────────────────────────────────────

    /**
     * 从 SensorStateHolder 快照刷新传感器预览状态
     *
     * 由 Activity 的 LaunchedEffect 每 2 秒调用一次。
     */
    fun refreshSensorPreviews() {
        _sensorPreviewState.value = computeSensorPreview()
    }

    // ── Dialog State ──────────────────────────────────────────────

    fun showUsageStatsDialog() { _showUsageStatsDialog.value = true }
    fun dismissUsageStatsDialog() { _showUsageStatsDialog.value = false }

    fun showNotificationListenerDialog() { _showNotificationListenerDialog.value = true }
    fun dismissNotificationListenerDialog() { _showNotificationListenerDialog.value = false }

    fun showAccessibilityDialog() { _showAccessibilityDialog.value = true }
    fun dismissAccessibilityDialog() { _showAccessibilityDialog.value = false }

    fun showStoragePermissionDialog() { _showStoragePermissionDialog.value = true }
    fun dismissStoragePermissionDialog() { _showStoragePermissionDialog.value = false }

    fun showBandKeyDialog() { _showBandKeyDialog.value = true }
    fun dismissBandKeyDialog() { _showBandKeyDialog.value = false }

    fun showVoiceprintPanel() { _showVoiceprintPanel.value = true }
    fun dismissVoiceprintPanel() { _showVoiceprintPanel.value = false }

    // ═══════════════════════════════════════════════════════════════
    //  Private Methods
    // ═══════════════════════════════════════════════════════════════

    /**
     * 从 SharedPreferences 加载所有初始状态
     */
    private fun loadInitialState() {
        ServerConfig.init(appContext)
        val axeuhPrefs = appContext.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val sensorPrefs = appContext.getSharedPreferences(PREFS_SENSORS, Context.MODE_PRIVATE)
        val dataPrefs = appContext.getSharedPreferences(PREFS_DATA_COLLECTOR, Context.MODE_PRIVATE)

        // Login
        val savedUrl = ServerConfig.BASE_URL
        _serverUrl.value = savedUrl
        _serverUrlText.value = savedUrl
        val token = axeuhPrefs.getString(KEY_TOKEN, null)
        val user = axeuhPrefs.getString(KEY_USERNAME, null)
        if (!token.isNullOrEmpty()) {
            _isLoggedIn.value = true
            _savedUsername.value = user ?: ""
            _loginStatus.value = "已连接"
        }

        // Sensor toggles
        _audioEnabled.value = DataCollectorService.isAudioEnabled(appContext)
        _foregroundEnabled.value = DataCollectorService.isForegroundEnabled(appContext)
        _notificationEnabled.value = DataCollectorService.isNotificationEnabled(appContext)
        _healthEnabled.value = DataCollectorService.isHealthEnabled(appContext)
        _gpsEnabled.value = DataCollectorService.isGpsEnabled(appContext)
        _wifiEnabled.value = DataCollectorService.isWifiEnabled(appContext)
        _bluetoothEnabled.value = DataCollectorService.isBluetoothEnabled(appContext)
        _screenStateEnabled.value = DataCollectorService.isScreenStateEnabled(appContext)
        _inputContentEnabled.value = DataCollectorService.isInputContentEnabled(appContext)
        _uploadEnabled.value = DataCollectorService.isUploadEnabled(appContext)

        // Intervals
        _collectionInterval.value = DataCollectorService.getLoopInterval(appContext).toInt()
        _notifyInterval.value = DataCollectorService.getNotifyInterval(appContext).toInt()

        // DB path
        _dbFilePath.value = DataCollectorService.getDbPath(appContext)

        // 加载 AI 模型列表（需要 token，已登录时才会成功）
        loadModels()
    }

    /**
     * POST /login -- 使用 HttpURLConnection 发送登录请求
     *
     * 保留与 SettingsActivity 相同的 trust-all SSL 行为。
     */
    private suspend fun performLogin(username: String, password: String): String? =
        withContext(Dispatchers.IO) {
            try {
                val body = JSONObject().apply {
                    put("username", username)
                    put("password", password)
                }
                val response = httpClient.post("${_serverUrl.value}/login", body.toString())
                val json = JSONObject(response)
                if (json.optBoolean("success", false) && !json.isNull("token")) {
                    json.getString("token")
                } else {
                    null
                }
            } catch (_: Exception) {
                null
            }
        }

    /**
     * 计算当前传感器预览状态
     *
     * 从 SensorStateHolder 快照值读取，并解析 debugStateJson 获取
     * 前台应用、WiFi、蓝牙、屏幕、通知数等合成字段。
     */
    private fun computeSensorPreview(): SensorPreviewState {
        val debug = try {
            JSONObject(sensorStateHolder.snapshotDebugState())
        } catch (_: Exception) {
            null
        }

        var foregroundText = ""
        var notifText = ""
        var wifiText = ""
        var btText = ""
        var screenText = ""
        var healthText = sensorStateHolder.snapshotLastSensorText()

        if (debug != null) {
            // 前台应用
            val usageArr = debug.optJSONArray("usage_stats")
            foregroundText = if (usageArr != null && usageArr.length() > 0) {
                usageArr.getJSONObject(0).optString("name", "")
            } else {
                debug.optString("foreground_app", "")
            }

            // 通知数
            val notifCount = debug.optInt("notification_count", -1)
            notifText = when {
                notifCount > 0 -> "通知 ${notifCount}条"
                notifCount == 0 -> "无通知"
                else -> ""
            }

            // WiFi / 蓝牙 / 屏幕
            wifiText = debug.optString("wifi", "")
            btText = debug.optString("bluetooth", "")
            screenText = debug.optString("screen", "")

            // 健康摘要
            val healthParts = mutableListOf<String>()
            debug.optInt("hr", -1).let { if (it > 0) healthParts.add("心率 ${it}bpm") }
            debug.optInt("steps", -1).let { if (it > 0) healthParts.add("步数 $it") }
            debug.optInt("stress", -1).let { if (it > 0) healthParts.add("压力 $it") }
            debug.optInt("spo2", -1).let { if (it > 0) healthParts.add("血氧 ${it}%") }
            if (healthParts.isNotEmpty()) healthText = healthParts.joinToString(" · ")
        }

        return SensorPreviewState(
            vadText = sensorStateHolder.snapshotVadStatus(),
            dbText = "%.1f dBFS".format(sensorStateHolder.snapshotDbLevel().toDouble()),
            healthText = healthText,
            responseText = sensorStateHolder.snapshotLastResponseText(),
            foregroundText = foregroundText,
            notifText = notifText,
            mediaText = sensorStateHolder.snapshotLastMediaText(),
            gpsText = sensorStateHolder.snapshotLastGps(),
            wifiText = wifiText,
            btText = btText,
            screenText = screenText
        )
    }
}
