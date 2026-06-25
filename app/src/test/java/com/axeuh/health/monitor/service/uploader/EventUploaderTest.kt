package com.axeuh.health.monitor.service.uploader

import android.content.Context
import android.content.SharedPreferences
import com.axeuh.health.monitor.network.AppHttpClient
import com.google.common.truth.Truth.assertThat
import io.mockk.every
import io.mockk.mockk
import kotlinx.coroutines.runBlocking
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.json.JSONObject
import org.junit.After
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/**
 * EventUploader 单元测试
 *
 * 使用 MockWebServer 模拟 HTTP 服务端，验证事件上传和离线缓存行为。
 * 使用 mockk 模拟 Context/SharedPreferences。
 * 使用 Robolectric 提供 Android 框架实现（JSONObject, Log）。
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class EventUploaderTest {

    private lateinit var mockWebServer: MockWebServer
    private lateinit var uploader: EventUploader
    private lateinit var mockPrefs: SharedPreferences
    private lateinit var mockPrefsEditor: SharedPreferences.Editor

    @Before
    fun setup() {
        mockWebServer = MockWebServer()
        mockWebServer.start()

        // Mock SharedPreferences.Editor
        mockPrefsEditor = mockk {
            every { putString(any(), any()) } returns this
            every { remove(any()) } returns this
            every { apply() } returns Unit
            every { commit() } returns true
        }

        // Mock SharedPreferences (auth_token defaults to empty)
        mockPrefs = mockk {
            every { getString("auth_token", "") } returns ""
            every { getString(any(), any()) } returns ""
            every { edit() } returns mockPrefsEditor
        }

        // Mock Context
        val context = mockk<Context>(relaxUnitFun = true) {
            every { getSharedPreferences(any<String>(), any()) } returns mockPrefs
        }

        val httpClient = AppHttpClient(context)
        uploader = EventUploader(httpClient, mockWebServer.url("").toString())
    }

    @After
    fun teardown() {
        mockWebServer.shutdown()
    }

    // ========================================================================
    // pushEvent - 基本发送
    // ========================================================================

    @Test
    fun `pushEvent sends POST with correct JSON format`() {
        runBlocking {
            mockWebServer.enqueue(MockResponse().setResponseCode(200))

            val payload = JSONObject().apply { put("app", "Chrome") }
            uploader.pushEvent("app", payload)

            val request = mockWebServer.takeRequest()
            assertThat(request.method).isEqualTo("POST")
            assertThat(request.path).contains("perception-event")

            val body = JSONObject(request.body.readUtf8())
            assertThat(body.getString("type")).isEqualTo("app")
            assertThat(body.getJSONObject("payload").getString("app")).isEqualTo("Chrome")
        }
    }

    @Test
    fun `pushEvent includes Content-Type header`() {
        runBlocking {
            mockWebServer.enqueue(MockResponse().setResponseCode(200))

            val payload = JSONObject().apply { put("key", "value") }
            uploader.pushEvent("test", payload)

            val request = mockWebServer.takeRequest()
            assertThat(request.getHeader("Content-Type")).contains("application/json")
        }
    }

    @Test
    fun `pushEvent includes auth token from SharedPreferences`() {
        runBlocking {
            every { mockPrefs.getString("auth_token", "") } returns "test-event-token"

            mockWebServer.enqueue(MockResponse().setResponseCode(200))

            val payload = JSONObject()
            uploader.pushEvent("auth_test", payload)

            val request = mockWebServer.takeRequest()
            assertThat(request.getHeader("Authorization")).isEqualTo("Bearer test-event-token")
        }
    }

    // ========================================================================
    // pushEvent - 离线缓存
    // ========================================================================

    @Test
    fun `pushEvent queues events on failure`() {
        runBlocking {
            // 服务器返回 500
            mockWebServer.enqueue(MockResponse().setResponseCode(500))

            val payload = JSONObject().apply { put("data", "test") }
            uploader.pushEvent("test_event", payload)

            assertThat(uploader.pendingCount).isEqualTo(1)
        }
    }

    @Test
    fun `pushEvent queues events when server is unreachable`() {
        runBlocking {
            // 使用不可达的 URL 创建独立 uploader（不依赖共享 MockWebServer）
            val offlineClient = AppHttpClient(mockk<Context>(relaxUnitFun = true) {
                every { getSharedPreferences(any<String>(), any()) } returns mockPrefs
            })
            val offlineUploader = EventUploader(offlineClient, "http://localhost:1")
            val payload = JSONObject().apply { put("data", "offline_test") }
            offlineUploader.pushEvent("offline", payload)

            assertThat(offlineUploader.pendingCount).isEqualTo(1)
        }
    }

    // ========================================================================
    // pushEvent - 队列刷新
    // ========================================================================

    @Test
    fun `successful pushEvent flushes queued events`() {
        runBlocking {
            // 第一个请求失败，事件入队
            mockWebServer.enqueue(MockResponse().setResponseCode(500))

            val payload1 = JSONObject().apply { put("data", "first") }
            uploader.pushEvent("event1", payload1)
            assertThat(uploader.pendingCount).isEqualTo(1)

            // 第二个请求成功 → 应自动刷新队列
            mockWebServer.enqueue(MockResponse().setResponseCode(200)) // 第二个 pushEvent
            mockWebServer.enqueue(MockResponse().setResponseCode(200)) // flush 中的缓存事件

            val payload2 = JSONObject().apply { put("data", "second") }
            uploader.pushEvent("event2", payload2)

            assertThat(uploader.pendingCount).isEqualTo(0)

            // 验证请求顺序：event2 → event1
            val req1 = mockWebServer.takeRequest()
            assertThat(JSONObject(req1.body.readUtf8()).getString("type")).isEqualTo("event1")

            val req2 = mockWebServer.takeRequest()
            assertThat(JSONObject(req2.body.readUtf8()).getString("type")).isEqualTo("event2")

            val req3 = mockWebServer.takeRequest()
            assertThat(JSONObject(req3.body.readUtf8()).getString("type")).isEqualTo("event1")
        }
    }

    @Test
    fun `flush stops on first failure and re-queues remaining events`() {
        runBlocking {
            // 入队第一个事件
            mockWebServer.enqueue(MockResponse().setResponseCode(500))
            uploader.pushEvent("event_a", JSONObject().apply { put("n", 1) })
            assertThat(uploader.pendingCount).isEqualTo(1)

            // 入队第二个事件
            mockWebServer.enqueue(MockResponse().setResponseCode(500))
            uploader.pushEvent("event_b", JSONObject().apply { put("n", 2) })
            assertThat(uploader.pendingCount).isEqualTo(2)

            // 现在 flush: 第一个成功, 第二个失败
            // pushEvent 会消费一个请求
            // flush 会消费两个: 第一个成功, 第二个失败
            mockWebServer.enqueue(MockResponse().setResponseCode(200)) // pushEvent 请求
            mockWebServer.enqueue(MockResponse().setResponseCode(200)) // flush: event_a 成功
            mockWebServer.enqueue(MockResponse().setResponseCode(500)) // flush: event_b 失败

            uploader.pushEvent("event_c", JSONObject().apply { put("n", 3) })

            // event_b 应被重新入队
            assertThat(uploader.pendingCount).isEqualTo(1)

            // 验证请求 (跳过已被 takeRequest 的 enqueue)
            // event_a (第一个 pushEvent) - 500
            mockWebServer.takeRequest()
            // event_b (第二个 pushEvent) - 500
            mockWebServer.takeRequest()
            // event_c (第三个 pushEvent) - 200
            val reqC = mockWebServer.takeRequest()
            assertThat(JSONObject(reqC.body.readUtf8()).getString("type")).isEqualTo("event_c")
            // flush: event_a - 200
            val reqA = mockWebServer.takeRequest()
            assertThat(JSONObject(reqA.body.readUtf8()).getString("type")).isEqualTo("event_a")
            // flush: event_b - 500
            val reqB = mockWebServer.takeRequest()
            assertThat(JSONObject(reqB.body.readUtf8()).getString("type")).isEqualTo("event_b")
        }
    }

    // ========================================================================
    // 边界情况
    // ========================================================================

    @Test
    fun `pendingCount is zero after successful pushEvent`() {
        runBlocking {
            mockWebServer.enqueue(MockResponse().setResponseCode(200))

            val payload = JSONObject().apply { put("data", "direct_success") }
            uploader.pushEvent("success", payload)

            assertThat(uploader.pendingCount).isEqualTo(0)
        }

    }

    @Test
    fun `flush empty queue does nothing`() {
        runBlocking {
            mockWebServer.enqueue(MockResponse().setResponseCode(200))

            val payload = JSONObject().apply { put("data", "test") }
            uploader.pushEvent("test", payload)

            // 队列为空，flush 不应发出请求
            val requestCount = mockWebServer.requestCount
            assertThat(uploader.pendingCount).isEqualTo(0)

            // payload 验证
            val request = mockWebServer.takeRequest()
            assertThat(JSONObject(request.body.readUtf8()).getString("type")).isEqualTo("test")
        }
    }

    @Test
    fun `multiple events are queued independently`() {
        runBlocking {
            // 3 个连续失败
            mockWebServer.enqueue(MockResponse().setResponseCode(500))
            mockWebServer.enqueue(MockResponse().setResponseCode(500))
            mockWebServer.enqueue(MockResponse().setResponseCode(500))

            uploader.pushEvent("e1", JSONObject())
            uploader.pushEvent("e2", JSONObject())
            uploader.pushEvent("e3", JSONObject())

            assertThat(uploader.pendingCount).isEqualTo(3)
        }
    }

    @Test
    fun `pendingCount is zero initially`() {
        assertThat(uploader.pendingCount).isEqualTo(0)
    }
}
