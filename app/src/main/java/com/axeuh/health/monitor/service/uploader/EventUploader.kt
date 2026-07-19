package com.axeuh.health.monitor.service.uploader

import timber.log.Timber
import com.axeuh.health.monitor.network.AppHttpClient
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject

/**
 * 感知事件上传器
 *
 * 使用 [AppHttpClient] 向后端 POST 感知事件（通知/前台App/媒体/传感器/锁屏等）。
 * 替代 [com.axeuh.health.monitor.service.DataCollectorService] 中直接使用
 * [java.net.HttpURLConnection] 的 pushEvent/sendEvent 方法。
 *
 * ## 离线缓存
 *
 * 当服务器不可达时，事件会暂存到内存队列中。
 * 下次成功推送后自动尝试刷新队列中的缓存事件。
 *
 * @param httpClient 统一 HTTP 客户端（OkHttp 封装）
 * @param baseUrl 服务器基础地址，如 "https://localhost:8767"
 */
class EventUploader(
    private val httpClient: AppHttpClient,
    private val baseUrl: String
) {

    private val tag = "EventUploader"

    /** 事件队列锁 */
    private val lock = Any()

    /** 未发送成功的事件暂存队列 */
    private val pendingEvents = mutableListOf<Pair<String, JSONObject>>()

    /** 感知事件上传 URL */
    private val eventUrl: String get() = "$baseUrl/api/screen/stt/perception-event"

    /**
     * 当前缓存的事件数量（仅用于测试/调试）
     */
    val pendingCount: Int get() = synchronized(lock) { pendingEvents.size }

    /**
     * 推送感知事件
     *
     * 尝试立即上传。成功时自动刷新队列中的缓存事件；
     * 失败时将事件入队等待下次推送时重试。
     *
     * ## 请求格式
     *
     * 与 DataCollectorService.pushEvent/sendEvent 保持相同的 JSON 结构：
     * ```json
     * { "type": "app", "payload": { "app": "Chrome" } }
     * ```
     *
     * @param type 事件类型（如 "app", "media", "screen", "sensor", "device_env", "profile"）
     * @param data 事件载荷（JSONObject）
     */
    suspend fun pushEvent(type: String, data: JSONObject) {
        try {
            // 构造请求体，保持与原有格式一致
            val body = JSONObject().apply {
                put("type", type)
                put("payload", data)
            }.toString()

            // 使用 AppHttpClient 发送 POST 请求
            httpClient.post(eventUrl, body)
            Timber.i("pushEvent $type -> HTTP 200")

            // 上传成功，尝试刷新队列
            flushPendingEvents()
        } catch (e: Exception) {
            Timber.w("pushEvent $type 失败: ${e.message}，加入缓存队列")
            // 服务器不可达，暂存到队列
            synchronized(lock) {
                pendingEvents.add(type to data)
            }
        }
    }

    /**
     * 刷新事件队列
     *
     * 尝试依次发送所有缓存事件。某个事件失败时停止，
     * 将该事件重新入队，后续等待下次 [pushEvent] 成功时再次尝试。
     */
    private suspend fun flushPendingEvents() {
        val events: List<Pair<String, JSONObject>>
        synchronized(lock) {
            events = pendingEvents.toList()
            pendingEvents.clear()
        }

        for ((type, data) in events) {
            try {
                val body = JSONObject().apply {
                    put("type", type)
                    put("payload", data)
                }.toString()
                httpClient.post(eventUrl, body)
                Timber.i("flushEvent $type -> HTTP 200")
            } catch (e: Exception) {
                Timber.w("flushEvent $type 失败: ${e.message}，重新入队")
                // 将本次及后续未发送的事件重新入队
                val reQueue = mutableListOf(type to data)
                val remaining = events.subList(events.indexOf(type to data) + 1, events.size)
                reQueue.addAll(remaining)
                synchronized(lock) {
                    pendingEvents.addAll(0, reQueue)
                }
                break
            }
        }
    }
}
