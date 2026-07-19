package com.axeuh.health.monitor.service.uploader

import android.content.Context
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import timber.log.Timber
import com.axeuh.health.monitor.network.AppHttpClient
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * 感知事件离线缓存 — 当前台应用/通知/GPS/锁屏等感知事件上传失败时，
 * 保存到本地文件，下次成功发送前自动重放。
 *
 * ## 缓存格式
 * ```
 * perception_cache/{timestamp_ms}_{type}.json
 * {"type":"app","payload":{"app":"Chrome"}}
 * ```
 *
 * ## 工作流
 * 1. [save]：上传失败时调用，写入缓存文件
 * 2. [flushSync] / [flushSuspend]：下次发送前调用，按序重放后删除
 *
 * 不依赖 AppHttpClient（兼容 Thread 和协程两种上下文），
 * 调用方传入自己的 HTTP 客户端即可。
 */
object PerceptionCache {

    private const val TAG = "PerceptionCache"
    private const val CACHE_DIR = "perception_cache"

    /**
     * 保存感知事件到本地缓存。
     *
     * @param ctx Context（用于获取 cacheDir）
     * @param type 事件类型（"app", "media", "device_env", "sensor", "screen"）
     * @param payload 事件载荷
     */
    fun save(ctx: Context, type: String, payload: JSONObject) {
        try {
            val dir = File(ctx.cacheDir, CACHE_DIR)
            dir.mkdirs()
            val ts = SimpleDateFormat("HH:mm:ss", Locale.getDefault()).format(Date())
            val data = JSONObject().apply {
                put("type", type)
                put("payload", payload)
                put("ts", ts)
            }
            val file = File(dir, "${System.currentTimeMillis()}_${type}.json")
            file.writeText(data.toString())
            Timber.tag(TAG).i("感知事件已缓存: ${file.name}")
        } catch (e: Exception) {
            Timber.tag(TAG).w("感知事件缓存失败: ${e.message}")
        }
    }

    /**
     * 同步刷新全部缓存（用于 [Thread] 上下文）。
     *
     * @param ctx Context（用于获取 cacheDir）
     * @param client OkHttpClient 实例
     * @param baseUrl 服务器基础地址
     * @param token Bearer token
     */
    fun flushSync(
        ctx: Context,
        client: OkHttpClient,
        baseUrl: String,
        token: String
    ) {
        val dir = File(ctx.cacheDir, CACHE_DIR)
        if (!dir.exists()) return
        val files = dir.listFiles { f -> f.isFile && f.name.endsWith(".json") }
            ?.sortedBy { it.name } ?: return
        if (files.isEmpty()) return

        val url = "$baseUrl/api/screen/stt/perception-event"
        Timber.tag(TAG).i("刷新 ${files.size} 个缓存感知事件...")

        for (f in files) {
            try {
                val body = f.readText()
                    .toRequestBody("application/json".toMediaType())
                val request = Request.Builder()
                    .url(url)
                    .apply {
                        if (token.isNotEmpty()) {
                            addHeader("Authorization", "Bearer $token")
                        }
                    }
                    .post(body)
                    .build()
                val response = client.newCall(request).execute()
                if (response.isSuccessful) {
                    f.delete()
                    Timber.tag(TAG).i("缓存事件已发送: ${f.name}")
                } else {
                    Timber.tag(TAG).w("缓存事件发送失败 HTTP ${response.code}，停止")
                    break
                }
            } catch (e: Exception) {
                Timber.tag(TAG).w("缓存事件发送异常: ${e.message}，停止")
                break
            }
        }
    }

    /**
     * 协程刷新全部缓存（用于 suspend 上下文）。
     *
     * @param ctx Context（用于获取 cacheDir）
     * @param client AppHttpClient 实例（已有 token 注入）
     * @param baseUrl 服务器基础地址
     */
    suspend fun flushSuspend(
        ctx: Context,
        client: AppHttpClient,
        baseUrl: String
    ) {
        val dir = File(ctx.cacheDir, CACHE_DIR)
        if (!dir.exists()) return
        val files = dir.listFiles { f -> f.isFile && f.name.endsWith(".json") }
            ?.sortedBy { it.name } ?: return
        if (files.isEmpty()) return

        val url = "$baseUrl/api/screen/stt/perception-event"
        Timber.tag(TAG).i("刷新 ${files.size} 个缓存感知事件...")

        for (f in files) {
            try {
                client.post(url, f.readText())
                f.delete()
                Timber.tag(TAG).i("缓存事件已发送: ${f.name}")
            } catch (e: Exception) {
                Timber.tag(TAG).w("缓存事件发送异常: ${e.message}，停止")
                break
            }
        }
    }
}
