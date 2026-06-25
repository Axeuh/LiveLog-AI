package com.axeuh.health.monitor.ota

import com.axeuh.health.monitor.network.AppHttpClient
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOn
import okhttp3.Request
import java.io.File
import java.io.FileOutputStream

/**
 * APK 下载进度
 */
sealed class DownloadProgress {
    /** 下载开始，totalBytes 为文件总大小（-1 表示未知） */
    data class Started(val totalBytes: Long) : DownloadProgress()

    /** 下载中 */
    data class InProgress(
        val downloadedBytes: Long,
        val totalBytes: Long,
        val progressPercent: Int
    ) : DownloadProgress()

    /** 下载完成，持有目标文件引用 */
    data class Completed(val file: File) : DownloadProgress()
}

/**
 * APK 下载器 — 通过 AppHttpClient (OkHttp) 下载 APK，通过 Flow 报告下载进度
 */
class ApkDownloader(
    private val httpClient: AppHttpClient,
    private val authToken: String = ""
) {

    /**
     * 下载 APK 到目标文件
     *
     * @param downloadUrl APK 下载地址（http/https）
     * @param targetFile 目标文件路径
     * @return Flow<[DownloadProgress]> 下载进度流，最后一个 emission 为 [DownloadProgress.Completed]
     */
    fun download(downloadUrl: String, targetFile: File): Flow<DownloadProgress> = flow {
        val requestBuilder = Request.Builder().url(downloadUrl)
        if (authToken.isNotEmpty()) {
            requestBuilder.header("Authorization", "Bearer $authToken")
        }
        val response = httpClient.getClient().newCall(requestBuilder.build()).execute()
        val body = response.body ?: throw Exception("响应体为空")
        val totalBytes = body.contentLength()
        var downloadedBytes = 0L

        emit(DownloadProgress.Started(totalBytes))

        body.byteStream().use { input ->
            FileOutputStream(targetFile).use { output ->
                val buffer = ByteArray(BUFFER_SIZE)
                var bytesRead: Int
                while (input.read(buffer).also { bytesRead = it } != -1) {
                    output.write(buffer, 0, bytesRead)
                    downloadedBytes += bytesRead
                    if (totalBytes > 0) {
                        val progress = (downloadedBytes.toFloat() / totalBytes * 100).toInt()
                        emit(DownloadProgress.InProgress(downloadedBytes, totalBytes, progress))
                    }
                }
            }
        }

        emit(DownloadProgress.Completed(targetFile))
    }.flowOn(Dispatchers.IO)

    companion object {
        private const val BUFFER_SIZE = 8192
    }
}
