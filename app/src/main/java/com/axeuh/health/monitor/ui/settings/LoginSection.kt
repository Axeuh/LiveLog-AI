package com.axeuh.health.monitor.ui.settings

import android.content.Context
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import com.axeuh.health.monitor.network.AppHttpClient

/**
 * LoginSection -- 账号与登录区域
 *
 * 从 SettingsActivity 中提取的登录 composable。
 * 使用 SettingsViewModel 的 StateFlows 读取登录状态，
 * 输入字段使用本地状态管理。
 *
 * 包含:
 * - 服务器地址显示
 * - 账号/密码输入
 * - 登录按钮（带 loading 状态）
 * - 已登录账号信息显示
 * - 连接状态显示
 * - 退出登录按钮
 * - 登录错误提示
 */
@Composable
fun LoginSection(
    viewModel: SettingsViewModel,
    snackbarHostState: SnackbarHostState? = null
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val httpClient = remember { AppHttpClient(context.applicationContext) }
    val prefs = context.getSharedPreferences(
        SettingsViewModel.PREFS_NAME, Context.MODE_PRIVATE
    )

    // 从 ViewModel StateFlows 读取登录状态
    val serverUrl by viewModel.serverUrl.collectAsState()
    val isLoggedIn by viewModel.isLoggedIn.collectAsState()
    val loginStatus by viewModel.loginStatus.collectAsState()
    val savedUsername by viewModel.savedUsername.collectAsState()
    val loginError by viewModel.loginError.collectAsState()

    // 输入字段使用本地状态（ViewModel 未暴露 setter）
    var username by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    // 本地登录状态，用于同步 ViewModel
    var localLoginStatus by remember { mutableStateOf(loginStatus) }
    var localLoginError by remember { mutableStateOf(loginError) }

    // 服务器地址显示
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(
            "服务器: ",
            fontSize = 14.sp,
            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f)
        )
        Text(
            serverUrl,
            fontSize = 14.sp,
            fontWeight = FontWeight.Medium
        )
    }

    HorizontalDivider(
        modifier = Modifier.padding(vertical = 2.dp),
        color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.08f),
        thickness = 0.5.dp
    )

    if (!isLoggedIn) {
        // ── 未登录: 输入框 + 登录按钮 ──

        // Username field
        OutlinedTextField(
            value = username,
            onValueChange = { username = it; localLoginError = "" },
            label = { Text("账号") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
            keyboardOptions = KeyboardOptions(imeAction = ImeAction.Next)
        )
        Spacer(Modifier.height(8.dp))

        // Password field
        OutlinedTextField(
            value = password,
            onValueChange = { password = it; localLoginError = "" },
            label = { Text("密码") },
            singleLine = true,
            visualTransformation = PasswordVisualTransformation(),
            modifier = Modifier.fillMaxWidth(),
            keyboardOptions = KeyboardOptions(
                keyboardType = KeyboardType.Password,
                imeAction = ImeAction.Done
            ),
            keyboardActions = KeyboardActions(
                    onDone = {
                        if (username.isNotBlank() && password.isNotBlank()) {
                            scope.launch {
                                performLogin(
                                    httpClient = httpClient,
                                    serverUrl = serverUrl,
                                    username = username,
                                    password = password,
                                    prefs = prefs,
                                    appContext = context.applicationContext,
                                    onStart = {
                                        localLoginStatus = "登录中..."
                                        localLoginError = ""
                                    },
                                    onSuccess = { user ->
                                        localLoginStatus = "已连接"
                                        scope.launch {
                                            snackbarHostState?.showSnackbar("登录成功")
                                        }
                                    },
                                    onError = { msg ->
                                        localLoginError = msg
                                        localLoginStatus = "未连接"
                                    }
                                )
                            }
                        }
                    }
            )
        )
        Spacer(Modifier.height(12.dp))

        // Login button
        Button(
            onClick = {
                if (username.isBlank() || password.isBlank()) {
                    localLoginError = "请输入账号和密码"
                    return@Button
                }
                scope.launch {
                    performLogin(
                        httpClient = httpClient,
                        serverUrl = serverUrl,
                        username = username,
                        password = password,
                        prefs = prefs,
                        appContext = context.applicationContext,
                        onStart = {
                            localLoginStatus = "登录中..."
                            localLoginError = ""
                        },
                        onSuccess = { user ->
                            localLoginStatus = "已连接"
                            scope.launch {
                                snackbarHostState?.showSnackbar("登录成功")
                            }
                        },
                        onError = { msg ->
                            localLoginError = msg
                            localLoginStatus = "未连接"
                        }
                    )
                }
            },
            modifier = Modifier.fillMaxWidth(),
            enabled = localLoginStatus != "登录中..."
        ) {
            if (localLoginStatus == "登录中...") {
                CircularProgressIndicator(
                    modifier = Modifier.size(20.dp),
                    strokeWidth = 2.dp,
                    color = MaterialTheme.colorScheme.onPrimary
                )
                Spacer(Modifier.width(8.dp))
            }
            Text("登录")
        }
    } else {
        // ── 已登录: 账号信息 ──
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                "账号: ",
                fontSize = 14.sp,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f)
            )
            Text(
                savedUsername,
                fontSize = 14.sp,
                fontWeight = FontWeight.Medium
            )
        }
    }

    // Error message
    val displayError = if (isLoggedIn) loginError else localLoginError
    if (displayError.isNotEmpty()) {
        Spacer(Modifier.height(4.dp))
        Text(
            text = displayError,
            fontSize = 13.sp,
            color = MaterialTheme.colorScheme.error
        )
    }

    // Connection status
    Spacer(Modifier.height(8.dp))
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(
            "状态: ",
            fontSize = 14.sp,
            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f)
        )
        Text(
            text = loginStatus,
            fontSize = 14.sp,
            fontWeight = FontWeight.Medium,
            color = if (isLoggedIn) MaterialTheme.colorScheme.primary
            else MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f)
        )
    }

    // Logout button
    if (isLoggedIn) {
        Spacer(Modifier.height(8.dp))
        TextButton(
            onClick = {
                viewModel.logout()
                username = ""
                password = ""
                localLoginStatus = "未连接"
                localLoginError = ""
                scope.launch {
                    snackbarHostState?.showSnackbar("已退出登录")
                }
            },
            modifier = Modifier.fillMaxWidth()
        ) {
            Text("退出登录", color = MaterialTheme.colorScheme.error)
        }
    }
}

/**
 * 执行登录并持久化 token
 *
 * POST /login 获取 token，成功后写入 SharedPreferences，
 * 并将 token 保存到 AppHttpClient 以供后续请求使用。
 */
private suspend fun performLogin(
    httpClient: AppHttpClient,
    serverUrl: String,
    username: String,
    password: String,
    prefs: android.content.SharedPreferences,
    appContext: android.content.Context,
    onStart: () -> Unit,
    onSuccess: (String) -> Unit,
    onError: (String) -> Unit
) {
    onStart()
    try {
        // 重置 401 标志，允许后续重认证
        AppHttpClient.resetAuthFailureFlag()

        val token = performLoginRequest(httpClient, serverUrl, username, password)
        if (token != null) {
            prefs.edit()
                .putString(SettingsViewModel.KEY_TOKEN, token)
                .putString(SettingsViewModel.KEY_USERNAME, username)
                .apply()
            // 保存密码到加密 prefs，供 tryReAuth() 自动重登录使用
            encryptedPrefs(appContext).edit()
                .putString(SettingsViewModel.KEY_PASSWORD, password)
                .apply()
            withContext(Dispatchers.Main) {
                onSuccess(username)
            }
        } else {
            withContext(Dispatchers.Main) {
                onError("账号或密码错误")
            }
        }
    } catch (e: Exception) {
        withContext(Dispatchers.Main) {
            onError("网络连接失败: ${e.message}")
        }
    }
}

/**
 * 加密 SharedPreferences — 与 SettingsViewModel / AppHttpClient 中相同，
 * 用于安全保存密码，供 401 自动重登录使用。
 */
private fun encryptedPrefs(context: android.content.Context): android.content.SharedPreferences {
    val masterKey = MasterKey.Builder(context)
        .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
        .build()
    return EncryptedSharedPreferences.create(
        context,
        "axeuh_secure_prefs",
        masterKey,
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
    )
}

/**
 * 登录请求 -- POST /login
 *
 * 使用 AppHttpClient (OkHttp + trust-all SSL)。
 */
private suspend fun performLoginRequest(
    httpClient: AppHttpClient,
    serverUrl: String,
    username: String,
    password: String
): String? = withContext(Dispatchers.IO) {
    try {
        val jsonBody = JSONObject().apply {
            put("username", username)
            put("password", password)
        }
        val response = httpClient.post("$serverUrl/login", jsonBody.toString())
        val json = JSONObject(response)
        if (json.optBoolean("success", false) && !json.isNull("token")) {
            json.getString("token")
        } else {
            null
        }
    } catch (_: Exception) {
        null
    }
}
