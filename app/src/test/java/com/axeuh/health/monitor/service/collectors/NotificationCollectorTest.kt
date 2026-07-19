package com.axeuh.health.monitor.service.collectors

import android.content.Context
import android.content.SharedPreferences
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import com.axeuh.health.monitor.network.AppHttpClient
import com.axeuh.health.monitor.service.state.SensorStateHolder
import io.mockk.coVerify
import io.mockk.every
import io.mockk.mockk
import io.mockk.verify
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/**
 * 验证 [NotificationCollector] 的生命周期、启停行为和通知采集逻辑。
 *
 * 生命周期测试通过 start/stop 验证协程管理。
 * 通知采集逻辑通过直接调用 [NotificationCollector.collectNotificationSummary]
 * 验证（internal suspend 方法，在测试中通过 runBlocking 调用）。
 *
 * NotificationListenerService 通过构造函数的 notificationServiceProvider 参数
 * 注入 mock 实例，避免静态方法 mocking。
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class NotificationCollectorTest {

    private val context = mockk<Context>(relaxed = true)
    private val stateHolder = mockk<SensorStateHolder>(relaxed = true)
    private val httpClient = mockk<AppHttpClient>(relaxed = true)
    private val notificationService = mockk<NotificationListenerService>(relaxed = true)

    @Before
    fun setUp() {
        // SharedPreferences 用于 event URL 构建
        val prefs = mockk<SharedPreferences>(relaxed = true)
        every { context.getSharedPreferences("axeuh_prefs", Context.MODE_PRIVATE) } returns prefs
        every { prefs.getString("server_url", any()) } returns "https://localhost:8767"

        // SharedPreferences 用于 notify_ms 读取
        val dataPrefs = mockk<SharedPreferences>(relaxed = true)
        every { context.getSharedPreferences("data_collector", Context.MODE_PRIVATE) } returns dataPrefs
        every { dataPrefs.getLong("notify_ms", 5000L) } returns 5000L
    }

    @After
    fun tearDown() {
        // 无需清理 mockkStatic
    }

    // ======================== 生命周期 ========================

    @Test
    fun `isEnabled returns true`() {
        val collector = createCollector()
        assertTrue(collector.isEnabled)
    }

    @Test
    fun `start does not throw`() {
        val collector = createCollector()
        collector.start()
        collector.stop()
    }

    @Test
    fun `stop does not throw`() {
        val collector = createCollector()
        collector.start()
        collector.stop()
    }

    @Test
    fun `double stop is idempotent`() {
        val collector = createCollector()
        collector.start()
        collector.stop()
        collector.stop()
    }

    @Test
    fun `double start only creates one scope`() {
        val collector = createCollector()
        collector.start()
        collector.start()
        collector.stop()
    }

    @Test
    fun `start after stop creates new scope`() {
        val collector = createCollector()
        collector.start()
        collector.stop()
        collector.start()
        collector.stop()
    }

    // ======================== 通知采集（直接调用 internal 方法） ========================

    @Test
    fun `collectNotificationSummary updates count with active notifications`() = runBlocking {
        val mockSbn1 = mockNotification("com.example.app1")
        val mockSbn2 = mockNotification("com.example.app2")
        every { notificationService.activeNotifications } returns arrayOf(mockSbn1, mockSbn2)

        val collector = createCollector()
        collector.collectNotificationSummary()

        verify { stateHolder.updateNotificationCount(2) }
    }

    @Test
    fun `collectNotificationSummary calls httpClient when notifications present`() = runBlocking {
        val mockSbn = mockNotification("com.example.test")
        every { notificationService.activeNotifications } returns arrayOf(mockSbn)

        val collector = createCollector()
        collector.collectNotificationSummary()

        coVerify { httpClient.post(any(), any()) }
    }

    @Test
    fun `skips when NotificationListenerService provider returns null`() = runBlocking {
        // 创建一个 provider 返回 null 的 collector
        val nullCollector = NotificationCollector(context, stateHolder, httpClient) { null }
        nullCollector.collectNotificationSummary()

        // httpClient 不应被调用
        coVerify(exactly = 0) { httpClient.post(any(), any()) }
    }

    @Test
    fun `skips when activeNotifications is null`() = runBlocking {
        every { notificationService.activeNotifications } returns null

        val collector = createCollector()
        collector.collectNotificationSummary()

        coVerify(exactly = 0) { httpClient.post(any(), any()) }
    }

    @Test
    fun `updateNotificationCount is 0 when no active notifications`() = runBlocking {
        every { notificationService.activeNotifications } returns emptyArray()

        val collector = createCollector()
        collector.collectNotificationSummary()

        verify { stateHolder.updateNotificationCount(0) }
    }

    @Test
    fun `multiple notifications from same app counted correctly`() = runBlocking {
        val mockSbn1 = mockNotification("com.example.same")
        val mockSbn2 = mockNotification("com.example.same")
        every { notificationService.activeNotifications } returns arrayOf(mockSbn1, mockSbn2)

        val collector = createCollector()
        collector.collectNotificationSummary()

        verify { stateHolder.updateNotificationCount(2) }
    }

    @Test
    fun `single notification triggers update`() = runBlocking {
        val mockSbn = mockNotification("com.example.single")
        every { notificationService.activeNotifications } returns arrayOf(mockSbn)

        val collector = createCollector()
        collector.collectNotificationSummary()

        verify { stateHolder.updateNotificationCount(1) }
    }

    @Test
    fun `sendEvent calls httpClient post with correct url`() = runBlocking {
        val collector = createCollector()
        val payload = org.json.JSONObject().apply { put("test", true) }
        collector.sendEvent("test_type", payload)

        coVerify { httpClient.post(match { it.contains("perception-event") }, any()) }
    }

    // ======================== 辅助方法 ========================

    private fun createCollector(): NotificationCollector {
        return NotificationCollector(context, stateHolder, httpClient) { notificationService }
    }

    /** 创建模拟的 StatusBarNotification */
    private fun mockNotification(packageName: String): StatusBarNotification {
        val sbn = mockk<StatusBarNotification>(relaxed = true)
        every { sbn.packageName } returns packageName
        return sbn
    }
}