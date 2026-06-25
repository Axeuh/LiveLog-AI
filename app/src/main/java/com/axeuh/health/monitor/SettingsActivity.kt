@file:SuppressLint("SetTextI18n")

package com.axeuh.health.monitor

import android.annotation.SuppressLint
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.util.Log
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.ViewModelProvider
import kotlinx.coroutines.launch
import com.axeuh.health.monitor.network.AppHttpClient
import com.axeuh.health.monitor.service.state.SensorStateHolder
import com.axeuh.health.monitor.ui.LogCache
import com.axeuh.health.monitor.ui.settings.*

/**
 * 设置页面 -- 使用提取的 Section Composables。
 *
 * Activity 负责:
 * - 生命周期管理
 * - 创建 AppHttpClient / SensorStateHolder / SettingsViewModel
 * - 权限 launcher 声明（需要 Activity Context）
 *
 * UI 部分由各 Section Composable 管理:
 * - LoginSection     → 账号与登录
 * - SensorControls   → 数据采集（11 个传感器开关 + 间隔 + 预览）
 * - AiSettingsSection → AI 模型选择 + 声纹管理
 * - OtaSection       → OTA 更新
 * - PermissionDialogs → 权限引导弹窗
 *
 * 系统设置（设备信息、服务器地址、同步）和服务日志仍保留 inline。
 */
class SettingsActivity : ComponentActivity() {

    companion object {
        const val KEY_SERVER_URL = "server_url"
        private const val PREFS_NAME = "axeuh_prefs"
        private const val KEY_TOKEN = "auth_token"
        private const val KEY_USERNAME = "auth_username"
    }

    /** Android 13+ 通知权限请求 */
    private val notificationPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        Log.i("Settings", "通知权限: ${if (granted) "已授予" else "已拒绝"}")
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Android 13+ 申请通知权限（前台服务通知 + 通知轮询需要）
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS)
                != PackageManager.PERMISSION_GRANTED
            ) {
                notificationPermissionLauncher.launch(android.Manifest.permission.POST_NOTIFICATIONS)
            }
        }

        // 创建依赖: 统一网络层 + 传感器状态 + ViewModel
        val httpClient = AppHttpClient(this)
        val sensorStateHolder = SensorStateHolder()
        val viewModel = ViewModelProvider(
            this,
            SettingsViewModel.Factory(this, httpClient, sensorStateHolder)
        ).get(SettingsViewModel::class.java)

        setContent {
            MaterialTheme(colorScheme = lightColorScheme()) {
                SettingsScreen(
                    onBack = { finish() },
                    viewModel = viewModel
                )
            }
        }
    }
}

// ─── SettingsScreen ─────────────────────────────────────────────────

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(
    onBack: () -> Unit,
    viewModel: SettingsViewModel
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val snackbarHostState = remember { SnackbarHostState() }

    // 收集 ViewModel 中需要的状态
    val uploadEnabled by viewModel.uploadEnabled.collectAsState()
    val serverUrlTextState by viewModel.serverUrlText.collectAsState()
    val syncStatusText by viewModel.syncStatusText.collectAsState()

    // ── Permission Launchers（需要 Activity Context，不能移动到 ViewModel）──
    val usageStatsSettingsLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { }
    val notificationListenerLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { }
    val audioPermissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { }
    val locationPermissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { }
    val notificationPostPermissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { }
    val accessibilitySettingsLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { }
    val dbFilePickerLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.OpenDocument()
    ) { }
    val manageStorageLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { }
    val readStorageLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { }
    val bluetoothPermissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { }

    // ── 传感器健康检查 ──
    // 如果 uploadEnabled 为 false，所有传感器开关应显示禁用状态
    // 查看 SensorControls 处理 isUploadEnabled 检查

    Scaffold(
        snackbarHost = { SnackbarHost(snackbarHostState) },
        topBar = {
            TopAppBar(
                title = { Text("设置") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(
                            Icons.AutoMirrored.Filled.ArrowBack,
                            contentDescription = "返回"
                        )
                    }
                }
            )
        }
    ) { paddingValues ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
                .padding(horizontal = 16.dp)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Spacer(Modifier.height(4.dp))

            // ── 1. 账号与登录 ─────────────────────────────────────
            LoginSection(viewModel = viewModel, snackbarHostState = snackbarHostState)

            // ── 2. 数据采集 ───────────────────────────────────────
            SensorControls(viewModel = viewModel)

            // ── 3. AI 设置 ────────────────────────────────────────
            AiSettingsSection(viewModel = viewModel)

            // ── 4. 系统 ───────────────────────────────────────────
            SettingsGroup(title = "系统") {
                // 设备信息
                Text(
                    "设备信息",
                    fontSize = 15.sp,
                    fontWeight = FontWeight.Medium
                )
                Spacer(Modifier.height(4.dp))
                SettingsInfoItem("品牌", Build.BRAND)
                SettingsInfoItem("型号", Build.MODEL)
                SettingsInfoItem("Android 版本", Build.VERSION.RELEASE)

                HorizontalDividerCompact()

                // 服务器地址
                var localServerUrl by remember { mutableStateOf(serverUrlTextState) }
                Text(
                    "服务器地址",
                    fontSize = 15.sp,
                    fontWeight = FontWeight.Medium
                )
                Spacer(Modifier.height(4.dp))
                OutlinedTextField(
                    value = localServerUrl,
                    onValueChange = { localServerUrl = it },
                    label = { Text("服务器地址") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                    keyboardOptions = KeyboardOptions(imeAction = ImeAction.Done),
                    keyboardActions = KeyboardActions(
                        onDone = { viewModel.saveServerUrl(localServerUrl) }
                    )
                )
                Spacer(Modifier.height(4.dp))
                Button(
                    onClick = {
                        viewModel.saveServerUrl(localServerUrl)
                        scope.launch { snackbarHostState.showSnackbar("服务器地址已保存") }
                    },
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text("保存")
                }

                HorizontalDividerCompact()

                // 立即同步
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text(
                            "立即同步数据",
                            fontSize = 15.sp,
                            fontWeight = FontWeight.Medium
                        )
                        if (syncStatusText.isNotEmpty()) {
                            Spacer(Modifier.height(2.dp))
                            Text(
                                syncStatusText,
                                fontSize = 12.sp,
                                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f)
                            )
                        }
                    }
                    Button(onClick = { viewModel.syncNow() }) {
                        Text("同步")
                    }
                }
            }

            // ── 5. OTA 更新 ─────────────────────────────────────────
            SettingsGroup(title = "系统更新") {
                OtaSection(viewModel = viewModel)
            }

            // ── 6. 服务日志 ─────────────────────────────────────────
            SettingsGroup(title = "服务日志") {
                val logEntries by LogCache.logFlow.collectAsState()
                val logScrollState = remember { androidx.compose.foundation.ScrollState(0) }
                val dateFormat = remember { java.text.SimpleDateFormat("HH:mm:ss", java.util.Locale.getDefault()) }
                val logText = remember(logEntries) {
                    logEntries.takeLast(200).joinToString("\n") { entry ->
                        "${dateFormat.format(java.util.Date(entry.epochMs))} ${entry.tag}: ${entry.message}"
                    }
                }
                if (logText.isNotEmpty()) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.End
                    ) {
                        TextButton(onClick = {
                            try {
                                val cm = context.getSystemService(Context.CLIPBOARD_SERVICE)
                                        as android.content.ClipboardManager
                                cm.setPrimaryClip(
                                    android.content.ClipData.newPlainText("log", logText)
                                )
                            } catch (_: Exception) { }
                        }) {
                            Text("复制日志", fontSize = 12.sp)
                        }
                    }
                    Box(modifier = Modifier
                        .height(200.dp)
                        .verticalScroll(logScrollState)
                    ) {
                        androidx.compose.foundation.text.selection.SelectionContainer {
                            Text(
                                text = logText,
                                fontSize = 9.sp,
                                fontFamily = FontFamily.Monospace,
                                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f),
                                lineHeight = 13.sp
                            )
                        }
                    }
                } else {
                    Text(
                        "暂无日志（采集服务可能未运行）",
                        fontSize = 12.sp,
                        color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.4f)
                    )
                }
            }

            Spacer(Modifier.height(24.dp))
        }
    }

    // ── 权限引导弹窗 ─────────────────────────────────────────────
    PermissionDialogs(viewModel = viewModel)
}

// ─── 通用 Composable 函数（被 Section 文件 import）─────────────────

/**
 * 设置分组卡片 -- 标题 + 内容
 */
@Composable
fun SettingsGroup(
    title: String,
    content: @Composable ColumnScope.() -> Unit
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.3f)
        )
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(
                text = title,
                fontSize = 17.sp,
                fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.primary
            )
            Spacer(Modifier.height(12.dp))
            content()
        }
    }
}

/**
 * 设置开关项 -- 带 Switch 的配置行
 */
@Composable
fun SettingsSwitchItem(
    label: String,
    description: String,
    checked: Boolean,
    onCheckedChange: (Boolean) -> Unit
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = label,
                fontSize = 15.sp,
                color = MaterialTheme.colorScheme.onSurface
            )
            Spacer(Modifier.height(1.dp))
            Text(
                text = description,
                fontSize = 12.sp,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.45f)
            )
        }
        Switch(
            checked = checked,
            onCheckedChange = onCheckedChange,
            colors = SwitchDefaults.colors()
        )
    }
}

/**
 * 分组内紧凑分隔线
 */
@Composable
fun HorizontalDividerCompact() {
    HorizontalDivider(
        modifier = Modifier.padding(vertical = 2.dp),
        color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.08f),
        thickness = 0.5.dp
    )
}

/**
 * 设置键值信息项
 */
@Composable
fun SettingsInfoItem(key: String, value: String) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 2.dp),
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Text(
            key,
            fontSize = 13.sp,
            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f)
        )
        Text(
            value,
            fontSize = 13.sp,
            fontWeight = FontWeight.Medium
        )
    }
}
