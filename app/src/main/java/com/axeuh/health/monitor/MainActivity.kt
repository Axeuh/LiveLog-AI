package com.axeuh.health.monitor

import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.util.Log
import timber.log.Timber
import com.axeuh.health.monitor.logging.AxeuhTimberTree
import androidx.activity.ComponentActivity
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import com.axeuh.health.monitor.network.AppHttpClient
import com.axeuh.health.monitor.config.ServerConfig
import com.axeuh.health.monitor.service.DataCollectorService
import com.axeuh.health.monitor.service.KeepAliveService
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * 主 Activity — Axeuh助手 启动入口
 *
 * 启动流程：
 * 1. 检查 SharedPreferences 中是否有 auth_token
 * 2. 无 token → 跳转 SettingsActivity（登录页）
 * 3. 有 token → HTTP 检查服务器 /health
 * 4. 服务器在线 → 跳转 MobileActivity（WebView 手机页）
 * 5. 服务器离线 → 跳转 SettingsActivity
 * 6. 跳转后 finish() 自身，不留在回退栈
 */
class MainActivity : ComponentActivity() {

    companion object {
        private const val TAG = "AxeuhMain"
    }

    /** Android 13+ 通知权限请求 */
    private val notificationPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        Log.i(TAG, "通知权限: ${if (granted) "已授予" else "已拒绝"}")
    }

    /** Android 13+ 申请通知权限（前台服务、通知轮询需要） */
    private fun requestNotificationPermission() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (ContextCompat.checkSelfPermission(this, android.Manifest.permission.POST_NOTIFICATIONS)
                != PackageManager.PERMISSION_GRANTED) {
                notificationPermissionLauncher.launch(android.Manifest.permission.POST_NOTIFICATIONS)
            }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        Timber.plant(AxeuhTimberTree())
        ServerConfig.init(this)

        // 注册全局 401 回调 — 收到 401 时清除 token 并跳转登录页
        AppHttpClient.resetAuthFailureFlag()
        AppHttpClient.onGlobalUnauthorized = {
            runOnUiThread {
                Log.i(TAG, "收到 401，跳转登录页")
                startActivity(Intent(this, SettingsActivity::class.java).apply {
                    flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_CLEAR_TASK
                })
                finish()
            }
        }

        // 全局未捕获异常处理
        Thread.setDefaultUncaughtExceptionHandler { thread, e ->
            Log.e(TAG, "全局未捕获异常: ${e.message}", e)
        }

        // Android 13+ 申请通知权限（前台服务通知需要）
        requestNotificationPermission()

        try {
            startKeepAliveService()
            startDataCollectorServiceIfEnabled()

            // 读取已保存的 token
            val prefs = getSharedPreferences("axeuh_prefs", MODE_PRIVATE)
            val token = prefs.getString("auth_token", null)
            val customUrl = ServerConfig.BASE_URL

            if (token.isNullOrEmpty()) {
                // 无 token → 跳转设置页登录
                Log.i(TAG, "无 token，跳转设置页")
                startActivity(Intent(this, SettingsActivity::class.java))
                finish()
                return
            }

            // 有 token → 后台检查服务器健康
            lifecycleScope.launch {
                try {
                    val httpClient = AppHttpClient(this@MainActivity)
                    withContext(Dispatchers.IO) {
                        httpClient.get("$customUrl/health")
                    }
                    Log.i(TAG, "服务器在线，启动手机管家")
                    startActivity(Intent(this@MainActivity, MobileActivity::class.java).apply {
                        putExtra("baseUrl", customUrl)
                        putExtra("token", token)
                    })
                } catch (e: Exception) {
                    Log.e(TAG, "服务器健康检查失败: ${e.message}")
                    startActivity(Intent(this@MainActivity, SettingsActivity::class.java))
                }
                finish()
            }

        } catch (e: Exception) {
            Log.e(TAG, "启动初始化失败: ${e.message}", e)
        }
    }

    /** 如果之前开启了上传，启动 DataCollectorService */
    private fun startDataCollectorServiceIfEnabled() {
        try {
            if (DataCollectorService.isUploadEnabled(this)) {
                val intent = Intent(this, DataCollectorService::class.java)
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    startForegroundService(intent)
                } else {
                    startService(intent)
                }
                Log.i(TAG, "自动启动 DataCollectorService（upload 已开启）")
            }
        } catch (_: Exception) { }
    }

    private fun startKeepAliveService() {
        try {
            val intent = Intent(this, KeepAliveService::class.java)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                startForegroundService(intent)
            } else {
                startService(intent)
            }
        } catch (_: Exception) { }
    }
}
