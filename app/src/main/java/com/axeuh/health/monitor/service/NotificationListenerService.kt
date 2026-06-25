package com.axeuh.health.monitor.service

import android.app.Notification
import android.content.Context
import android.provider.Settings
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import android.util.Log
import java.util.LinkedList

/**
 * NotificationListenerService - 通知监听服务
 *
 * 监听系统所有通知（微信消息、系统通知等），将通知内容缓存到内存。
 * 通过 getRecentNotifications() 供其他组件查询最近通知。
 *
 * 缓存上限 50 条，线程安全（synchronized）。
 *
 * ## Xiaomi / MIUI 兼容性
 * 在 MIUI / HyperOS 上，仅声明 BIND_NOTIFICATION_LISTENER_SERVICE 权限不够，
 * 用户必须手动开启「通知读取权限」：
 *   Settings → 应用设置 → 应用管理 → Axeuh助手 → 通知读取权限
 * 或通过 Intent 引导：
 *   Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS)
 *
 * ## Android 15+ 兼容性
 * notification.extras 可能缺少 EXTRA_TITLE 或 EXTRA_TEXT，代码已做 null 安全处理。
 * extras 本身也可能为 null（罕见但可能），已做 try-catch 保护。
 */
class NotificationListenerService : NotificationListenerService() {

    /**
     * 通知条目数据类
     */
    data class NotificationEntry(
        val packageName: String,
        val title: String,
        val text: String,
        val postTime: Long
    )

    companion object {
        /** 当前正在运行的 NotificationListenerService 实例 */
        @JvmStatic
        var currentInstance: NotificationListenerService? = null
            private set

        /**
         * 检查通知监听服务是否已启用
         * 优先判断 currentInstance（服务正在运行），
         * 回退检查系统设置（解决 MIUI 等 ROM 重启后 currentInstance 丢失的问题）
         */
        @JvmStatic
        fun isListenerEnabled(context: Context? = null): Boolean {
            if (currentInstance != null) return true
            val ctx = context ?: currentInstance ?: return false
            val enabled = try {
                Settings.Secure.getString(
                    ctx.contentResolver,
                    "enabled_notification_listeners"
                )
            } catch (_: Exception) { null }
            return enabled?.contains("com.axeuh.health.monitor/.service.NotificationListenerService") == true
        }

        /**
         * 获取 currentInstance（供 DataCollectorService 直接操作）
         */
        @JvmStatic
        fun getInstance(): NotificationListenerService? = currentInstance
    }

    /** 内存缓存，最多 50 条 */
    @JvmField
    val notificationCache: java.util.LinkedList<NotificationEntry> = LinkedList()

    override fun onListenerConnected() {
        super.onListenerConnected()
        currentInstance = this
    }

    override fun onListenerDisconnected() {
        super.onListenerDisconnected()
        currentInstance = null
    }

    override fun onNotificationPosted(sbn: StatusBarNotification) {
        try {
            val extras = sbn.notification.extras ?: return
            val entry = NotificationEntry(
                packageName = sbn.packageName,
                title = extras.getString(Notification.EXTRA_TITLE) ?: "",
                text = extras.getString(Notification.EXTRA_TEXT) ?: "",
                postTime = sbn.postTime
            )
            synchronized(notificationCache) {
                notificationCache.addLast(entry)
                if (notificationCache.size > 50) {
                    notificationCache.removeFirst()
                }
            }
        } catch (_: Exception) {
            // 通知解析失败时静默跳过，不崩溃
        }
    }

    override fun onNotificationRemoved(sbn: StatusBarNotification) {
        // 通知移除时不做处理，保留在缓存中供历史查询
    }

    /**
     * 获取最近的通知列表（线程安全）
     */
    fun getRecentNotifications(): List<NotificationEntry> {
        synchronized(notificationCache) {
            return notificationCache.toList()
        }
    }
}
