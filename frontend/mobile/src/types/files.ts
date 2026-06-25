/**
 * 文件浏览类型
 *
 * 对应 /api/mobile/files 和 /api/mobile/files/content 接口
 */

/** 文件条目类型 */
export type FileEntryType = 'dir' | 'file';

/** 文件图标分类 (用于前端渲染) */
export type FileIconClass = 'dir' | 'audio' | 'image' | 'doc';

/** 单个文件/目录条目 */
export interface FileEntry {
  /** 文件/目录名称 */
  name: string;
  /** 条目类型 */
  type: FileEntryType;
  /** 文件大小 (字节) */
  size?: number;
  /** 最后修改时间 (ISO 字符串) */
  modified_at?: string;
}

/** /api/mobile/files 响应: 目录列表 */
export interface FileTreeResponse {
  entries: FileEntry[];
}

/**
 * /api/mobile/files/content 响应
 * 文本文件返回 { content: string }
 * JSON/JSONL 文件返回 { objects: PerceptionObject[] }
 * 纯文本端点也可能直接返回字符串 (asText=true)
 */
export interface FileContentJsonResponse {
  /** 文件文本内容 */
  content?: string;
  /** JSON/JSONL 解析后的对象数组 */
  objects?: Array<Record<string, unknown>>;
}

/** 文件搜索查询参数 */
export interface FileSearchQuery {
  /** 搜索关键词 */
  q?: string;
  /** 搜索范围路径 */
  path?: string;
  /** 文件类型过滤 */
  type?: 'dir' | 'file';
}
