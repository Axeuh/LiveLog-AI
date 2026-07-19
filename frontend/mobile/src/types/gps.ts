/**
 * GPS 数据类型
 *
 * 对应 /api/mobile/files/content?path=.../perception.jsonl 中的 GPS 数据
 * 以及 parseGpsFromPerception / mergeGpsPoints 处理流程
 */

// ==================== 原始 GPS 数据 ====================

/**
 * 感知数据对象 (perception.jsonl 中的单行对象)
 * 可能包含 GPS 信息，格式可为字符串 "lat,lng" 或数组 [{lat, lng}]
 */
export interface PerceptionObject {
  /** 时间字符串 (如 "12:00") */
  t?: string;
  /** GPS 位置 - 可能是 "lat,lng" 字符串 */
  gps?: string;
  /** 地点名称 */
  place?: string;
  /** 其他感知字段 */
  [key: string]: unknown;
}

/**
 * 解析后的原始 GPS 点
 * 由 parseGpsFromPerception 从 PerceptionObject[] 中提取
 */
export interface GpsRawPoint {
  /** 时间字符串 (如 "12:00") */
  t: string;
  /** 纬度 */
  lat: number;
  /** 经度 */
  lng: number;
  /** 地点名称 */
  place: string;
}

// ==================== 合并后的 GPS 点 ====================

/**
 * 合并后的 GPS 点 (由 mergeGpsPoints 处理)
 * 将邻近/相同位置的原始点合并，减少渲染点数
 * 接口未知，从使用模式推断
 */
export interface MergedGpsPoint {
  /** 时间字符串 */
  t: string;
  /** 纬度 */
  lat: number;
  /** 经度 */
  lng: number;
  /** 地点名称 */
  place: string;
  /** 合并计数 (该位置聚合的原始点数) */
  count?: number;
}

// ==================== 文件内容响应 ====================

/** /api/mobile/files/content 返回的 JSON 文件内容 */
export interface PerceptionFileContent {
  /** 感知数据对象数组 */
  objects: PerceptionObject[];
}

// ==================== 地图相关类型 ====================

/** GPS 预览画布渲染数据点 */
export interface GpsPreviewPoint {
  x: number;
  y: number;
  lat: number;
  lng: number;
  label: string;
}
