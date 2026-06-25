/**
 * TTS 播放器 Composable — 通过 WebSocket 接收并播放 TTS 音频
 *
 * 对应 ws 消息类型:
 *   - tts_start:        TTS 开始
 *   - tts_audio:        完整音频 (base64 WAV) — 不拆分，一次播放
 *   - tts_audio_chunk:  音频分片 (base64 WAV/PCM) — 按序播放，不叠加
 *   - tts_end:          TTS 结束
 *
 * 使用 Web Audio API 解码并播放音频
 */
import { useRealTimeSingleton } from '@/composables/useRealTime'

// ==================== 音频分片数据结构 ====================

interface TtsChunk {
  audio: string
  chunk_index: number
  chunk_total: number
}

// ==================== Web Audio API ====================

let _audioCtx: AudioContext | null = null
let _wired = false
/** 当前正在播放的音源节点，用于停止 */
let _currentSource: AudioBufferSourceNode | null = null

function getAudioCtx(): AudioContext {
  if (!_audioCtx) {
    _audioCtx = new (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)()
  }
  if (_audioCtx.state === 'suspended') {
    _audioCtx.resume()
  }
  return _audioCtx
}

/** 停止当前正在播放的音频 */
function stopCurrentAudio(): void {
  if (_currentSource) {
    try {
      _currentSource.onended = null  // 防止触发 resolve
      _currentSource.stop()
    } catch {
      // 可能已经停止了
    }
    _currentSource = null
  }
}

/** 播放 Base64 编码音频，返回 Promise 在播放完成后 resolve */
function playTtsAudio(base64Audio: string): Promise<void> {
  return new Promise((resolve) => {
    try {
      const binaryStr = atob(base64Audio)
      const bytes = new Uint8Array(binaryStr.length)
      for (let i = 0; i < binaryStr.length; i++) {
        bytes[i] = binaryStr.charCodeAt(i)
      }
      const ctx = getAudioCtx()
      ctx.decodeAudioData(bytes.buffer, (buf) => {
        const src = ctx.createBufferSource()
        src.buffer = buf
        src.connect(ctx.destination)
        src.onended = () => {
          _currentSource = null
          resolve()
        }
        _currentSource = src
        src.start()
      }, () => {
        _currentSource = null
        resolve()
      })
    } catch {
      _currentSource = null
      resolve()
    }
  })
}

// ==================== WS 消息处理 ====================

/** 播放队列：链式 Promise，确保音频按序播放不叠加 */
let _playingQueue: Promise<void> = Promise.resolve()

function handleWsMessage(data: unknown): void {
  const msg = data as Record<string, unknown>
  const type = msg.type as string | undefined
  if (!type) return

  if (type === 'tts_start') {
    // 前台停止正在播放的音频 + 重置队列，丢弃未播的
    stopCurrentAudio()
    _playingQueue = Promise.resolve()
    return
  }

  if (type === 'tts_audio') {
    // 完整音频排队播（不覆盖队列，防止与 chunk 叠加）
    const audio = msg.audio as string | undefined
    if (audio) {
      _playingQueue = _playingQueue.then(() => playTtsAudio(audio))
    }
    return
  }

  if (type === 'tts_audio_chunk') {
    // 音频分片按序播放：新分片排队等前一个播完
    const chunk = msg as unknown as TtsChunk
    if (chunk.audio) {
      _playingQueue = _playingQueue.then(() => playTtsAudio(chunk.audio))
    }
    return
  }

  if (type === 'tts_end') {
    // TTS 结束，不做操作
  }
}

/**
 * 挂载 TTS 播放器到 WebSocket 消息流
 */
export function wireTtsPlayer(): void {
  if (_wired) return
  _wired = true
  const rt = useRealTimeSingleton()
  rt.onWSMessage(handleWsMessage)
}
