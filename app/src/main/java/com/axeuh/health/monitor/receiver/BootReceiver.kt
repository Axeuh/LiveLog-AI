package com.axeuh.health.monitor.receiver

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

/**
 * BootReceiver - 开机自启动
 * 接收 BOOT_COMPLETED 广播后启动保活服务
 * TODO: Wave 2 - 实现开机自启动逻辑
 */
class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context?, intent: Intent?) {
        // TODO: Wave 2 - 启动 KeepAliveService
    }
}
