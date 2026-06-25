package com.axeuh.health.monitor.network

import android.content.Context
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOn
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.asRequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.util.concurrent.TimeUnit

/**
 * 下载进度
 *
 * 用于 [AppHttpClient.download] 方法报告下载状态。
 */
sealed class DownloadProgress {
    /** 下载中 */
    data class InProgress(val progressPercent: Int) : DownloadProgress()
    /** 下载完成 */
    data class Completed(val file: File) : DownloadProgress()
    /** 下载失败 */
    data class Failed(val error: String) : DownloadProgress()
}

/**
 * 统一 HTTP 客户端 -- 封装 OkHttp，提供 SSL/TLS 支持、Token 注入和常用方法
 *
 * 替换 App 中所有零散的 [java.net.HttpURLConnection] 调用，统一使用 OkHttp。
 *
 * ## SSL 安全说明
 *
 * 使用系统默认 SSL 验证（OkHttp 默认行为），信任由受信任的 CA 签发的证书。
 * 服务器使用 Let's Encrypt（公共 CA），无需自定义证书信任逻辑。
 *
 * @param appContext Application Context，用于读取 SharedPreferences 中的 auth_token
 */
class AppHttpClient(private val appContext: Context) {

    /** 401 已处理标志，避免重复触发 */
    companion object {
        @Volatile
        var authFailureHandled = false

        /**
         * 全局 401 回调 — 当任何通过 AppHttpClient 的请求收到 401 时触发。
         * 在 MainActivity.onCreate 中注册，用于跳转登录页。
         */
        @Volatile
        var onGlobalUnauthorized: (() -> Unit)? = null

        /**
         * 重置认证失败标志，在成功登录后调用
         */
        fun resetAuthFailureFlag() {
            authFailureHandled = false
        }

        /**
         * 强制登出 — 清除 token + 触发全局 401 回调（跳转登录页）。
         * 供 VoiceprintPanel 等非 AppHttpClient 的 HTTP 调用使用。
         */
        fun forceLogout(context: android.content.Context) {
            if (!authFailureHandled) {
                authFailureHandled = true
                context.getSharedPreferences("axeuh_prefs", Context.MODE_PRIVATE)
                    .edit().remove("auth_token").apply()
                onGlobalUnauthorized?.invoke()
            }
        }
    }

    private val httpClient: OkHttpClient by lazy { buildClient() }

    /** 专用于重登录的独立 OkHttpClient（不含 401 拦截器，避免递归） */
    private val reAuthClient: OkHttpClient by lazy {
        OkHttpClient.Builder()
            .connectTimeout(10, TimeUnit.SECONDS)
            .readTimeout(10, TimeUnit.SECONDS)
            .build()
    }

    /**
     * 发送 GET 请求
     *
     * @param url 目标 URL
     * @return 响应体字符串
     * @throws Exception HTTP 状态码非 2xx 时抛出
     */
    suspend fun get(url: String): String = withContext(Dispatchers.IO) {
        val request = requestBuilder(url).get().build()
        executeRequest(request)
    }

    /**
     * 发送 POST 请求（JSON body）
     *
     * @param url 目标 URL
     * @param body JSON 字符串
     * @return 响应体字符串
     * @throws Exception HTTP 状态码非 2xx 时抛出
     */
    suspend fun post(url: String, body: String): String = withContext(Dispatchers.IO) {
        val request = requestBuilder(url)
            .post(body.toRequestBody("application/json".toMediaType()))
            .build()
        executeRequest(request)
    }

    /**
     * 发送 Multipart POST 请求（文件上传）
     *
     * @param url 目标 URL
     * @param file 要上传的文件
     * @param params 额外的表单参数
     * @return 响应体字符串
     * @throws Exception HTTP 状态码非 2xx 时抛出
     */
    suspend fun postMultipart(
        url: String,
        file: File,
        params: Map<String, String>
    ): String = withContext(Dispatchers.IO) {
        val builder = MultipartBody.Builder()
            .setType(MultipartBody.FORM)
        params.forEach { (key, value) ->
            builder.addFormDataPart(key, value)
        }
        builder.addFormDataPart(
            "file", file.name,
            file.asRequestBody("application/octet-stream".toMediaType())
        )
        val multipartBody = builder.build()
        val request = requestBuilder(url)
            .post(multipartBody)
            .build()
        executeRequest(request)
    }

    /**
     * 下载文件（如 APK），通过 Flow 报告下载进度
     *
     * @param url 下载 URL
     * @param targetFile 目标文件路径
     * @return Flow<[DownloadProgress]> 下载进度流，正常结束会 emit [DownloadProgress.Completed]
     */
    fun download(url: String, targetFile: File): Flow<DownloadProgress> = flow {
        val request = requestBuilder(url).get().build()
        val response = httpClient.newCall(request).execute()
        if (!response.isSuccessful) {
            val errorBody = response.body?.string() ?: response.message
            emit(DownloadProgress.Failed("HTTP ${response.code}: $errorBody"))
            return@flow
        }
        val body = response.body ?: run {
            emit(DownloadProgress.Failed("响应体为空"))
            return@flow
        }
        val contentLength = body.contentLength()
        body.byteStream().use { input ->
            FileOutputStream(targetFile).use { output ->
                val buffer = ByteArray(8192)
                var bytesRead: Int
                var totalRead = 0L
                while (input.read(buffer).also { bytesRead = it } != -1) {
                    output.write(buffer, 0, bytesRead)
                    totalRead += bytesRead
                    if (contentLength > 0) {
                        val progress = ((totalRead.toFloat() / contentLength) * 100).toInt()
                        emit(DownloadProgress.InProgress(progress))
                    }
                }
            }
        }
        emit(DownloadProgress.Completed(targetFile))
    }.flowOn(Dispatchers.IO)

    /**
     * 直接获取 OkHttpClient 实例
     *
     * 用于需要直接访问 OkHttp 的场景（如自定义请求、WebSocket 等）。
     */
    fun getClient(): OkHttpClient = httpClient

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

    /**
     * 构建 OkHttpClient -- 系统默认 SSL + 超时配置
     *
     * 连接超时: 15s
     * 读取超时: 30s
     */
    private fun buildClient(): OkHttpClient {
        return OkHttpClient.Builder()
            .connectTimeout(15, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            // 401 拦截器 — 自动重登录 + 重试原请求
            .addInterceptor { chain ->
                val response = chain.proceed(chain.request())
                if (response.code == 401 && !authFailureHandled) {
                    authFailureHandled = true
                    if (tryReAuth()) {
                        // 重登录成功 → 重置标志，用新 token 重试原请求
                        authFailureHandled = false
                        val newRequest = requestBuilder(chain.request().url.toString())
                            .method(chain.request().method, chain.request().body)
                            .build()
                        return@addInterceptor chain.proceed(newRequest)
                    }
                    // 重登录失败 → 触发回调（跳转登录页）
                    onGlobalUnauthorized?.invoke()
                }
                response
            }
            .build()
    }

    /**
     * 从 SharedPreferences 读取 auth_token
     *
     * 每次请求时读取，不缓存，以支持 token 动态更新。
     */
    private fun authToken(): String {
        val prefs = appContext.getSharedPreferences("axeuh_prefs", Context.MODE_PRIVATE)
        return prefs.getString("auth_token", "") ?: ""
    }

    /**
     * 构建 Request.Builder，自动注入 Authorization header
     *
     * 如果 SharedPreferences 中存在 auth_token，添加 Bearer 认证头。
     */
    private fun requestBuilder(url: String): Request.Builder {
        val builder = Request.Builder().url(url)
        val token = authToken()
        if (token.isNotEmpty()) {
            builder.addHeader("Authorization", "Bearer $token")
        }
        return builder
    }

    /**
     * 执行请求并解析响应
     *
     * @throws Exception HTTP 状态码非 2xx 时抛出，异常消息包含状态码和响应体
     */
    private fun executeRequest(request: Request): String {
        val response = httpClient.newCall(request).execute()
        val body = response.body?.string() ?: ""
        if (!response.isSuccessful) {
            throw Exception("HTTP ${response.code}: $body")
        }
        return body
    }

    /**
     * 尝试使用保存的账号密码重新登录
     *
     * 被 401 拦截器调用，使用独立的 [reAuthClient] 避免递归。
     *
     * @return true=重登录成功（token 已更新），false=重登录失败
     */
    private fun tryReAuth(): Boolean {
        try {
            val prefs = appContext.getSharedPreferences("axeuh_prefs", Context.MODE_PRIVATE)
            val username = prefs.getString("auth_username", "") ?: ""
            val password = encryptedPrefs().getString("auth_password", "") ?: ""
            if (username.isBlank() || password.isBlank()) return false

            val baseUrl = com.axeuh.health.monitor.config.ServerConfig.BASE_URL

            val loginBody = JSONObject().apply {
                put("username", username)
                put("password", password)
            }.toString().toRequestBody("application/json".toMediaType())

            val loginRequest = Request.Builder()
                .url("$baseUrl/login")
                .post(loginBody)
                .build()

            val response = reAuthClient.newCall(loginRequest).execute()
            if (!response.isSuccessful) return false

            val body = response.body?.string() ?: return false
            val json = JSONObject(body)
            val newToken = json.optString("token", "")
            if (newToken.isEmpty()) return false

            // 保存新 token
            prefs.edit().putString("auth_token", newToken).apply()
            return true
        } catch (_: Exception) {
            return false
        }
    }
}
