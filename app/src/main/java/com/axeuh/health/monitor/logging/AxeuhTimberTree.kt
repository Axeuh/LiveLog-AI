package com.axeuh.health.monitor.logging

import android.util.Log
import com.axeuh.health.monitor.ui.LogCache
import com.axeuh.health.monitor.ui.LogEntry
import com.axeuh.health.monitor.ui.LogLevel
import timber.log.Timber

/**
 * 自定义 Timber.DebugTree — 将日志写入 [LogCache] 内存缓冲区。
 *
 * [Timber.DebugTree.log] 被 [AxeuhTimberTree.log] 拦截，构造 [LogEntry] 并
 * 同步添加到 [LogCache]。异常堆栈会被转换为字符串附加到 message 尾部。
 */
class AxeuhTimberTree : Timber.DebugTree() {

    override fun log(priority: Int, tag: String?, message: String, t: Throwable?) {
        val level = when (priority) {
            Log.VERBOSE, Log.DEBUG -> LogLevel.DEBUG
            Log.INFO -> LogLevel.INFO
            Log.WARN -> LogLevel.WARN
            Log.ERROR, Log.ASSERT -> LogLevel.ERROR
            else -> LogLevel.DEBUG
        }

        val displayTag = tag ?: "Axeuh"
        val displayMessage = if (t != null) {
            "$message\n${Log.getStackTraceString(t)}"
        } else {
            message
        }

        val entry = LogEntry(
            epochMs = System.currentTimeMillis(),
            tag = displayTag,
            message = displayMessage,
            level = level
        )
        LogCache.add(entry)
    }
}
