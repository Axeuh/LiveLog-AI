package com.axeuh.health.monitor.ota

import android.content.Context
import android.content.Intent
import android.util.Log
import androidx.core.content.FileProvider
import java.io.File

/**
 * APK 安装结果
 */
sealed class InstallResult {
    /** 安装成功 */
    data object Success : InstallResult()

    /** 安装失败 */
    data class Failure(
        val error: String,
        val exception: Throwable? = null
    ) : InstallResult()
}

/**
 * APK 安装器 — 通过系统安装工具（ACTION_VIEW）打开 APK
 *
 * 使用 FileProvider 生成 content:// URI 传给系统 PackageInstaller，
 * 用户在系统界面点击确认安装。对 Android 8+ 兼容。
 *
 * @param context Android 上下文
 */
class ApkInstaller(
    private val context: Context
) {

    companion object {
        private const val TAG = "ApkInstaller"
    }

    /**
     * 安装 APK 文件 — 打开系统安装界面
     *
     * @param apkFile 待安装的 APK 文件（必须位于 FileProvider 声明的路径下）
     * @return [InstallResult] 安装结果（启动系统安装器即返回 Success）
     */
    fun install(apkFile: File): InstallResult {
        return try {
            val authority = context.packageName + ".fileprovider"
            val apkUri = FileProvider.getUriForFile(context, authority, apkFile)
            val intent = Intent(Intent.ACTION_VIEW).apply {
                setDataAndType(apkUri, "application/vnd.android.package-archive")
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            }
            context.startActivity(intent)
            Log.i(TAG, "已打开系统安装器: $apkUri")
            InstallResult.Success
        } catch (e: Exception) {
            Log.e(TAG, "启动系统安装器失败: ${e.message}")
            InstallResult.Failure("启动系统安装器失败: ${e.message}", e)
        }
    }
}
