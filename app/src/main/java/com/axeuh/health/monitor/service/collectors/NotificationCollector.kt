package com.axeuh.health.monitor.service.collectors

import android.app.Notification
import android.content.Context
import android.service.notification.NotificationListenerService as AndroidNotificationListenerService
import timber.log.Timber
import com.axeuh.health.monitor.network.AppHttpClient
import com.axeuh.health.monitor.service.DataCollectorService
import com.axeuh.health.monitor.service.state.SensorStateHolder
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import org.json.JSONArray
import org.json.JSONObject

/**
 * 通知状态采集器 —— 轮询 (android.service.notification.NotificationListenerService) 获取活跃通知计数和摘要。
 *
 * 通知**内容**由 NotificationListenerService 持续监听并缓存，
 * 本采集器只负责任务性的轮询：获取当前活跃通知的数量和各应用分布。
 *
 * 采集内容（可配置间隔，默认 5s）：
 * 1. 活跃通知总数
 * 2. 各应用的通知数量分布
 *
 * 仅用于更新 [SensorStateHolder] 的通知计数状态。
 */
class NotificationCollector(
    context: Context,
    stateHolder: SensorStateHolder,
    httpClient: AppHttpClient,
    /** 通知服务提供者（可注入 mock 以方便测试） */
    private val notificationServiceProvider: () -> AndroidNotificationListenerService?
) : BaseCollector(context, stateHolder, httpClient) {

    companion object {
        /** 使用 NotificationListenerService.getInstance 创建生产实例 */
        fun create(
            context: Context,
            stateHolder: SensorStateHolder,
            httpClient: AppHttpClient
        ): NotificationCollector {
            val ourServiceClass =
                "com.axeuh.health.monitor.service.NotificationListenerService"
            return NotificationCollector(context, stateHolder, httpClient) {
                try {
                    val clazz = Class.forName(ourServiceClass)
                    val method = clazz.getMethod("getInstance")
                    method.invoke(null) as? AndroidNotificationListenerService
                } catch (_: Exception) {
                    null
                }
            }
        }
    }

    private var scope: CoroutineScope? = null
    override val isEnabled: Boolean
        get() = DataCollectorService.isNotificationEnabled(context)

    override fun start() {
        if (scope != null) return
        scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
        scope!!.launch {
            val initialInterval = getNotifyInterval()
            Timber.i("通知采集已启动（每${initialInterval / 1000}s）")
            while (isActive) {
                try {
                    collectNotificationSummary()
                } catch (e: Exception) {
                    Timber.w("通知采集异常: ${e.message}")
                }
                delay(getNotifyInterval())
            }
        }
    }

    override fun stop() {
        scope?.cancel()
        scope = null
        Timber.i("通知采集已停止")
    }

    /** 从 SharedPreferences 读取通知轮询间隔（默认 5000ms） */
    private fun getNotifyInterval(): Long {
        val prefs = context.getSharedPreferences("data_collector", Context.MODE_PRIVATE)
        return prefs.getLong("notify_ms", 5000L)
    }

    /**
     * 单次采集入口（供内部循环和测试使用）。
     * 采集通知摘要：
     * 1. 通过 [notificationServiceProvider] 获取当前实例
     * 2. 读取 activeNotifications 获取活跃通知列表
     * 3. 统计总数和各应用分布
     * 4. 更新 SensorStateHolder 的通知计数
     */
    internal suspend fun collectNotificationSummary() {
        val nls = notificationServiceProvider() ?: run {
            Timber.d("NotificationListenerService 未运行，跳过采集")
            return
        }
        val sbns = nls.activeNotifications ?: run {
            Timber.d("activeNotifications 为 null，跳过采集")
            return
        }

        val totalCount = sbns.size
        stateHolder.updateNotificationCount(totalCount)

        // 按应用统计通知数量，使用 TreeMap 保证每次输出顺序一致
        val appCounts = java.util.TreeMap<String, Int>()
        for (sbn in sbns) {
            val pkg = sbn.packageName ?: continue
            appCounts[pkg] = (appCounts[pkg] ?: 0) + 1
        }

        Timber.i("通知摘要: $totalCount 条来自 ${appCounts.size} 个应用")
    }
}
