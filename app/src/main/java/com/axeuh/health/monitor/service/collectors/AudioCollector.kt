package com.axeuh.health.monitor.service.collectors

import android.content.Context
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaCodec
import android.media.MediaCodecInfo
import android.media.MediaFormat
import android.media.MediaRecorder
import android.os.Handler
import android.os.Looper
import timber.log.Timber
import com.axeuh.health.monitor.network.AppHttpClient
import com.axeuh.health.monitor.service.state.SensorStateHolder
import kotlin.math.log10
import kotlin.math.sqrt
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.Request
import okhttp3.RequestBody.Companion.asRequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * 音频采集器 —— 从 [com.axeuh.health.monitor.service.DataCollectorService] 提取的
 * AudioRecord PCM 录音 + VAD 能量检测 + MediaCodec AAC 编码 + multipart 上传。
 *
 * ## 采集参数
 * - 采样率: 16000 Hz (SR)
 * - 帧大小: 480 samples (30ms @ 16kHz)
 * - VAD 阈值: RMS >= 8.0 视为有效语音
 * - 静音超时: 1500ms 连续静音结束说话段
 * - 最短说话: 500ms 以下丢弃
 *
 * ## 工作流程
 * ```
 * start() → AudioRecord.startRecording()
 *   → 录音线程音频循环 (audioCaptureLoop)
 *     → 每帧 VAD 能量检测 (computeRms)
 *     → 状态写回 SensorStateHolder (vadStatus, currentDbLevel)
 *     → VAD 检测到说话段 -> 收集到 PCM 缓冲区
 *     → 静音超时 / 满缓冲 -> 生成 WAV
 *   → sendToBackend() -> multipart POST 到 voice-session-multipart
 *   → 循环下一轮录音
 * ```
 *
 * ## 数据流
 * ```
 * AudioRecord PCM → audioCaptureLoop → WAV ByteArray
 *   → sendToBackend (OkHttp MultipartBody)
 *   → /api/screen/stt/voice-session-multipart
 *   → 失败 → saveToCache (本地 JSON + WAV)
 *   → 下次上传前 → uploadCachedData 按序重试
 * ```
 */
class AudioCollector(
    context: Context,
    stateHolder: SensorStateHolder,
    httpClient: AppHttpClient
) : BaseCollector(context, stateHolder, httpClient) {

    companion object {
        private const val TAG = "AudioCollector"

        /** 采样率 16kHz */
        const val SR = 16000

        /** 帧大小 30ms @ 16kHz */
        const val FRAME_SIZE = 480

        /** 每帧毫秒数 */
        const val FRAME_MS = 30

        /** VAD 音量阈值（RMS） */
        const val RMS_THRESHOLD = 8.0

        /** 连续静音多久（ms）结束说话段 */
        const val SILENCE_MS = 1500

        /** 最短说话长度（ms），低于此丢弃 */
        const val MIN_SPEECH_MS = 500

        private const val CACHE_DIR_NAME = "upload_cache"
    }

    // ── 录音状态 ──

    /** AudioRecord 实例（录音期间非空） */
    private var record: AudioRecord? = null

    /** WAV 字节数组（录音完成后填充，上传后清空） */
    private var audioBytes: ByteArray? = null

    /** 录音开始时间戳，用于 client_time */
    private var recordingStartMs: Long? = null

    // ── 生命周期 ──

    /** 是否启用音频采集（从 SharedPreferences 读取） */
    override val isEnabled: Boolean
        get() = context.getSharedPreferences("data_collector", Context.MODE_PRIVATE)
            .getBoolean("audio_enabled", false)

    /**
     * 启动音频采集。
     *
     * 如果音频已启用，立即创建 AudioRecord 并开始录音循环。
     * 如果音频已关闭，记录日志并跳过。
     */
    override fun start() {
        if (isEnabled) {
            Timber.i("音频采集已启动")
            startRecording()
        } else {
            Timber.i("音频采集已关闭，跳过启动")
        }
    }

    /**
     * 停止音频采集。
     *
     * 释放 AudioRecord 实例，清空缓存音频数据。
     * 调用 [start] 后可重新开始录音。
     */
    override fun stop() {
        Timber.i("音频采集已停止")
        try {
            record?.let { ar ->
                try {
                    if (ar.recordingState == AudioRecord.RECORDSTATE_RECORDING) {
                        ar.stop()
                    }
                } catch (_: Exception) {}
                ar.release()
            }
        } catch (_: Exception) {}
        record = null
        audioBytes = null
    }

    // ======================== 录音 ========================

    /**
     * 创建 AudioRecord 实例并启动录音线程。
     *
     * 1. 尝试 VOICE_RECOGNITION / CAMCORDER / MIC 三种音源
     * 2. 启动 [audioCaptureLoop] 在后台线程读取 PCM 数据
     * 3. 录音完成后调用 [sendToBackend]
     * 4. 如果仍启用，自动开始下一轮录音
     *
     * 线程名: DcRecord（与原始 DataCollectorService 一致）
     */
    private fun startRecording() {
        // 防止重复创建
        if (record != null && record!!.recordingState == AudioRecord.RECORDSTATE_RECORDING) {
            Timber.i("已有活跃录音实例，跳过")
            return
        }

        recordingStartMs = System.currentTimeMillis()
        try {
            val bufSize = AudioRecord.getMinBufferSize(
                SR, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT
            )
            if (bufSize <= 0) {
                Timber.w("系统不支持 16kHz 录音")
                return
            }

            // 遍历音源，优先 VOICE_RECOGNITION（绕过蓝牙 MIC）
            val sources = intArrayOf(
                MediaRecorder.AudioSource.VOICE_RECOGNITION,
                MediaRecorder.AudioSource.CAMCORDER,
                MediaRecorder.AudioSource.MIC,
            )
            var ar: AudioRecord? = null
            for (src in sources) {
                try {
                    val a = AudioRecord(
                        src, SR, AudioFormat.CHANNEL_IN_MONO,
                        AudioFormat.ENCODING_PCM_16BIT, bufSize * 4
                    )
                    if (a.state == AudioRecord.STATE_INITIALIZED) {
                        ar = a
                        Timber.i("音源=$src 初始化成功")
                        break
                    }
                    a.release()
                } catch (e: Exception) {
                    Timber.w("音源=$src 异常: ${e.message}")
                }
            }
            if (ar == null) {
                Timber.w("所有音源初始化失败")
                return
            }

            record = ar
            ar.startRecording()
            Timber.i("录音已启动")

            // ── 录音线程 ──
            Thread({
                try {
                    audioCaptureLoop(ar)
                } finally {
                    // 停止并释放 AudioRecord
                    try {
                        if (ar.recordingState == AudioRecord.RECORDSTATE_RECORDING) ar.stop()
                    } catch (_: Exception) {}
                    ar.release()
                    if (record === ar) record = null

                    // 上传音频
                    sendToBackend()

                    // 下一轮录音（循环）
                    if (isEnabled) {
                        Handler(Looper.getMainLooper()).post {
                            if (isEnabled) {
                                startRecording()
                            }
                        }
                    }
                }
            }, "DcRecord").start()
        } catch (e: Exception) {
            Timber.w("录音启动失败: ${e.message}")
            sendToBackend()
        }
    }

    // ======================== VAD 音频循环 ========================

    /**
     * PCM 音频采集循环。
     *
     * 从 [ar] 持续读取 480 采样帧，进行 VAD 能量检测：
     * - RMS >= [RMS_THRESHOLD] → speaking 状态，开始/继续说话段
     * - RMS < [RMS_THRESHOLD] → 启动静音计时器
     * - 连续静音超过 [SILENCE_MS] → 结束当前说话段
     * - 从未说过话 → idle 状态，继续监听
     *
     * 循环退出条件：
     * 1. 录满总周期时长（从 [loop_ms] 配置读取）
     * 2. VAD 检测到说话结束（静音超时）
     * 3. AudioRecord 状态异常
     *
     * 结束时将 PCM 数据转换为 WAV 写入 [audioBytes]。
     * 如果说话段短于 [MIN_SPEECH_MS]，丢弃数据（audioBytes=null）。
     */
    private fun audioCaptureLoop(ar: AudioRecord) {
        val prefs = context.getSharedPreferences("data_collector", Context.MODE_PRIVATE)
        val intervalMs = prefs.getLong("loop_ms", 30000L)
        val intervalSec = (intervalMs / 1000).toInt()
        val maxFrames = SR * intervalSec
        val pcmBuf = ShortArray(maxFrames)
        var pos = 0
        val frameBuf = ShortArray(FRAME_SIZE)

        // VAD 状态追踪
        var silenceStartMs: Long? = null   // 连续静音开始时间（相对 loopStartMs）
        var speechStartMs: Long? = null    // 当前说话段开始时间
        var hasEverSpoken = false          // 本轮是否说过话
        val loopStartMs = System.currentTimeMillis()

        // 初始状态：监听
        stateHolder.updateVadStatus("idle")

        while (pos < maxFrames) {
            if (ar.recordingState != AudioRecord.RECORDSTATE_RECORDING) {
                Timber.w("录音状态异常 state=${ar.recordingState}，立即退出")
                break
            }
            val n = ar.read(frameBuf, 0, FRAME_SIZE)
            if (n > 0) {
                System.arraycopy(frameBuf, 0, pcmBuf, pos, n.coerceAtMost(maxFrames - pos))
                pos += n

                // VAD: 计算 RMS 和 dB 电平
                val elapsedMs = System.currentTimeMillis() - loopStartMs
                val rms = computeRms(frameBuf, n)
                val dbLevel = if (rms > 0) {
                    (20.0 * log10(rms / 32768.0)).toFloat()
                } else {
                    -80f
                }
                stateHolder.updateDbLevel(dbLevel)

                if (rms >= RMS_THRESHOLD) {
                    // ── 有声音活动 ──
                    if (!hasEverSpoken) {
                        hasEverSpoken = true
                        speechStartMs = elapsedMs
                    }
                    stateHolder.updateVadStatus("speaking")
                    silenceStartMs = null
                } else {
                    // ── 静音帧 ──
                    if (hasEverSpoken) {
                        // 曾经说过话 → 检查静音超时
                        if (silenceStartMs == null) {
                            silenceStartMs = elapsedMs
                        } else if (elapsedMs - silenceStartMs >= SILENCE_MS) {
                            // 静音足够长 → 结束说话段
                            Timber.i("VAD: 静音超时 ${SILENCE_MS}ms，结束说话段")
                            stateHolder.updateVadStatus("idle")
                            break
                        }
                    } else {
                        // 从未说过话 → 继续监听
                        stateHolder.updateVadStatus("listening")
                    }
                }
            } else if (n < 0) {
                Timber.w("录音读取错误: $n")
                break
            }
        }

        // 计算实际说话时长
        val speechDurationMs = if (speechStartMs != null) {
            // 说话结束时间 = 静音开始时间（如果有静音）或当前时间（安静结束）
            val speechEndMs = silenceStartMs ?: (System.currentTimeMillis() - loopStartMs)
            speechEndMs - speechStartMs
        } else 0L

        // 有音频数据且满足最短说话长度
        if (pos > 0 && speechDurationMs >= MIN_SPEECH_MS) {
            val totalBytes = pos * 2
            val baos = java.io.ByteArrayOutputStream(44 + totalBytes)

            // 工具函数：写入 16-bit 小端整数
            fun w16(v: Int) {
                baos.write(v and 0xFF)
                baos.write(v shr 8 and 0xFF)
            }
            fun w32(v: Int) { w16(v); w16(v shr 16) }

            // WAV 头部
            baos.write("RIFF".toByteArray()); w32(36 + totalBytes)
            baos.write("WAVE".toByteArray())
            baos.write("fmt ".toByteArray()); w32(16)
            w16(1)      // PCM
            w16(1)      // mono
            w32(SR)     // sample rate
            w32(SR * 2) // byte rate
            w16(2)      // block align
            w16(16)     // bits per sample
            baos.write("data".toByteArray()); w32(totalBytes)

            // PCM 采样数据
            for (i in 0 until pos) w16(pcmBuf[i].toInt())

            audioBytes = baos.toByteArray()
            Timber.i("录音完成: ${audioBytes!!.size}B (${pos / SR}s, speech=${speechDurationMs}ms)")
        } else {
            Timber.i("录音未采集到有效语音 (pos=$pos, speechMs=$speechDurationMs)")
            audioBytes = null
        }
    }

    /**
     * 计算 PCM 帧的均方根 (RMS) 能量。
     *
     * @param frame 短整型 PCM 数据（16-bit）
     * @param count 有效采样数
     * @return RMS 值（0 ~ 32768）
     */
    internal fun computeRms(frame: ShortArray, count: Int): Double {
        if (count <= 0) return 0.0
        var sum = 0.0
        for (i in 0 until count) {
            val s = frame[i].toDouble()
            sum += s * s
        }
        return sqrt(sum / count)
    }

    // ======================== AAC 编码 ========================

    /**
     * PCM 16-bit 16kHz mono → AAC (ADTS) 编码。
     *
     * @param pcmBytes PCM 原始数据（16-bit 小端序）
     * @param sampleRate 采样率
     * @return AAC ADTS 字节数组，失败返回 null
     */
    internal fun encodePcmToAac(pcmBytes: ByteArray, sampleRate: Int): ByteArray? {
        try {
            val mime = "audio/mp4a-latm"
            val codec = MediaCodec.createEncoderByType(mime)
            val format = MediaFormat.createAudioFormat(mime, sampleRate, 1)
            format.setInteger(MediaFormat.KEY_BIT_RATE, 64000)  // 64kbps
            format.setInteger(
                MediaFormat.KEY_AAC_PROFILE,
                MediaCodecInfo.CodecProfileLevel.AACObjectLC
            )
            codec.configure(format, null, null, MediaCodec.CONFIGURE_FLAG_ENCODE)
            codec.start()

            val output = java.io.ByteArrayOutputStream()
            val bufferInfo = MediaCodec.BufferInfo()
            val timeoutUs = 10000L
            var inputOffset = 0
            val frameBytes = 2048  // 1024 samples * 2 bytes

            while (inputOffset < pcmBytes.size ||
                bufferInfo.flags and MediaCodec.BUFFER_FLAG_END_OF_STREAM == 0
            ) {
                // 喂入输入
                if (inputOffset < pcmBytes.size) {
                    val inIdx = codec.dequeueInputBuffer(timeoutUs)
                    if (inIdx >= 0) {
                        val inBuf = codec.getInputBuffer(inIdx)!!
                        inBuf.clear()
                        val chunk = minOf(frameBytes, pcmBytes.size - inputOffset)
                        inBuf.put(pcmBytes, inputOffset, chunk)
                        inputOffset += chunk
                        val pts = (inputOffset * 1000000L) / (sampleRate * 2)
                        val flags = if (inputOffset >= pcmBytes.size) {
                            MediaCodec.BUFFER_FLAG_END_OF_STREAM
                        } else 0
                        codec.queueInputBuffer(inIdx, 0, chunk, pts, flags)
                    }
                }

                // 收集输出
                val outIdx = codec.dequeueOutputBuffer(bufferInfo, timeoutUs)
                if (outIdx >= 0) {
                    if (bufferInfo.flags and MediaCodec.BUFFER_FLAG_CODEC_CONFIG == 0 &&
                        bufferInfo.size > 0
                    ) {
                        val outBuf = codec.getOutputBuffer(outIdx)!!
                        val frame = ByteArray(bufferInfo.size)
                        outBuf.get(frame)
                        outBuf.clear()
                        // 添加 ADTS 头部
                        val adts = createAdtsHeader(bufferInfo.size + 7, sampleRate)
                        output.write(adts)
                        output.write(frame)
                    }
                    codec.releaseOutputBuffer(outIdx, false)
                }
            }

            codec.stop()
            codec.release()
            val result = output.toByteArray()
            return if (result.isNotEmpty()) result else null
        } catch (e: Exception) {
            Timber.w(e, "AAC 编码失败")
            return null
        }
    }

    /**
     * 生成 AAC ADTS 头部（7 字节，无 CRC）。
     *
     * @param frameLength ADTS 帧总长度（含头部）
     * @param sampleRate 采样率
     * @return 7 字节 ADTS 头部
     */
    internal fun createAdtsHeader(frameLength: Int, sampleRate: Int): ByteArray {
        val srIdx = when (sampleRate) {
            96000 -> 0; 88200 -> 1; 64000 -> 2; 48000 -> 3
            44100 -> 4; 32000 -> 5; 24000 -> 6; 22050 -> 7
            16000 -> 8; 12000 -> 9; 11025 -> 10; 8000 -> 11
            else -> 4
        }
        val hdr = ByteArray(7)
        hdr[0] = 0xFF.toByte()
        hdr[1] = 0xF9.toByte()
        hdr[2] = ((0x01 shl 6) or (srIdx shl 2) or (0x01 shr 2)).toByte()
        hdr[3] = (((0x01 and 0x03) shl 6) or (frameLength shr 11 and 0x03)).toByte()
        hdr[4] = (frameLength shr 3 and 0xFF).toByte()
        hdr[5] = ((frameLength and 0x07) shl 5 or 0x1F).toByte()
        hdr[6] = 0xFC.toByte()
        return hdr
    }

    // ======================== 上传 ========================

    /**
     * 异步上传 WAV 音频到后端。
     *
     * 流程：
     * 1. 先尝试上传本地缓存的离线数据 ([uploadCachedData])
     * 2. 构建 multipart/form-data 请求（file/client_time/mode）
     * 3. 通过 OkHttp 发送到 [backendUrl]
     * 4. 成功 → 更新 [stateHolder] response text 和 debug state
     * 5. 失败 → 本地缓存 ([saveToCache])
     *
     * 仅在 [audioBytes] 非空时执行上传。
     * 线程名: DcUpload（与原始 DataCollectorService 一致）
     */
    private fun sendToBackend() {
        Thread({
            try {
                // 先上传缓存数据
                uploadCachedData()

                val wav = audioBytes ?: return@Thread
                val clientMs = recordingStartMs ?: System.currentTimeMillis()
                val clientTimeStr = SimpleDateFormat(
                    "yyyy-MM-dd'T'HH:mm:ssXXX", Locale.getDefault()
                ).format(Date(clientMs))

                val prefs = context.getSharedPreferences("axeuh_prefs", Context.MODE_PRIVATE)
                val baseUrl = com.axeuh.health.monitor.config.ServerConfig.BASE_URL
                val url = "$baseUrl/api/screen/stt/voice-session-multipart"
                val token = prefs.getString("auth_token", "") ?: ""

                // 构建 multipart body
                val requestBody = MultipartBody.Builder()
                    .setType(MultipartBody.FORM)
                    .addFormDataPart("client_time", clientTimeStr)
                    .addFormDataPart("mode", "listen")
                    .addFormDataPart(
                        "file", "audio.wav",
                        wav.toRequestBody("audio/wav".toMediaType())
                    )
                    .build()

                val request = Request.Builder()
                    .url(url)
                    .apply {
                        if (token.isNotEmpty()) {
                            addHeader("Authorization", "Bearer $token")
                        }
                    }
                    .post(requestBody)
                    .build()

                val response = httpClient.getClient().newCall(request).execute()
                val code = response.code
                val respBody = response.body?.string() ?: ""
                response.close()

                Timber.i("上传完成 HTTP $code: ${respBody.take(80)}")

                if (code == 200) {
                    // 更新响应文本
                    try {
                        val text = JSONObject(respBody).optString("text", "")
                        if (text.isNotEmpty()) {
                            stateHolder.updateLastResponseText(text)
                        }
                    } catch (_: Exception) {}
                    stateHolder.updateDebugState(JSONObject().apply {
                        put("audio_last_upload", "success")
                        put("audio_size", wav.size)
                    }.toString())
                } else {
                    Timber.w("上传失败 HTTP $code")
                    saveToCache()
                }

                audioBytes = null
            } catch (e: Exception) {
                Timber.w("上传异常: ${e.message}")
                saveToCache()
            }
        }, "DcUpload").start()
    }

    // ======================== 离线缓存 ========================

    /**
     * 保存当前音频数据到本地缓存。
     * 在 [sendToBackend] 上传失败时调用。
     *
     * 缓存格式：
     * - {timestamp}.json — 包含 client_time 和 mode
     * - {timestamp}.wav  — WAV 音频数据
     */
    private fun saveToCache() {
        try {
            val wav = audioBytes ?: return
            val cacheDir = File(context.cacheDir, CACHE_DIR_NAME)
            cacheDir.mkdirs()
            val ts = System.currentTimeMillis().toString()
            val nowMs = System.currentTimeMillis()
            val clientTimeStr = SimpleDateFormat(
                "yyyy-MM-dd'T'HH:mm:ssXXX", Locale.getDefault()
            ).format(Date(nowMs))
            val jsonData = JSONObject().apply {
                put("client_time", clientTimeStr)
                put("mode", "listen")
            }
            File(cacheDir, "$ts.json").writeText(jsonData.toString())
            File(cacheDir, "$ts.wav").writeBytes(wav)
            Timber.i("数据已缓存: $ts.json + $ts.wav (${wav.size}B)")
        } catch (e: Exception) {
            Timber.w("缓存保存失败: ${e.message}")
        }
    }

    /**
     * 上传一条缓存的 JSON+WAV 到后端。
     *
     * @return true 上传成功
     */
    private fun sendCachedData(jsonStr: String, wavFile: File?): Boolean {
        return try {
            val cachedJson = JSONObject(jsonStr)
            val prefs = context.getSharedPreferences("axeuh_prefs", Context.MODE_PRIVATE)
            val baseUrl = com.axeuh.health.monitor.config.ServerConfig.BASE_URL
            val url = "$baseUrl/api/screen/stt/voice-session-multipart"
            val token = prefs.getString("auth_token", "") ?: ""

            val builder = MultipartBody.Builder().setType(MultipartBody.FORM)
            builder.addFormDataPart(
                "client_time", cachedJson.getString("client_time")
            )
            builder.addFormDataPart(
                "mode", cachedJson.optString("mode", "listen")
            )
            if (wavFile != null && wavFile.exists()) {
                builder.addFormDataPart(
                    "file", "audio.wav",
                    wavFile.asRequestBody("audio/wav".toMediaType())
                )
            }
            val requestBody = builder.build()

            val request = Request.Builder()
                .url(url)
                .apply {
                    if (token.isNotEmpty()) {
                        addHeader("Authorization", "Bearer $token")
                    }
                }
                .post(requestBody)
                .build()

            val response = httpClient.getClient().newCall(request).execute()
            val code = response.code
            response.close()
            code == 200
        } catch (e: Exception) {
            Timber.w("sendCachedData 异常: ${e.message}")
            false
        }
    }

    /**
     * 上传 upload_cache 目录中所有缓存的 JSON+WAV。
     * 按文件名排序（时间戳前缀），先上传最早的。
     * 遇到失败立即停止（服务器可能仍不可用）。
     */
    private fun uploadCachedData() {
        try {
            val cacheDir = File(context.cacheDir, CACHE_DIR_NAME)
            if (!cacheDir.exists()) return
            val jsonFiles = cacheDir.listFiles { f ->
                f.isFile && f.name.endsWith(".json")
            }?.sortedBy { it.name } ?: return
            if (jsonFiles.isEmpty()) return
            Timber.i("找到 ${jsonFiles.size} 个缓存文件，尝试上传...")
            for (jsonFile in jsonFiles) {
                val baseName = jsonFile.nameWithoutExtension
                val wavFile = File(cacheDir, "$baseName.wav")
                try {
                    val jsonData = jsonFile.readText()
                    val success = sendCachedData(
                        jsonData, if (wavFile.exists()) wavFile else null
                    )
                    if (success) {
                        jsonFile.delete()
                        if (wavFile.exists()) wavFile.delete()
                        Timber.i("缓存上传成功: $baseName")
                    } else {
                        Timber.w("缓存上传失败，停止后续尝试: $baseName")
                        break
                    }
                } catch (e: Exception) {
                    Timber.w("缓存上传异常: ${e.message}")
                    break
                }
            }
        } catch (e: Exception) {
            Timber.w("uploadCachedData 异常: ${e.message}")
        }
    }
}
