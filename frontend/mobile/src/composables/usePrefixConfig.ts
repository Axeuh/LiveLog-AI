/**
 * 消息前缀配置 Composable
 *
 * 管理发送消息时附加到请求中的前缀配置 (speaker + prompt)。
 * 配置持久化到 localStorage key 'prefix_config'。
 *
 * 使用方式:
 *   const { prefixConfig, updatePrefixConfig } = usePrefixConfig()
 *   console.log(prefixConfig.value.speaker)
 *   updatePrefixConfig({ speaker: '助手', prompt: '请用英文回复' })
 */

import { ref, watch, type Ref } from 'vue';

// ==================== 类型定义 ====================

export interface PrefixConfig {
  speaker: string;
  prompt: string;
}

// ==================== 默认值 ====================

const STORAGE_KEY = 'prefix_config';

const DEFAULT_CONFIG: PrefixConfig = {
  speaker: '用户',
  prompt: '必须第一时间使用tts_speak工具中文回复语音消息。',
};

// ==================== 工具函数 ====================

function loadFromStorage(): PrefixConfig {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      return {
        speaker: parsed.speaker || DEFAULT_CONFIG.speaker,
        prompt: parsed.prompt || DEFAULT_CONFIG.prompt,
      };
    }
  } catch {
    // localStorage 不可用或数据损坏时忽略
  }
  return { ...DEFAULT_CONFIG };
}

function saveToStorage(config: PrefixConfig): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(config));
  } catch {
    // localStorage 不可用时忽略
  }
}

// ==================== 模块级单例 ====================

let _config: Ref<PrefixConfig> | null = null;

/**
 * 获取消息前缀配置单例
 * 确保多个组件间共享同一份响应式状态
 */
export function usePrefixConfig(): {
  prefixConfig: Ref<PrefixConfig>;
  updatePrefixConfig: (config: PrefixConfig) => void;
} {
  if (!_config) {
    _config = ref<PrefixConfig>(loadFromStorage());

    // 持久化同步: 每次 prefixConfig 变化时写回 localStorage
    watch(_config, (val) => {
      saveToStorage(val);
    }, { deep: true });
  }

  function updatePrefixConfig(config: PrefixConfig): void {
    if (_config) {
      _config.value = { ...config };
    }
  }

  return {
    prefixConfig: _config as Ref<PrefixConfig>,
    updatePrefixConfig,
  };
}
