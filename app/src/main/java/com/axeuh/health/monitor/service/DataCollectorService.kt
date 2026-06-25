package com.axeuh.health.monitor.service
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import timber.log.Timber
import androidx.core.app.NotificationCompat
import com.axeuh.health.monitor.network.AppHttpClient
import com.axeuh.health.monitor.service.collectors.*
import com.axeuh.health.monitor.service.state.SensorStateHolder
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class DataCollectorService : Service() {
    companion object {
        private const val TAG = "DataCollector"; private const val NID = 9003
        private const val PD = "data_collector"; private const val PS = "sensor_toggles"
        private var appContext: Context? = null
        private fun p(c: Context, n: String) = c.getSharedPreferences(n, Context.MODE_PRIVATE)
        private fun b(c: Context, n: String, k: String, d: Boolean = false) = p(c, n).getBoolean(k, d)
        private fun sb(c: Context, n: String, k: String, v: Boolean) { p(c, n).edit().putBoolean(k, v).apply() }
        private fun l(c: Context, n: String, k: String, d: Long = 0L) = p(c, n).getLong(k, d)
        private fun sl(c: Context, n: String, k: String, v: Long) { p(c, n).edit().putLong(k, v).apply() }
        private fun s(c: Context, n: String, k: String, d: String? = null) = p(c, n).getString(k, d)
        private fun ss(c: Context, n: String, k: String, v: String) { p(c, n).edit().putString(k, v).apply() }

        @JvmStatic var vadStatus: String = "idle"; @JvmStatic var currentDbLevel: Float = -80f
        @JvmStatic var lastResponseText: String = ""; @JvmStatic var lastResponseJson: String = ""
        @JvmStatic var lastSensorText: String = ""; @JvmStatic var lastAiResponse: String = ""
        @JvmStatic var lastUploadSuccess: Boolean = true; @JvmStatic var lastMediaText: String = ""
        @JvmStatic var debugStateJson: String = "{}"

        @JvmStatic fun isAudioEnabled(c: Context) = b(c, PD, "audio_enabled")
        @JvmStatic fun setAudioEnabled(c: Context, v: Boolean) { sb(c, PD, "audio_enabled", v) }
        @JvmStatic fun isForegroundEnabled(c: Context) = b(c, PS, "foreground_enabled")
        @JvmStatic fun setForegroundEnabled(c: Context, v: Boolean) { sb(c, PS, "foreground_enabled", v) }
        @JvmStatic fun isNotificationEnabled(c: Context) = b(c, PS, "notification_enabled")
        @JvmStatic fun setNotificationEnabled(c: Context, v: Boolean) { sb(c, PS, "notification_enabled", v) }
        @JvmStatic fun isHealthEnabled(c: Context) = b(c, PS, "health_enabled")
        @JvmStatic fun setHealthEnabled(c: Context, v: Boolean) { sb(c, PS, "health_enabled", v) }
        @JvmStatic fun isGpsEnabled(c: Context) = b(c, PS, "gps_enabled")
        @JvmStatic fun setGpsEnabled(c: Context, v: Boolean) { sb(c, PS, "gps_enabled", v) }
        @JvmStatic fun isInputContentEnabled(c: Context) = b(c, PS, "input_content_enabled")
        @JvmStatic fun setInputContentEnabled(c: Context, v: Boolean) { sb(c, PS, "input_content_enabled", v) }
        @JvmStatic fun isWifiEnabled(c: Context) = b(c, PS, "wifi_enabled")
        @JvmStatic fun setWifiEnabled(c: Context, v: Boolean) { sb(c, PS, "wifi_enabled", v) }
        @JvmStatic fun isBluetoothEnabled(c: Context) = b(c, PS, "bluetooth_enabled")
        @JvmStatic fun setBluetoothEnabled(c: Context, v: Boolean) { sb(c, PS, "bluetooth_enabled", v) }
        @JvmStatic fun isScreenStateEnabled(c: Context) = b(c, PS, "screen_state_enabled")
        @JvmStatic fun setScreenStateEnabled(c: Context, v: Boolean) { sb(c, PS, "screen_state_enabled", v) }
        @JvmStatic fun isBatteryEnabled(c: Context) = b(c, PS, "battery_enabled", true)
        @JvmStatic fun setBatteryEnabled(c: Context, v: Boolean) { sb(c, PS, "battery_enabled", v) }
        @JvmStatic fun isUploadEnabled(c: Context) = b(c, PD, "upload_enabled", true)
        @JvmStatic fun setUploadEnabled(c: Context, v: Boolean) { sb(c, PD, "upload_enabled", v) }
        @JvmStatic fun getLoopInterval(c: Context) = l(c, PD, "loop_ms", 30000L)
        @JvmStatic fun setLoopInterval(c: Context, v: Long) { sl(c, PD, "loop_ms", v) }
        @JvmStatic fun getNotifyInterval(c: Context) = l(c, PD, "notify_ms", 5000L)
        @JvmStatic fun setNotifyInterval(c: Context, v: Long) { sl(c, PD, "notify_ms", v) }
        @JvmStatic fun getLastSyncTs(c: Context) = l(c, PD, "last_sync_ts")
        @JvmStatic fun setLastSyncTs(c: Context, v: Long) { sl(c, PD, "last_sync_ts", v) }
        private const val DEFAULT_DB_PATH = "/storage/emulated/0/Gadgetbridge.db"
        @JvmStatic fun getDbPath(c: Context) = s(c, PS, "gadgetbridge_db_path") ?: DEFAULT_DB_PATH
        @JvmStatic fun setDbPath(c: Context, v: String) { ss(c, PS, "gadgetbridge_db_path", v) }
        @JvmStatic fun getDbFile(c: Context) = File(getDbPath(c))

        private val _logBuffer = java.util.LinkedList<String>()
        @JvmStatic fun log(tag: String, msg: String) = synchronized(_logBuffer) {
            _logBuffer.addLast("${SimpleDateFormat("HH:mm:ss", Locale.getDefault()).format(Date())} $tag: $msg")
            if (_logBuffer.size > 200) _logBuffer.removeFirst()
        }
        @JvmStatic fun getRecentLogs(n: Int = 100) = synchronized(_logBuffer) { _logBuffer.takeLast(n).toList() }

        @JvmStatic
        fun pushEvent(type: String, payload: JSONObject) {
            Thread({
                try {
                    val ctx = appContext ?: return@Thread
                    val baseUrl = com.axeuh.health.monitor.config.ServerConfig.BASE_URL
                    val token = s(ctx, "axeuh_prefs", "auth_token") ?: ""
                    val httpClient = AppHttpClient(ctx)
                    val requestBody = JSONObject().apply { put("type", type); put("payload", payload) }.toString()
                        .toRequestBody("application/json".toMediaType())
                    val requestBuilder = okhttp3.Request.Builder()
                        .url("$baseUrl/api/screen/stt/perception-event")
                        .post(requestBody)
                    if (token.isNotEmpty()) {
                        requestBuilder.header("Authorization", "Bearer $token")
                    }
                    val response = httpClient.getClient().newCall(requestBuilder.build()).execute()
                    Timber.i("pushEvent $type -> HTTP ${response.code}")
                } catch (e: Exception) {
                    Timber.w("pushEvent $type: ${e.message}")
                }
            }, "DcPushEvent").start()
        }

        @JvmStatic fun triggerCycle(c: Context) { try { c.startService(Intent(c, DataCollectorService::class.java).putExtra("trigger_cycle", true)) } catch (e: Exception) { Timber.w("triggerCycle: ${e.message}") } }
        @JvmStatic fun triggerSync(c: Context) { try { c.startService(Intent(c, DataCollectorService::class.java).putExtra("force_sync", true)) } catch (e: Exception) { Timber.w("triggerSync: ${e.message}") } }
        @JvmStatic fun getDebugState(): String = debugStateJson
    }

    private var isRunning = false
    private val handler = Handler(Looper.getMainLooper())
    private lateinit var sh: SensorStateHolder
    private lateinit var hc: AppHttpClient
    private lateinit var cm: CollectorManager
    private var notificationLoopRunnable: Runnable? = null

    override fun onBind(intent: Intent?) = null

    override fun onCreate() {
        super.onCreate(); appContext = this; createNotificationChannel()
        com.axeuh.health.monitor.config.ServerConfig.init(this)
        sh = SensorStateHolder(); hc = AppHttpClient(this); cm = CollectorManager(this, sh, hc)
        val f = IntentFilter().apply { addAction(Intent.ACTION_SCREEN_ON); addAction(Intent.ACTION_SCREEN_OFF) }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) registerReceiver(screenReceiver, f, RECEIVER_NOT_EXPORTED)
        else registerReceiver(screenReceiver, f)
        startNotificationPolling()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        startForeground(NID, createNotification())
        when {
            intent?.getBooleanExtra("force_sync", false) == true -> { Timber.i("Force sync"); cm.forceSync(); return START_STICKY }
            intent?.getBooleanExtra("trigger_cycle", false) == true -> { Timber.i("Trigger cycle"); handler.post { updateSnapshot() }; return START_STICKY }
            intent?.getBooleanExtra("force_restart", false) == true -> {
                Timber.i("Force restart audio"); (getSystemService(Context.NOTIFICATION_SERVICE) as? NotificationManager)?.cancel(1001)
                handler.post { cm.restartAudio() }; return START_STICKY
            }
        }
        if (!isRunning) { isRunning = true; cm.startAll(); startMainLoop() }
        return START_STICKY
    }

    override fun onDestroy() {
        isRunning = false; cm.stopAll(); handler.removeCallbacksAndMessages(null)
        notificationLoopRunnable?.let { handler.removeCallbacks(it) }
        try { unregisterReceiver(screenReceiver) } catch (_: Exception) {}
        try { (getSystemService(Context.NOTIFICATION_SERVICE) as? NotificationManager)?.cancel(1001) } catch (_: Exception) {}
        if (isAudioEnabled(this)) showServiceStoppedNotification(); super.onDestroy()
    }

    private val screenReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context, intent: Intent) {
            pushEvent("screen", JSONObject().apply { put("locked", intent.action == Intent.ACTION_SCREEN_OFF) })
        }
    }

    private fun startMainLoop() {
        handler.post(object : Runnable {
            override fun run() {
                if (!isRunning) return
                try {
                    try { sendBroadcast(Intent("nodomain.freeyourgadget.gadgetbridge.command.ACTIVITY_SYNC")) } catch (_: Exception) {}
                    try { sendBroadcast(Intent("nodomain.freeyourgadget.gadgetbridge.command.TRIGGER_EXPORT")) } catch (_: Exception) {}
                    val s = JSONObject()
                    if (isGpsEnabled(this@DataCollectorService)) {
                        sh.snapshotLastGps().takeIf { it.isNotEmpty() }?.let { s.put("gps", it) }
                    }
                    if (isBatteryEnabled(this@DataCollectorService)) {
                        try { val bi = registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
                            if (bi != null) s.put("phone_battery", bi.getIntExtra("level", 0) * 100 / bi.getIntExtra("scale", 100)) } catch (_: Exception) {}
                    }
                    if (s.length() > 0) pushEvent("sensor", s)
                    updateSnapshot()
                } catch (e: Exception) { Timber.w("Loop: ${e.message}") }
                handler.postDelayed(this, getLoopInterval(this@DataCollectorService))
            }
        })
    }

    inner class CollectorManager(
        private val ctx: Context, private val sh: SensorStateHolder, private val hc: AppHttpClient
    ) {
        private val sc = SystemStateCollector(ctx, sh, hc)
        private val nc = NotificationCollector.create(ctx, sh, hc)
        private val gc = GpsCollector(ctx, sh, hc)
        private val hdc = HealthDataCollector(ctx, sh, hc)
        private val ac = AudioCollector(ctx, sh, hc)
        fun startAll() {
            if (sc.isEnabled) sc.start()
            if (nc.isEnabled) nc.start()
            if (gc.isEnabled) gc.start()
            if (hdc.isEnabled) hdc.start()
            if (isAudioEnabled(ctx)) ac.start()
            Timber.i("${listOf(sc.isEnabled, nc.isEnabled, gc.isEnabled, hdc.isEnabled, ac.isEnabled).count { it }} 个采集器已启动")
        }
        fun stopAll() { sc.stop(); nc.stop(); gc.stop(); hdc.stop(); ac.stop(); Timber.i("Collectors stopped") }
        fun restartAudio() { ac.stop(); if (isAudioEnabled(ctx)) ac.start() }
        fun forceSync() { Timber.i("Force sync"); updateSnapshot() }
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val nm = getSystemService(NotificationManager::class.java)
        nm.createNotificationChannel(NotificationChannel("axeuh_datacollector", "Axeuh 数据采集", NotificationManager.IMPORTANCE_MIN).apply { setShowBadge(false); description = "传感器+语音采集" })
        nm.createNotificationChannel(NotificationChannel("axeuh_notification", "Axeuh 系统通知", NotificationManager.IMPORTANCE_HIGH).apply { setShowBadge(true); description = "AI 推送通知" })
    }

    private fun createNotification() = NotificationCompat.Builder(this, "axeuh_datacollector")
        .setContentTitle("Axeuh 数据采集").setContentText("传感器+语音采集运行中")
        .setSmallIcon(android.R.drawable.ic_menu_compass).setOngoing(true).setPriority(NotificationCompat.PRIORITY_MIN).build()

    private fun showServiceStoppedNotification() {
        try {
            val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager; val ch = "axeuh_service_stopped"
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) nm.createNotificationChannel(NotificationChannel(ch, "Service Status", NotificationManager.IMPORTANCE_DEFAULT))
            val pi = PendingIntent.getActivity(this, 0, packageManager.getLaunchIntentForPackage(packageName), PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
            nm.notify(1002, NotificationCompat.Builder(this, ch).setSmallIcon(android.R.drawable.ic_dialog_alert)
                .setContentTitle("采集已停止").setContentText("点击重新启动").setAutoCancel(true).setContentIntent(pi).build())
        } catch (_: Exception) {}
    }

    private fun startNotificationPolling() {
        notificationLoopRunnable = Runnable {
            Thread({
                try {
                    val ctx = this@DataCollectorService
                    val baseUrl = com.axeuh.health.monitor.config.ServerConfig.BASE_URL
                    val token = s(ctx, "axeuh_prefs", "auth_token") ?: ""
                    val requestBuilder = okhttp3.Request.Builder()
                        .url("$baseUrl/api/notification/poll")
                        .get()
                    if (token.isNotEmpty()) {
                        requestBuilder.header("Authorization", "Bearer $token")
                    }
                    val response = hc.getClient().newCall(requestBuilder.build()).execute()
                    val body = response.body?.string() ?: ""
                    if (response.isSuccessful && body.isNotEmpty()) {
                        val json = JSONObject(body)
                        val notifications = json.optJSONArray("notifications")
                        if (notifications != null) {
                            for (i in 0 until notifications.length()) {
                                val item = notifications.getJSONObject(i)
                                val id = item.getInt("id")
                                val title = item.optString("title", "")
                                val content = item.optString("content", "")
                                showSystemNotification(title, content, id)
                            }
                        }
                    }
                } catch (e: Exception) {
                    Timber.w("Notification poll: ${e.message}")
                }
                handler.postDelayed(notificationLoopRunnable!!, getNotifyInterval(this@DataCollectorService))
            }, "NotificationPoll").start()
        }
        handler.postDelayed(notificationLoopRunnable!!, getNotifyInterval(this@DataCollectorService))
    }

    private fun showSystemNotification(title: String, content: String, id: Int) {
        try {
            val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            val pi = PendingIntent.getActivity(this, 0, packageManager.getLaunchIntentForPackage(packageName), PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
            nm.notify(9004 + id, NotificationCompat.Builder(this, "axeuh_notification")
                .setSmallIcon(android.R.drawable.ic_dialog_info)
                .setContentTitle(title)
                .setContentText(content)
                .setAutoCancel(true)
                .setContentIntent(pi)
                .setPriority(NotificationCompat.PRIORITY_HIGH)
                .build())
        } catch (e: Exception) {
            Timber.w("showSystemNotification: ${e.message}")
        }
    }

    private fun updateSnapshot() {
        try {
            debugStateJson = JSONObject().apply {
                put("running", isRunning); put("vad", sh.snapshotVadStatus())
                put("hr", sh.snapshotHeartRate()); put("steps", sh.snapshotSteps())
                put("stress", sh.snapshotStress()); put("spo2", sh.snapshotSpo2())
                put("gps", sh.snapshotLastGps().take(50))
                put("last_sensor_text", sh.snapshotLastSensorText().take(100))
                put("last_response_text", sh.snapshotLastResponseText().take(80))
                put("last_media_text", sh.snapshotLastMediaText().take(80))
            }.toString(2)
            vadStatus = sh.snapshotVadStatus(); currentDbLevel = sh.snapshotDbLevel()
            lastSensorText = sh.snapshotLastSensorText(); lastResponseText = sh.snapshotLastResponseText()
            lastMediaText = sh.snapshotLastMediaText()
        } catch (_: Exception) {}
    }
}
