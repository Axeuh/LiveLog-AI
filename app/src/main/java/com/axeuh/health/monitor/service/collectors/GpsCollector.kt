package com.axeuh.health.monitor.service.collectors

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.location.LocationManager
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

/**
 * GPS 位置采集器 —— 从 [com.axeuh.health.monitor.service.DataCollectorService]
 * 提取的 GPS 定位采集。
 *
 * 使用 [LocationManager] 获取最后已知位置（latitude/longitude），
 * 以 `"latitude,longitude"` 字符串格式存储到 [SensorStateHolder]。
 * 与原始 DataCollectorService 的 JSON 字段名（"gps"）完全一致。
 *
 * 采集间隔：5 分钟（慢采集周期），通过协程循环实现。
 * 遵循 [BaseCollector] 生命周期：start() 启动循环，stop() 取消循环。
 *
 * ## 权限
 * 需要 `android.permission.ACCESS_FINE_LOCATION`。无权限时记录警告并跳过。
 */
class GpsCollector(
    context: Context,
    stateHolder: SensorStateHolder,
    httpClient: AppHttpClient
) : BaseCollector(context, stateHolder, httpClient) {

    companion object {
        /** 采集间隔：5 分钟 */
        private const val COLLECT_INTERVAL_MS = 300_000L
    }

    // ── 系统服务（by lazy 避免构造时获取，便于测试） ──

    private val locationManager: LocationManager? by lazy {
        context.getSystemService(Context.LOCATION_SERVICE) as? LocationManager
    }

    // ── 协程生命周期 ──

    private var scope: CoroutineScope? = null

    override val isEnabled: Boolean
        get() = DataCollectorService.isGpsEnabled(context)

    /**
     * 启动 GPS 采集循环。
     * 每 [COLLECT_INTERVAL_MS]（5 分钟）执行一次 [collectLocation]。
     * 重复调用安全（不会创建多个协程作用域）。
     */
    override fun start() {
        if (scope != null) return
        scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
        scope!!.launch {
            Timber.i("GPS 采集已启动（每${COLLECT_INTERVAL_MS / 1000}s）")
            while (isActive) {
                try {
                    collectLocation()
                } catch (e: Exception) {
                    Timber.w("GPS 采集异常: ${e.message}")
                }
                delay(COLLECT_INTERVAL_MS)
            }
        }
    }

    /**
     * 停止 GPS 采集循环。
     * 重复调用安全（cancel 空作用域不抛异常）。
     */
    override fun stop() {
        scope?.cancel()
        scope = null
        Timber.i("GPS 采集已停止")
    }

    // ======================== GPS 位置采集 ========================

    /**
     * 单次 GPS 位置采集。
     *
     * `internal`（包可见）以便测试直接调用。
     *
     * 采集流程：
     * 1. 检查 [LocationManager] 是否可用
     * 2. 检查 [Manifest.permission.ACCESS_FINE_LOCATION] 权限
     * 3. 依次尝试 PASSIVE → GPS → NETWORK provider 的最后已知位置
     * 4. 将结果以 `"latitude,longitude"` 格式更新到 [SensorStateHolder]
     *
     * 与原始 DataCollectorService 的 GPS 缓存读取逻辑一致：
     * - 格式：`"${loc.latitude},${loc.longitude}"`
     * - 优先顺序：PASSIVE > GPS > NETWORK
     * - 无权限时清除旧值
     */
    internal suspend fun collectLocation() {
        val lm = locationManager ?: run {
            Timber.w("LocationManager 不可用，跳过定位")
            return
        }

        // 检查 ACCESS_FINE_LOCATION 权限
        if (context.checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION)
            != PackageManager.PERMISSION_GRANTED
        ) {
            Timber.w("GPS 无 ACCESS_FINE_LOCATION 权限")
            stateHolder.updateLastGps("")
            return
        }

        // 依次尝试各 provider 的缓存位置（与原始 DataCollectorService 顺序一致）
        val providers = listOf(
            LocationManager.PASSIVE_PROVIDER,
            LocationManager.GPS_PROVIDER,
            LocationManager.NETWORK_PROVIDER
        )

        for (provider in providers) {
            try {
                val loc = lm.getLastKnownLocation(provider)
                if (loc != null) {
                    if (loc.accuracy > 1000f) {
                        Timber.w("GPS($provider): 精度=${loc.accuracy}m 超出合理范围(>1000m)，跳过")
                        continue
                    }
                    val gpsStr = "${loc.latitude},${loc.longitude}"
                    stateHolder.updateLastGps(gpsStr)
                    Timber.i("GPS($provider): $gpsStr 精度=${loc.accuracy}m")
                    return  // 找到位置即返回
                }
            } catch (_: SecurityException) {
                Timber.w("GPS 无权限访问 provider: $provider")
            } catch (_: Exception) {
                // 单个 provider 异常不干扰后续尝试
                Timber.w("GPS provider $provider 异常，尝试下一个")
            }
        }

        // 所有 provider 均无缓存位置
        Timber.w("GPS: 所有 provider 均无可用位置")
    }
}
