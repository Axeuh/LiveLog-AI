package com.axeuh.health.monitor.ui.settings

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import com.axeuh.health.monitor.HorizontalDividerCompact
import com.axeuh.health.monitor.SettingsGroup
import com.axeuh.health.monitor.ui.VoiceprintPanel

/**
 * AI 设置区域 Composable
 *
 * 从 SettingsActivity 中提取的 AI 设置部分，包含:
 * - 模型选择下拉菜单（按供应商分组）
 * - 声纹管理按钮（触发 VoiceprintPanel 弹窗）
 *
 * @param viewModel SettingsViewModel 实例，提供 AI 设置的状态和操作方法
 */
@Composable
fun AiSettingsSection(viewModel: SettingsViewModel) {
    // 从 ViewModel 收集状态
    val providers by viewModel.providers.collectAsState()
    val currentModelName by viewModel.currentModelName.collectAsState()
    val currentProviderName by viewModel.currentProviderName.collectAsState()
    val modelLoading by viewModel.modelLoading.collectAsState()
    val showVoiceprintPanel by viewModel.showVoiceprintPanel.collectAsState()
    val serverUrl by viewModel.serverUrl.collectAsState()

    SettingsGroup(title = "AI 设置") {
        // 模型选择标题
        Text(
            "模型选择",
            fontSize = 15.sp,
            fontWeight = FontWeight.Medium
        )
        Spacer(Modifier.height(4.dp))

        // 模型加载状态 / 选择下拉菜单 / 空状态
        if (modelLoading) {
            // 加载中指示器
            Row(verticalAlignment = Alignment.CenterVertically) {
                CircularProgressIndicator(
                    modifier = Modifier.size(16.dp),
                    strokeWidth = 2.dp
                )
                Spacer(Modifier.width(8.dp))
                Text(
                    "加载模型列表...",
                    fontSize = 13.sp,
                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f)
                )
            }
        } else if (providers.isNotEmpty()) {
            // 模型选择下拉菜单
            var expanded by remember { mutableStateOf(false) }
            val displayText = if (currentModelName.isNotEmpty()) {
                "$currentProviderName: $currentModelName"
            } else {
                "未选择"
            }

            Box {
                OutlinedButton(
                    onClick = { expanded = true },
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text(displayText, modifier = Modifier.weight(1f))
                    Text(" ▼ ", fontSize = 10.sp)
                }
                DropdownMenu(
                    expanded = expanded,
                    onDismissRequest = { expanded = false }
                ) {
                    providers.forEach { provider ->
                        if (provider.models.isNotEmpty()) {
                            // 供应商名称（不可点击，仅作分组标签）
                            DropdownMenuItem(
                                text = {
                                    Text(
                                        provider.name,
                                        fontWeight = FontWeight.Bold,
                                        fontSize = 13.sp
                                    )
                                },
                                onClick = { },
                                enabled = false
                            )
                            // 该供应商下的模型列表
                            provider.models.forEach { model ->
                                DropdownMenuItem(
                                    text = { Text("  ${model.name}", fontSize = 13.sp) },
                                    onClick = {
                                        expanded = false
                                        viewModel.selectModel(provider.id, model.id)
                                    }
                                )
                            }
                        }
                    }
                }
            }
        } else {
            // 无可用模型
            Text(
                "暂无可用模型",
                fontSize = 13.sp,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f)
            )
        }

        HorizontalDividerCompact()

        // 声纹管理按钮
        Button(
            onClick = { viewModel.showVoiceprintPanel() },
            modifier = Modifier.fillMaxWidth()
        ) {
            Text("声纹管理")
        }
    }

    // 声纹管理面板弹窗
    if (showVoiceprintPanel) {
        Dialog(onDismissRequest = { viewModel.dismissVoiceprintPanel() }) {
            VoiceprintPanel(
                onClose = { viewModel.dismissVoiceprintPanel() },
                serverUrl = serverUrl
            )
        }
    }
}
