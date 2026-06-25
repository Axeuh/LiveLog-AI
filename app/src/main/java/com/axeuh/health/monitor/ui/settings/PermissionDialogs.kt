package com.axeuh.health.monitor.ui.settings

import android.app.AppOpsManager
import android.app.usage.UsageStatsManager
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.Process
import android.provider.Settings
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.axeuh.health.monitor.service.DataCollectorService

/**
 * 权限引导弹窗容器组件
 *
 * 包含 5 个权限引导弹窗，当用户启用对应传感器但权限缺失时弹出：
 * 1. 使用情况访问权限（前台应用感知）
 * 2. 通知监听权限（通知感知）
 * 3. 无障碍服务权限（输入内容感知）
 * 4. 存储权限（健康数据感知）
 * 5. 手环数据采集设置指南（Gadgetbridge）
 *
 * @param viewModel SettingsViewModel 实例，提供弹窗状态和操作方法
 */
@Composable
fun PermissionDialogs(viewModel: SettingsViewModel) {
    val context = LocalContext.current

    // ── 权限设置页面启动器 ──

    // 使用情况访问设置页面
    val usageStatsSettingsLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.StartActivityForResult()
    ) { /* 从设置页面返回后自动刷新 */ }

    // 通知监听设置页面
    val notificationListenerLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.StartActivityForResult()
    ) {
        // 从系统设置返回后，重新检查权限并自动开启开关
        if (hasNotificationListenerPermission(context)) {
            viewModel.toggleSensor("notification", true)
        }
    }

    // 无障碍服务设置页面
    val accessibilitySettingsLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.StartActivityForResult()
    ) {
        if (hasAccessibilityServiceEnabled(context)) {
            viewModel.toggleSensor("inputContent", true)
        }
    }

    // 文件选择器（手环数据库路径）
    val dbFilePickerLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.OpenDocument()
    ) { uri ->
        if (uri != null) {
            try {
                // 把 content:// URI 转为真实文件路径
                val docId = android.provider.DocumentsContract.getDocumentId(uri)
                val parts = docId.split(":")
                val realPath = if (parts.size >= 2 && "primary".equals(parts[0], ignoreCase = true)) {
                    "/storage/emulated/0/${parts.subList(1, parts.size).joinToString(":")}"
                } else if (parts.size >= 2) {
                    "/storage/${parts[0]}/${parts.subList(1, parts.size).joinToString(":")}"
                } else {
                    docId
                }
                viewModel.setDbPath(realPath)
                android.util.Log.d("PermissionDialogs", "手环 DB 路径已设置为: $realPath")
            } catch (_: Exception) { }
        }
    }

    // 存储权限设置页面（Android 11+ MANAGE_EXTERNAL_STORAGE）
    val manageStorageLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.StartActivityForResult()
    ) {
        if (hasStoragePermission(context)) {
            viewModel.toggleSensor("health", true)
            viewModel.toggleSensor("upload", true)
            ensureServiceRunning(context, true)
        }
    }

    // 存储权限请求（Android 10 及以下 READ_EXTERNAL_STORAGE）
    val readStorageLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (granted) {
            viewModel.toggleSensor("health", true)
            viewModel.toggleSensor("upload", true)
            ensureServiceRunning(context, true)
        }
    }

    // ── 使用情况访问权限弹窗 ──
    if (viewModel.showUsageStatsDialog.collectAsState().value) {
        UsageStatsPermissionDialog(
            onDismiss = { viewModel.dismissUsageStatsDialog() },
            onGoToSettings = {
                viewModel.dismissUsageStatsDialog()
                val intent = Intent(Settings.ACTION_USAGE_ACCESS_SETTINGS)
                usageStatsSettingsLauncher.launch(intent)
            }
        )
    }

    // ── 通知监听权限弹窗 ──
    if (viewModel.showNotificationListenerDialog.collectAsState().value) {
        NotificationListenerPermissionDialog(
            onDismiss = { viewModel.dismissNotificationListenerDialog() },
            onGoToSettings = {
                viewModel.dismissNotificationListenerDialog()
                val intent = Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS)
                notificationListenerLauncher.launch(intent)
            }
        )
    }

    // ── 无障碍服务权限弹窗 ──
    if (viewModel.showAccessibilityDialog.collectAsState().value) {
        AccessibilityServiceDialog(
            onDismiss = { viewModel.dismissAccessibilityDialog() },
            onGoToSettings = {
                viewModel.dismissAccessibilityDialog()
                val intent = Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)
                accessibilitySettingsLauncher.launch(intent)
            }
        )
    }

    // ── 存储权限弹窗 ──
    if (viewModel.showStoragePermissionDialog.collectAsState().value) {
        StoragePermissionDialog(
            onDismiss = { viewModel.dismissStoragePermissionDialog() },
            onGoToSettings = {
                viewModel.dismissStoragePermissionDialog()
                if (Build.VERSION.SDK_INT >= 30) {
                    manageStorageLauncher.launch(
                        Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION).apply {
                            data = android.net.Uri.parse("package:${context.packageName}")
                        }
                    )
                } else {
                    readStorageLauncher.launch(android.Manifest.permission.READ_EXTERNAL_STORAGE)
                }
            }
        )
    }

    // ── 手环数据采集设置指南弹窗 ──
    if (viewModel.showBandKeyDialog.collectAsState().value) {
        BandKeyGuideDialog(
            onDismiss = { viewModel.dismissBandKeyDialog() }
        )
    }
}

// ─── 单个弹窗组件 ─────────────────────────────────────────────────

/**
 * 使用情况访问权限引导弹窗
 *
 * 引导用户开启「使用情况访问」权限，用于读取当前前台应用信息。
 */
@Composable
private fun UsageStatsPermissionDialog(
    onDismiss: () -> Unit,
    onGoToSettings: () -> Unit
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("使用情况访问权限") },
        text = {
            Text(
                "需要开启「使用情况访问」权限才能读取当前前台应用信息。" +
                        "请在系统设置中为「Axeuh 助手」开启此权限。"
            )
        },
        confirmButton = {
            Button(onClick = onGoToSettings) { Text("去设置") }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("取消") }
        }
    )
}

/**
 * 通知监听权限引导弹窗
 *
 * 引导用户开启「通知监听」权限，用于读取系统通知内容。
 */
@Composable
private fun NotificationListenerPermissionDialog(
    onDismiss: () -> Unit,
    onGoToSettings: () -> Unit
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("通知监听权限") },
        text = {
            Text(
                "需要开启「通知监听」权限才能读取系统通知内容。" +
                        "请在系统设置中为「Axeuh 助手」开启此权限。"
            )
        },
        confirmButton = {
            Button(onClick = onGoToSettings) { Text("去设置") }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("取消") }
        }
    )
}

/**
 * 无障碍服务权限引导弹窗
 *
 * 引导用户开启无障碍服务，用于收集键盘输入内容。
 */
@Composable
private fun AccessibilityServiceDialog(
    onDismiss: () -> Unit,
    onGoToSettings: () -> Unit
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("无障碍服务权限") },
        text = {
            Text(
                "需要开启无障碍服务才能收集键盘输入内容。" +
                        "请在系统设置中为「Axeuh 助手」开启此权限。"
            )
        },
        confirmButton = {
            Button(onClick = onGoToSettings) { Text("去设置") }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("取消") }
        }
    )
}

/**
 * 存储权限引导弹窗
 *
 * 引导用户开启存储权限，用于直接读取 Gadgetbridge 手环数据库。
 */
@Composable
private fun StoragePermissionDialog(
    onDismiss: () -> Unit,
    onGoToSettings: () -> Unit
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("存储权限") },
        text = {
            Text(
                "需要授予存储权限才能直接读取 Gadgetbridge 手环数据库。" +
                        "请在系统设置中为「Axeuh 助手」开启「所有文件访问权限」。"
            )
        },
        confirmButton = {
            Button(onClick = onGoToSettings) { Text("去设置") }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("取消") }
        }
    )
}

/**
 * 手环数据采集设置指南弹窗
 *
 * 显示 Gadgetbridge 数据库导出配置步骤和手环 Auth Key 获取方法。
 */
@Composable
private fun BandKeyGuideDialog(
    onDismiss: () -> Unit
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("手环数据采集设置") },
        text = {
            Column(modifier = Modifier.verticalScroll(rememberScrollState())) {
                Text(
                    "首次使用按以下步骤操作：",
                    fontWeight = FontWeight.Bold,
                    fontSize = 14.sp
                )
                Spacer(Modifier.height(8.dp))
                Text("1. Gadgetbridge 设置 → 自动化 → 自动导出数据库 → 开启", fontSize = 13.sp)
                Text("2. 导出间隔设为一小时（不改也行）", fontSize = 13.sp)
                Text("3. 点击「立即运行自动导出」", fontSize = 13.sp)
                Spacer(Modifier.height(4.dp))
                Text("4. 返回 Axeuh App → 选择数据库文件", fontSize = 13.sp)
                Text("5. 选中 Gadgetbridge 导出的 .db 文件", fontSize = 13.sp)
                Text("6. 下方健康数据区域验证是否能读到数据", fontSize = 13.sp)
                Spacer(Modifier.height(8.dp))
                Text(
                    "确认数据可读后，开启蓝牙 Intent API：",
                    fontWeight = FontWeight.Bold,
                    fontSize = 13.sp
                )
                Spacer(Modifier.height(4.dp))
                Text("7. Gadgetbridge 设置 → 开发者选项", fontSize = 13.sp)
                Text("8. 意图接口 → 蓝牙 Intent API → 开启", fontSize = 13.sp)
                Text("9. 允许数据库导出 → 开启", fontSize = 13.sp)
                Text("10. 数据库导出时广播 → 开启", fontSize = 13.sp)
                Spacer(Modifier.height(8.dp))
                Text(
                    "打开后 App 后台 Service 可自动触发 Gadgetbridge 导出，实现自动采集。",
                    fontSize = 12.sp,
                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f)
                )
                Spacer(Modifier.height(8.dp))
                HorizontalDividerCompact()
                Spacer(Modifier.height(8.dp))
                Text(
                    "手环 Auth Key 获取步骤：",
                    fontWeight = FontWeight.Bold,
                    fontSize = 13.sp
                )
                Spacer(Modifier.height(4.dp))
                Text("1. 安装小米运动健康 App，连接手环正常使用", fontSize = 12.sp)
                Text("2. 用 MT 文件管理器打开 /sdcard/Android/data/com.mi.health/files/log/", fontSize = 12.sp)
                Text("3. 找到 Transfer.device.log，搜索 token", fontSize = 12.sp)
                Text("4. 能找到两种 token：小米账号 token 和手环 Auth Key，都试试", fontSize = 12.sp)
                Text("5. Auth Key 是 32 位十六进制字符串（纯 0-9 a-f）", fontSize = 12.sp)
                Spacer(Modifier.height(8.dp))
                Text(
                    "连接 Gadgetbridge 后务必关闭小米运动健康后台：",
                    fontWeight = FontWeight.Bold,
                    fontSize = 12.sp,
                    color = MaterialTheme.colorScheme.error.copy(alpha = 0.8f)
                )
                Spacer(Modifier.height(2.dp))
                Text("设置 → 应用管理 → 小米运动健康 → 关闭自启动、禁止后台、禁止获取设备列表", fontSize = 12.sp)
                Spacer(Modifier.height(4.dp))
                Text(
                    "详细说明见 app/docs/band_data_collection_guide.md",
                    fontSize = 11.sp,
                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.4f)
                )
            }
        },
        confirmButton = {
            Button(onClick = onDismiss) { Text("知道了") }
        }
    )
}

// ─── 内部组件 ─────────────────────────────────────────────────────

/**
 * 分组内紧凑分隔线
 */
@Composable
private fun HorizontalDividerCompact() {
    androidx.compose.material3.HorizontalDivider(
        modifier = Modifier.padding(vertical = 2.dp),
        color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.08f),
        thickness = 0.5.dp
    )
}

// ─── 权限检查工具函数 ─────────────────────────────────────────────

/**
 * 检查 Usage Stats 权限是否已开启
 */
private fun hasUsageStatsPermission(context: Context): Boolean {
    return try {
        val appOps = context.getSystemService(Context.APP_OPS_SERVICE) as? AppOpsManager ?: return false
        val mode = appOps.checkOpNoThrow(
            AppOpsManager.OPSTR_GET_USAGE_STATS,
            Process.myUid(),
            context.packageName
        )
        if (mode == AppOpsManager.MODE_ALLOWED) return true

        // 兜底检查：queryUsageStats 是否能返回数据
        val usm = context.getSystemService(Context.USAGE_STATS_SERVICE) as? UsageStatsManager ?: return false
        val now = System.currentTimeMillis()
        val stats = usm.queryUsageStats(UsageStatsManager.INTERVAL_DAILY, now - 86400000, now)
        stats != null && stats.isNotEmpty()
    } catch (_: Exception) {
        false
    }
}

/**
 * 检查 Notification Listener 权限是否已开启
 */
private fun hasNotificationListenerPermission(context: Context): Boolean {
    val cn = Settings.Secure.getString(
        context.contentResolver, "enabled_notification_listeners"
    ) ?: return false
    return cn.contains("com.axeuh.health.monitor.service.NotificationListenerService")
}

/**
 * 检查存储权限（API 30+ 用 MANAGE_EXTERNAL_STORAGE，旧版用 READ_EXTERNAL_STORAGE）
 */
private fun hasStoragePermission(context: Context): Boolean {
    return if (Build.VERSION.SDK_INT >= 30) {
        android.os.Environment.isExternalStorageManager()
    } else {
        context.checkSelfPermission(android.Manifest.permission.READ_EXTERNAL_STORAGE) == 0
    }
}

/**
 * 检查无障碍服务 AxeuhAccessibilityService 是否已开启
 */
private fun hasAccessibilityServiceEnabled(context: Context): Boolean {
    val cn = Settings.Secure.getString(
        context.contentResolver,
        Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES
    ) ?: return false
    return cn.contains(".service.AxeuhAccessibilityService")
}

/**
 * 确保 DataCollectorService 在开启传感器时正在运行
 */
private fun ensureServiceRunning(context: Context, enabled: Boolean) {
    if (!enabled) return
    try {
        val i = Intent(context, DataCollectorService::class.java)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            context.startForegroundService(i)
        } else {
            context.startService(i)
        }
        android.util.Log.d("PermissionDialogs", "DataCollectorService 已启动（传感器开启）")
    } catch (_: Exception) { }
}
