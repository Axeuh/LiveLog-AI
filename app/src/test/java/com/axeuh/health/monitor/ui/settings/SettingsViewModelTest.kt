package com.axeuh.health.monitor.ui.settings

import android.content.Context
import androidx.lifecycle.ViewModel
import androidx.test.core.app.ApplicationProvider
import com.axeuh.health.monitor.network.AppHttpClient
import com.axeuh.health.monitor.service.state.SensorStateHolder
import io.mockk.mockk
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class SettingsViewModelTest {

    private lateinit var context: Context
    private lateinit var httpClient: AppHttpClient
    private lateinit var sensorStateHolder: SensorStateHolder
    private lateinit var viewModel: SettingsViewModel

    @Before
    fun setUp() {
        context = ApplicationProvider.getApplicationContext()
        httpClient = mockk(relaxed = true)
        sensorStateHolder = SensorStateHolder()

        // Write known initial values to SharedPreferences
        val axeuhPrefs = context.getSharedPreferences(
            SettingsViewModel.PREFS_NAME, Context.MODE_PRIVATE
        )
        val dataPrefs = context.getSharedPreferences(
            SettingsViewModel.PREFS_DATA_COLLECTOR, Context.MODE_PRIVATE
        )
        val sensorPrefs = context.getSharedPreferences(
            SettingsViewModel.PREFS_SENSORS, Context.MODE_PRIVATE
        )

        axeuhPrefs.edit()
            .putString(SettingsViewModel.KEY_SERVER_URL, "https://custom.example.com:8767")
            .putString(SettingsViewModel.KEY_TOKEN, "test_token_123")
            .putString(SettingsViewModel.KEY_USERNAME, "testuser")
            .apply()

        dataPrefs.edit()
            .putBoolean("audio_enabled", true)
            .putBoolean("upload_enabled", false)
            .putLong("loop_ms", 60000L)
            .putLong("notify_ms", 15000L)
            .apply()

        sensorPrefs.edit()
            .putBoolean("foreground_enabled", true)
            .putBoolean("health_enabled", true)
            .putBoolean("gps_enabled", false)
            .putString("gadgetbridge_db_path", "/custom/db/path")
            .apply()

        viewModel = SettingsViewModel(context, httpClient, sensorStateHolder)
    }

    // ── Test 1: Initial state loads from SharedPreferences ─────────

    @Test
    fun `initial login state loads from preferences`() {
        assertTrue("isLoggedIn should be true from saved token", viewModel.isLoggedIn.value)
        assertEquals("savedUsername should match", "testuser", viewModel.savedUsername.value)
        assertEquals("loginStatus should be connected", "已连接", viewModel.loginStatus.value)
        assertEquals("serverUrl should match", "https://custom.example.com:8767", viewModel.serverUrl.value)
        assertEquals("serverUrlText should match", "https://custom.example.com:8767", viewModel.serverUrlText.value)
    }

    @Test
    fun `initial sensor toggles load from preferences`() {
        assertTrue("audio should be enabled", viewModel.audioEnabled.value)
        assertTrue("foreground should be enabled", viewModel.foregroundEnabled.value)
        assertTrue("health should be enabled", viewModel.healthEnabled.value)
        assertFalse("gps should be disabled", viewModel.gpsEnabled.value)
        assertFalse("upload should be disabled", viewModel.uploadEnabled.value)
    }

    @Test
    fun `initial intervals and db path load from preferences`() {
        assertEquals("collectionInterval should be 60000", 60000, viewModel.collectionInterval.value)
        assertEquals("notifyInterval should be 15000", 15000, viewModel.notifyInterval.value)
        assertEquals("dbFilePath should match", "/custom/db/path", viewModel.dbFilePath.value)
    }

    // ── Test 2: Toggle sensor updates StateFlow and SharedPreferences ──

    @Test
    fun `toggleSensor updates StateFlow and SharedPreferences`() {
        // Start with audio = true (from prefs)
        assertTrue(viewModel.audioEnabled.value)

        // Toggle off
        viewModel.toggleSensor("audio", false)
        assertFalse("audioEnabled should be false after toggle", viewModel.audioEnabled.value)

        // Verify SharedPreferences was updated
        val prefs = context.getSharedPreferences(
            SettingsViewModel.PREFS_DATA_COLLECTOR, Context.MODE_PRIVATE
        )
        assertFalse("SharedPreferences audio should be false", prefs.getBoolean("audio_enabled", true))

        // Toggle on
        viewModel.toggleSensor("audio", true)
        assertTrue("audioEnabled should be true after re-toggle", viewModel.audioEnabled.value)
        assertTrue("SharedPreferences audio should be true", prefs.getBoolean("audio_enabled", false))
    }

    @Test
    fun `toggleSensor handles all sensor keys`() {
        // Test each key doesn't crash and updates StateFlow
        val keyValuePairs = listOf(
            "audio" to viewModel.audioEnabled,
            "foreground" to viewModel.foregroundEnabled,
            "notification" to viewModel.notificationEnabled,
            "health" to viewModel.healthEnabled,
            "gps" to viewModel.gpsEnabled,
            "wifi" to viewModel.wifiEnabled,
            "bluetooth" to viewModel.bluetoothEnabled,
            "screen" to viewModel.screenStateEnabled,
            "inputContent" to viewModel.inputContentEnabled,
            "upload" to viewModel.uploadEnabled
        )

        keyValuePairs.forEach { (key, flow) ->
            val original = flow.value
            viewModel.toggleSensor(key, !original)
            assertEquals("$key should toggle to ${!original}", !original, flow.value)
            // Toggle back
            viewModel.toggleSensor(key, original)
            assertEquals("$key should toggle back to $original", original, flow.value)
        }
    }

    // ── Test 3: Interval setters update StateFlow and SharedPreferences ──

    @Test
    fun `setCollectionInterval updates state and prefs`() {
        viewModel.setCollectionInterval(15000)
        assertEquals(15000, viewModel.collectionInterval.value)

        val prefs = context.getSharedPreferences(
            SettingsViewModel.PREFS_DATA_COLLECTOR, Context.MODE_PRIVATE
        )
        assertEquals(15000L, prefs.getLong("loop_ms", 0L))
    }

    @Test
    fun `setNotifyInterval updates state and prefs`() {
        viewModel.setNotifyInterval(30000)
        assertEquals(30000, viewModel.notifyInterval.value)

        val prefs = context.getSharedPreferences(
            SettingsViewModel.PREFS_DATA_COLLECTOR, Context.MODE_PRIVATE
        )
        assertEquals(30000L, prefs.getLong("notify_ms", 0L))
    }

    // ── Test 4: Sensor preview computation ──────────────────────────

    @Test
    fun `refreshSensorPreviews computes from sensorStateHolder`() {
        // Set up SensorStateHolder values
        sensorStateHolder.updateVadStatus("speaking")
        sensorStateHolder.updateDbLevel(-15.5f)
        sensorStateHolder.updateLastResponseText("你好世界")
        sensorStateHolder.updateLastGps("39.9042,116.4074")
        sensorStateHolder.updateLastMediaText("正在播放: 音乐")
        sensorStateHolder.updateLastSensorText("心率 72bpm")

        // Set debug JSON with additional fields
        val debugJson = """
            {
                "foreground_app": "com.example.app",
                "notification_count": 5,
                "wifi": "MyWiFi (-60dBm)",
                "bluetooth": "Mi Band 6",
                "screen": "解锁",
                "hr": 72,
                "steps": 5000,
                "stress": 30,
                "spo2": 98
            }
        """.trimIndent()
        sensorStateHolder.updateDebugState(debugJson)

        // Refresh
        viewModel.refreshSensorPreviews()

        val preview = viewModel.sensorPreviewState.value
        assertEquals("speaking", preview.vadText)
        assertEquals("-15.5 dBFS", preview.dbText)
        assertEquals("你好世界", preview.responseText)
        assertEquals("39.9042,116.4074", preview.gpsText)
        assertEquals("正在播放: 音乐", preview.mediaText)
        assertEquals("com.example.app", preview.foregroundText)
        assertEquals("通知 5条", preview.notifText)
        assertEquals("MyWiFi (-60dBm)", preview.wifiText)
        assertEquals("Mi Band 6", preview.btText)
        assertEquals("解锁", preview.screenText)

        // Health summary should combine lastSensorText with parsed values
        assertTrue("healthText should contain heart rate", preview.healthText.contains("72bpm"))
        assertTrue("healthText should contain steps", preview.healthText.contains("5000"))
        assertTrue("healthText should contain stress", preview.healthText.contains("30"))
        assertTrue("healthText should contain spo2", preview.healthText.contains("98"))
    }

    @Test
    fun `refreshSensorPreviews handles empty debug JSON`() {
        // Debug JSON defaults to "{}"
        sensorStateHolder.updateVadStatus("idle")
        sensorStateHolder.updateDbLevel(-80f)

        viewModel.refreshSensorPreviews()

        val preview = viewModel.sensorPreviewState.value
        assertEquals("idle", preview.vadText)
        assertEquals("-80.0 dBFS", preview.dbText)
        assertEquals("", preview.foregroundText)
        assertEquals("", preview.notifText)
        assertEquals("", preview.wifiText)
        assertEquals("", preview.btText)
        assertEquals("", preview.screenText)
    }

    @Test
    fun `refreshSensorPreviews handles malformed debug JSON`() {
        sensorStateHolder.updateDebugState("not valid json{{{")
        sensorStateHolder.updateVadStatus("idle")

        viewModel.refreshSensorPreviews()

        val preview = viewModel.sensorPreviewState.value
        assertEquals("idle", preview.vadText)
        // Should not crash, field should remain empty
        assertEquals("", preview.foregroundText)
        assertEquals("", preview.notifText)
    }

    // ── Test 5: Logout clears state ──────────────────────────────────

    @Test
    fun `logout clears login state and SharedPreferences`() {
        assertTrue(viewModel.isLoggedIn.value)

        viewModel.logout()

        assertFalse("isLoggedIn should be false after logout", viewModel.isLoggedIn.value)
        assertEquals("savedUsername should be empty", "", viewModel.savedUsername.value)
        assertEquals("loginStatus should be disconnected", "未连接", viewModel.loginStatus.value)
        assertEquals("username should be cleared", "", viewModel.username.value)
        assertEquals("password should be cleared", "", viewModel.password.value)

        // Verify SharedPreferences
        val prefs = context.getSharedPreferences(
            SettingsViewModel.PREFS_NAME, Context.MODE_PRIVATE
        )
        assertTrue("token should be removed from prefs", prefs.getString(SettingsViewModel.KEY_TOKEN, null) == null)
        assertTrue("username should be removed from prefs", prefs.getString(SettingsViewModel.KEY_USERNAME, null) == null)
    }

    // ── Test 6: Factory creates ViewModel correctly ──────────────────

    @Test
    fun `Factory creates correct ViewModel type`() {
        val factory = SettingsViewModel.Factory(context, httpClient, sensorStateHolder)
        val vm = factory.create(SettingsViewModel::class.java)
        assertNotNull("ViewModel should not be null", vm)
        assertTrue("ViewModel should be SettingsViewModel", vm is SettingsViewModel)
    }

    // ── Test 7: DB path persistence ──────────────────────────────────

    @Test
    fun `setDbPath updates state and SharedPreferences`() {
        val newPath = "/storage/emulated/0/Gadgetbridge_new.db"
        viewModel.setDbPath(newPath)
        assertEquals(newPath, viewModel.dbFilePath.value)

        val sensorPrefs = context.getSharedPreferences(
            SettingsViewModel.PREFS_SENSORS, Context.MODE_PRIVATE
        )
        assertEquals(newPath, sensorPrefs.getString("gadgetbridge_db_path", ""))
    }

    // ── Test 8: Server URL persistence ───────────────────────────────

    @Test
    fun `saveServerUrl updates state and SharedPreferences`() {
        val newUrl = "https://new.server.com:8888"
        viewModel.saveServerUrl(newUrl)
        assertEquals(newUrl, viewModel.serverUrlText.value)
        assertEquals(newUrl, viewModel.serverUrl.value)

        val axeuhPrefs = context.getSharedPreferences(
            SettingsViewModel.PREFS_NAME, Context.MODE_PRIVATE
        )
        assertEquals(newUrl, axeuhPrefs.getString(SettingsViewModel.KEY_SERVER_URL, ""))
    }
}
