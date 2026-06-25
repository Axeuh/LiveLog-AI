package com.axeuh.health.monitor.ui.settings

import android.app.AppOpsManager
import android.app.usage.UsageStatsManager
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.Process
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.axeuh.health.monitor.HorizontalDividerCompact
import com.axeuh.health.monitor.SettingsGroup
import com.axeuh.health.monitor.SettingsSwitchItem
import com.axeuh.health.monitor.service.DataCollectorService
import kotlinx.coroutines.delay

/**
 * 传感器控制面板 -- 提取自 SettingsActivity
 *
 * 包含 11 个传感器开关、采集间隔配置、通知轮询间隔、
 * 手环数据库路径选择、传感器预览显示。
 *
 * @param viewModel SettingsViewModel，提供所有 StateFlow 和操作方法
 */
@Composable
fun SensorControls(viewModel: SettingsViewModel) {
    val context = LocalContext.current

    // ── 从 ViewModel 收集状态 ──────────────────────────────────────
    val audioEnabled by viewModel.audioEnabled.collectAsState()
    val foregroundEnabled by viewModel.foregroundEnabled.collectAsState()
    val notificationEnabled by viewModel.notificationEnabled.collectAsState()
    val healthEnabled by viewModel.healthEnabled.collectAsState()
    val gpsEnabled by viewModel.gpsEnabled.collectAsState()
    val wifiEnabled by viewModel.wifiEnabled.collectAsState()
    val bluetoothEnabled by viewModel.bluetoothEnabled.collectAsState()
    val screenStateEnabled by viewModel.screenStateEnabled.collectAsState()
    val inputContentEnabled by viewModel.inputContentEnabled.collectAsState()
    val uploadEnabled by viewModel.uploadEnabled.collectAsState()
    val collectionInterval by viewModel.collectionInterval.collectAsState()
    val notifyInterval by viewModel.notifyInterval.collectAsState()
    val dbFilePath by viewModel.dbFilePath.collectAsState()
    val sensorPreview by viewModel.sensorPreviewState.collectAsState()

    // ── 本地 UI 状态 ──────────────────────────────────────────────
    var customIntervalSec by remember { mutableStateOf("") }

    // ── 权限引导弹窗状态 ──────────────────────────────────────────
    var showUsageStatsDialog by remember { mutableStateOf(false) }
    var showNotificationListenerDialog by remember { mutableStateOf(false) }
    var showAccessibilityDialog by remember { mutableStateOf(false) }
    var showStoragePermissionDialog by remember { mutableStateOf(false) }
    var showBandKeyDialog by remember { mutableStateOf(false) }

    // ── 权限 Launcher ─────────────────────────────────────────────
    val usageStatsSettingsLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.StartActivityForResult()
    ) { /* 从设置页返回后自动刷新 */ }

    val notificationListenerLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.StartActivityForResult()
    ) {
        if (hasNotificationListenerPermission(context)) {
            viewModel.toggleSensor("notification", true)
            ensureServiceRunning(context, true)
        }
    }

    val audioPermissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (granted) {
            viewModel.toggleSensor("audio", true)
            ensureServiceRunning(context, true)
        }
    }

    val locationPermissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestMultiplePermissions()
    ) { granted ->
        if (granted.values.any { it }) {
            // GPS 和 WiFi 共用定位权限，回调中不指定具体传感器
            // 由调用方在 onCheckedChange 中自行处理
        }
    }

    val accessibilitySettingsLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.StartActivityForResult()
    ) {
        if (hasAccessibilityServiceEnabled(context)) {
            viewModel.toggleSensor("inputContent", true)
            ensureServiceRunning(context, true)
        }
    }

    val bluetoothPermissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (granted) {
            viewModel.toggleSensor("bluetooth", true)
            ensureServiceRunning(context, true)
        }
    }

    val manageStorageLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.StartActivityForResult()
    ) {
        if (hasStoragePermission(context)) {
            viewModel.toggleSensor("health", true)
            ensureServiceRunning(context, true)
        }
    }

    val readStorageLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (granted) {
            viewModel.toggleSensor("health", true)
            ensureServiceRunning(context, true)
        }
    }

    val dbFilePickerLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.OpenDocument()
    ) { uri ->
        if (uri != null) {
            try {
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
            } catch (_: Exception) { }
        }
    }

    // ── 定时刷新传感器预览 ────────────────────────────────────────
    LaunchedEffect(Unit) {
        while (true) {
            viewModel.refreshSensorPreviews()
            delay(2000)
        }
    }

    // ── 传感器控制 UI ─────────────────────────────────────────────
    SettingsGroup(title = "数据采集") {
        // ── 总开关 ──
        SettingsSwitchItem(
            label = "感知数据上传",
            description = "总开关，关闭后停止整个采集服务",
            checked = uploadEnabled,
            onCheckedChange = { en ->
                viewModel.toggleSensor("upload", en)
                if (en) {
                    val svcIntent = Intent(context, DataCollectorService::class.java)
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                        context.startForegroundService(svcIntent)
                    } else {
                        context.startService(svcIntent)
                    }
                    DataCollectorService.triggerCycle(context)
                } else {
                    context.stopService(Intent(context, DataCollectorService::class.java))
                }
            }
        )

        HorizontalDividerCompact()
        // ── 声音感知 ──
        SettingsSwitchItem(
            label = "声音感知",
            description = "麦克风录音及语音活动检测",
            checked = audioEnabled,
            onCheckedChange = { en ->
                if (en && context.checkSelfPermission(android.Manifest.permission.RECORD_AUDIO)
                    != android.content.pm.PackageManager.PERMISSION_GRANTED
                ) {
                    audioPermissionLauncher.launch(android.Manifest.permission.RECORD_AUDIO)
                } else {
                    viewModel.toggleSensor("audio", en)
                    ensureServiceRunning(context, en)
                }
            }
        )
        if (audioEnabled && sensorPreview.dbText.isNotBlank()) {
            Text(
                sensorPreview.dbText,
                fontSize = 11.sp,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f),
                modifier = Modifier.padding(start = 4.dp, bottom = 4.dp)
            )
        }

        HorizontalDividerCompact()
        // ── 前台应用感知 ──
        SettingsSwitchItem(
            label = "前台应用感知",
            description = "获取当前运行的应用信息",
            checked = foregroundEnabled,
            onCheckedChange = { en ->
                if (en && !hasUsageStatsPermission(context)) {
                    showUsageStatsDialog = true
                } else {
                    viewModel.toggleSensor("foreground", en)
                    ensureServiceRunning(context, en)
                }
            }
        )
        if (foregroundEnabled && sensorPreview.foregroundText.isNotBlank()) {
            Text(
                sensorPreview.foregroundText,
                fontSize = 11.sp,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f),
                modifier = Modifier.padding(start = 4.dp, bottom = 4.dp)
            )
        }

        HorizontalDividerCompact()
        // ── 通知感知 ──
        SettingsSwitchItem(
            label = "通知感知",
            description = "读取系统通知内容",
            checked = notificationEnabled,
            onCheckedChange = { en ->
                if (en && !hasNotificationListenerPermission(context)) {
                    showNotificationListenerDialog = true
                } else {
                    viewModel.toggleSensor("notification", en)
                    ensureServiceRunning(context, en)
                }
            }
        )
        if (notificationEnabled) {
            if (sensorPreview.notifText.isNotBlank()) {
                Text(
                    sensorPreview.notifText,
                    fontSize = 11.sp,
                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f),
                    modifier = Modifier.padding(start = 4.dp, bottom = 2.dp)
                )
            }
            if (sensorPreview.mediaText.isNotBlank()) {
                Text(
                    sensorPreview.mediaText,
                    fontSize = 11.sp,
                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f),
                    modifier = Modifier.padding(start = 4.dp, bottom = 4.dp)
                )
            }
        }

        HorizontalDividerCompact()
        // ── 健康数据感知 ──
        SettingsSwitchItem(
            label = "健康数据感知",
            description = "心率/步数/血氧/压力传感器",
            checked = healthEnabled,
            onCheckedChange = { en ->
                if (en && !hasStoragePermission(context)) {
                    showStoragePermissionDialog = true
                } else {
                    viewModel.toggleSensor("health", en)
                    ensureServiceRunning(context, en)
                }
            }
        )
        if (healthEnabled && sensorPreview.healthText.isNotBlank()) {
            Text(
                sensorPreview.healthText,
                fontSize = 11.sp,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f),
                modifier = Modifier.padding(start = 4.dp, bottom = 4.dp),
                maxLines = 2
            )
        }

        HorizontalDividerCompact()
        // ── GPS 感知 ──
        SettingsSwitchItem(
            label = "GPS 感知",
            description = "位置信息采集",
            checked = gpsEnabled,
            onCheckedChange = { en ->
                if (en) {
                    val fineOk = context.checkSelfPermission(android.Manifest.permission.ACCESS_FINE_LOCATION)
                    val coarseOk = context.checkSelfPermission(android.Manifest.permission.ACCESS_COARSE_LOCATION)
                    if (fineOk != android.content.pm.PackageManager.PERMISSION_GRANTED &&
                        coarseOk != android.content.pm.PackageManager.PERMISSION_GRANTED
                    ) {
                        locationPermissionLauncher.launch(
                            arrayOf(
                                android.Manifest.permission.ACCESS_FINE_LOCATION,
                                android.Manifest.permission.ACCESS_COARSE_LOCATION
                            )
                        )
                        return@SettingsSwitchItem
                    }
                }
                viewModel.toggleSensor("gps", en)
                ensureServiceRunning(context, en)
            }
        )
        if (gpsEnabled && sensorPreview.gpsText.isNotBlank()) {
            Text(
                sensorPreview.gpsText,
                fontSize = 11.sp,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f),
                modifier = Modifier.padding(start = 4.dp, bottom = 4.dp)
            )
        }

        HorizontalDividerCompact()
        // ── WiFi/移动数据感知 ──
        SettingsSwitchItem(
            label = "WiFi/移动数据感知",
            description = "获取WiFi名称、信号强度、网络类型",
            checked = wifiEnabled,
            onCheckedChange = { en ->
                if (en) {
                    val fineOk = context.checkSelfPermission(android.Manifest.permission.ACCESS_FINE_LOCATION)
                    val coarseOk = context.checkSelfPermission(android.Manifest.permission.ACCESS_COARSE_LOCATION)
                    if (fineOk != android.content.pm.PackageManager.PERMISSION_GRANTED &&
                        coarseOk != android.content.pm.PackageManager.PERMISSION_GRANTED
                    ) {
                        locationPermissionLauncher.launch(
                            arrayOf(
                                android.Manifest.permission.ACCESS_FINE_LOCATION,
                                android.Manifest.permission.ACCESS_COARSE_LOCATION
                            )
                        )
                        return@SettingsSwitchItem
                    }
                }
                viewModel.toggleSensor("wifi", en)
                ensureServiceRunning(context, en)
            }
        )
        if (wifiEnabled && sensorPreview.wifiText.isNotBlank()) {
            Text(
                sensorPreview.wifiText,
                fontSize = 11.sp,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f),
                modifier = Modifier.padding(start = 4.dp, bottom = 4.dp)
            )
        }

        HorizontalDividerCompact()
        // ── 蓝牙感知 ──
        SettingsSwitchItem(
            label = "蓝牙感知",
            description = "获取已连接的蓝牙设备列表",
            checked = bluetoothEnabled,
            onCheckedChange = { en ->
                if (en && Build.VERSION.SDK_INT >= 31) {
                    val bc = context.checkSelfPermission(android.Manifest.permission.BLUETOOTH_CONNECT)
                    if (bc != android.content.pm.PackageManager.PERMISSION_GRANTED) {
                        bluetoothPermissionLauncher.launch(android.Manifest.permission.BLUETOOTH_CONNECT)
                        return@SettingsSwitchItem
                    }
                }
                viewModel.toggleSensor("bluetooth", en)
                ensureServiceRunning(context, en)
            }
        )
        if (bluetoothEnabled && sensorPreview.btText.isNotBlank()) {
            Text(
                sensorPreview.btText,
                fontSize = 11.sp,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f),
                modifier = Modifier.padding(start = 4.dp, bottom = 4.dp)
            )
        }

        HorizontalDividerCompact()
        // ── 锁屏状态感知 ──
        SettingsSwitchItem(
            label = "锁屏状态感知",
            description = "检测屏幕是否锁定",
            checked = screenStateEnabled,
            onCheckedChange = { en ->
                viewModel.toggleSensor("screen", en)
                ensureServiceRunning(context, en)
            }
        )
        if (screenStateEnabled && sensorPreview.screenText.isNotBlank()) {
            Text(
                sensorPreview.screenText,
                fontSize = 11.sp,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f),
                modifier = Modifier.padding(start = 4.dp, bottom = 4.dp)
            )
        }

        HorizontalDividerCompact()
        // ── 输入内容感知 ──
        SettingsSwitchItem(
            label = "输入内容感知",
            description = "收集键盘输入内容进行分析",
            checked = inputContentEnabled,
            onCheckedChange = { en ->
                if (en && !hasAccessibilityServiceEnabled(context)) {
                    showAccessibilityDialog = true
                } else {
                    viewModel.toggleSensor("inputContent", en)
                    ensureServiceRunning(context, en)
                }
            }
        )

        HorizontalDividerCompact()
        // ── Gadgetbridge 数据库路径 ──
        Text(
            "手环数据库路径",
            fontSize = 14.sp,
            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f)
        )
        Spacer(Modifier.height(4.dp))
        Text(
            dbFilePath,
            fontSize = 12.sp,
            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f),
            maxLines = 1,
            modifier = Modifier.padding(bottom = 4.dp)
        )
        OutlinedButton(
            onClick = { dbFilePickerLauncher.launch(arrayOf("*/*")) },
            modifier = Modifier.fillMaxWidth()
        ) {
            Text("选择数据库文件")
        }
        TextButton(
            onClick = { showBandKeyDialog = true },
            modifier = Modifier.padding(top = 2.dp)
        ) {
            Text(
                "如何获取手环 Auth Key？",
                fontSize = 12.sp,
                color = MaterialTheme.colorScheme.primary.copy(alpha = 0.7f)
            )
        }

        Spacer(Modifier.height(8.dp))
        // ── 采集间隔 ──
        Text(
            "采集间隔",
            fontSize = 14.sp,
            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f)
        )
        Spacer(Modifier.height(4.dp))
        Row(
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            listOf(15000L to "15秒", 30000L to "30秒", 60000L to "60秒").forEach { (ms, label) ->
                FilterChip(
                    selected = collectionInterval == ms.toInt(),
                    onClick = {
                        customIntervalSec = ""
                        viewModel.setCollectionInterval(ms.toInt())
                    },
                    label = { Text(label, fontSize = 13.sp) }
                )
            }
        }
        Spacer(Modifier.height(4.dp))
        OutlinedTextField(
            value = customIntervalSec,
            onValueChange = { v ->
                customIntervalSec = v
                val sec = v.toIntOrNull()
                if (sec != null && sec > 0) {
                    viewModel.setCollectionInterval(sec * 1000)
                }
            },
            label = { Text("自定义秒数") },
            placeholder = { Text("输入秒数（如 10）") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
            keyboardOptions = KeyboardOptions(
                keyboardType = KeyboardType.Number,
                imeAction = ImeAction.Done
            ),
            suffix = { Text("秒") }
        )

        Spacer(Modifier.height(8.dp))
        // ── 通知轮询间隔 ──
        Text(
            "通知轮询间隔",
            fontSize = 14.sp,
            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f)
        )
        Spacer(Modifier.height(4.dp))
        Row(
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            listOf(5000L to "5秒", 15000L to "15秒", 30000L to "30秒").forEach { (ms, label) ->
                FilterChip(
                    selected = notifyInterval == ms.toInt(),
                    onClick = { viewModel.setNotifyInterval(ms.toInt()) },
                    label = { Text(label, fontSize = 13.sp) }
                )
            }
        }
    }

    // ── 权限引导弹窗 ──────────────────────────────────────────────

    // 使用情况访问权限
    if (showUsageStatsDialog) {
        AlertDialog(
            onDismissRequest = { showUsageStatsDialog = false },
            title = { Text("使用情况访问权限") },
            text = {
                Text(
                    "需要开启「使用情况访问」权限才能读取当前前台应用信息。" +
                            "请在系统设置中为「Axeuh 助手」开启此权限。"
                )
            },
            confirmButton = {
                Button(onClick = {
                    showUsageStatsDialog = false
                    val intent = Intent(android.provider.Settings.ACTION_USAGE_ACCESS_SETTINGS)
                    usageStatsSettingsLauncher.launch(intent)
                }) { Text("去设置") }
            },
            dismissButton = {
                TextButton(onClick = { showUsageStatsDialog = false }) { Text("取消") }
            }
        )
    }

    // 通知监听权限
    if (showNotificationListenerDialog) {
        AlertDialog(
            onDismissRequest = { showNotificationListenerDialog = false },
            title = { Text("通知监听权限") },
            text = {
                Text(
                    "需要开启「通知监听」权限才能读取系统通知内容。" +
                            "请在系统设置中为「Axeuh 助手」开启此权限。"
                )
            },
            confirmButton = {
                Button(onClick = {
                    showNotificationListenerDialog = false
                    val intent = Intent(android.provider.Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS)
                    notificationListenerLauncher.launch(intent)
                }) { Text("去设置") }
            },
            dismissButton = {
                TextButton(onClick = { showNotificationListenerDialog = false }) { Text("取消") }
            }
        )
    }

    // 无障碍服务权限
    if (showAccessibilityDialog) {
        AlertDialog(
            onDismissRequest = { showAccessibilityDialog = false },
            title = { Text("无障碍服务权限") },
            text = {
                Text(
                    "需要开启无障碍服务才能收集键盘输入内容。" +
                            "请在系统设置中为「Axeuh 助手」开启此权限。"
                )
            },
            confirmButton = {
                Button(onClick = {
                    showAccessibilityDialog = false
                    val intent = Intent(android.provider.Settings.ACTION_ACCESSIBILITY_SETTINGS)
                    accessibilitySettingsLauncher.launch(intent)
                }) { Text("去设置") }
            },
            dismissButton = {
                TextButton(onClick = { showAccessibilityDialog = false }) { Text("取消") }
            }
        )
    }

    // 存储权限
    if (showStoragePermissionDialog) {
        AlertDialog(
            onDismissRequest = { showStoragePermissionDialog = false },
            title = { Text("存储权限") },
            text = {
                Text(
                    "需要授予存储权限才能直接读取 Gadgetbridge 手环数据库。" +
                            "请在系统设置中为「Axeuh 助手」开启「所有文件访问权限」。"
                )
            },
            confirmButton = {
                Button(onClick = {
                    showStoragePermissionDialog = false
                    if (Build.VERSION.SDK_INT >= 30) {
                        manageStorageLauncher.launch(
                            Intent(android.provider.Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION).apply {
                                data = android.net.Uri.parse("package:${context.packageName}")
                            }
                        )
                    } else {
                        readStorageLauncher.launch(android.Manifest.permission.READ_EXTERNAL_STORAGE)
                    }
                }) { Text("去设置") }
            },
            dismissButton = {
                TextButton(onClick = { showStoragePermissionDialog = false }) { Text("取消") }
            }
        )
    }

    // 手环设置指南
    if (showBandKeyDialog) {
        AlertDialog(
            onDismissRequest = { showBandKeyDialog = false },
            title = { Text("手环数据采集设置") },
            text = {
                Column(modifier = Modifier.padding(vertical = 4.dp)) {
                    Text(
                        "首次使用按以下步骤操作：",
                        fontWeight = androidx.compose.ui.text.font.FontWeight.Bold,
                        fontSize = 14.sp
                    )
                    Spacer(Modifier.height(8.dp))
                    Text("1. Gadgetbridge 设置 -> 自动化 -> 自动导出数据库 -> 开启", fontSize = 13.sp)
                    Text("2. 导出间隔设为一小时（不改也行）", fontSize = 13.sp)
                    Text("3. 点击「立即运行自动导出」", fontSize = 13.sp)
                    Spacer(Modifier.height(4.dp))
                    Text("4. 返回 Axeuh App -> 选择数据库文件", fontSize = 13.sp)
                    Text("5. 选中 Gadgetbridge 导出的 .db 文件", fontSize = 13.sp)
                    Text("6. 下方健康数据区域验证是否能读到数据", fontSize = 13.sp)
                    Spacer(Modifier.height(8.dp))
                    Text(
                        "确认数据可读后，开启蓝牙 Intent API：",
                        fontWeight = androidx.compose.ui.text.font.FontWeight.Bold,
                        fontSize = 13.sp
                    )
                    Spacer(Modifier.height(4.dp))
                    Text("7. Gadgetbridge 设置 -> 开发者选项", fontSize = 13.sp)
                    Text("8. 意图接口 -> 蓝牙 Intent API -> 开启", fontSize = 13.sp)
                    Text("9. 允许数据库导出 -> 开启", fontSize = 13.sp)
                    Text("10. 数据库导出时广播 -> 开启", fontSize = 13.sp)
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
                        fontWeight = androidx.compose.ui.text.font.FontWeight.Bold,
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
                        fontWeight = androidx.compose.ui.text.font.FontWeight.Bold,
                        fontSize = 12.sp,
                        color = MaterialTheme.colorScheme.error.copy(alpha = 0.8f)
                    )
                    Spacer(Modifier.height(2.dp))
                    Text("设置 -> 应用管理 -> 小米运动健康 -> 关闭自启动、禁止后台、禁止获取设备列表", fontSize = 12.sp)
                    Spacer(Modifier.height(4.dp))
                    Text(
                        "详细说明见 app/docs/band_data_collection_guide.md",
                        fontSize = 11.sp,
                        color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.4f)
                    )
                }
            },
            confirmButton = {
                Button(onClick = { showBandKeyDialog = false }) { Text("知道了") }
            }
        )
    }
}

// ─── 权限检查（与 SettingsActivity 保持一致）─────────────────────────

/** 检查 Usage Stats 权限是否已开启 */
private fun hasUsageStatsPermission(context: Context): Boolean {
    return try {
        val appOps = context.getSystemService(Context.APP_OPS_SERVICE) as? AppOpsManager ?: return false
        val mode = appOps.checkOpNoThrow(
            AppOpsManager.OPSTR_GET_USAGE_STATS,
            Process.myUid(),
            context.packageName
        )
        if (mode == AppOpsManager.MODE_ALLOWED) return true

        val usm = context.getSystemService(Context.USAGE_STATS_SERVICE) as? UsageStatsManager ?: return false
        val now = System.currentTimeMillis()
        val stats = usm.queryUsageStats(UsageStatsManager.INTERVAL_DAILY, now - 86400000, now)
        stats != null && stats.isNotEmpty()
    } catch (_: Exception) {
        false
    }
}

/** 检查 Notification Listener 权限是否已开启 */
private fun hasNotificationListenerPermission(context: Context): Boolean {
    val cn = android.provider.Settings.Secure.getString(
        context.contentResolver, "enabled_notification_listeners"
    ) ?: return false
    return cn.contains("com.axeuh.health.monitor.service.NotificationListenerService")
}

/** 检查存储权限（API 30+ 用 MANAGE_EXTERNAL_STORAGE，旧版用 READ_EXTERNAL_STORAGE） */
private fun hasStoragePermission(context: Context): Boolean {
    return if (Build.VERSION.SDK_INT >= 30) {
        android.os.Environment.isExternalStorageManager()
    } else {
        context.checkSelfPermission(android.Manifest.permission.READ_EXTERNAL_STORAGE) == 0
    }
}

/** 检查无障碍服务是否已开启 */
private fun hasAccessibilityServiceEnabled(context: Context): Boolean {
    val cn = android.provider.Settings.Secure.getString(
        context.contentResolver,
        android.provider.Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES
    ) ?: return false
    return cn.contains(".service.AxeuhAccessibilityService")
}

/** 确保 DataCollectorService 在开启传感器时正在运行 */
private fun ensureServiceRunning(context: Context, enabled: Boolean) {
    if (!enabled) return
    try {
        val i = Intent(context, DataCollectorService::class.java)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            context.startForegroundService(i)
        } else {
            context.startService(i)
        }
    } catch (_: Exception) { }
}
