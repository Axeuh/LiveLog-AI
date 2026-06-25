/**
 * 文件浏览 API
 *
 * 对应:
 *   - /api/mobile/files?scope=root&path=... — 目录列表
 *   - /api/mobile/files/content?scope=root&path=... — 文件内容
 *   - /api/mobile/files/raw?scope=root&path=... — 原始文件 (图片/音频)
 *
 * 使用方式:
 *   import { fetchDirectory, fetchFileContent, fetchFileRawUrl } from '@/api/files'
 */

import { apiGet } from '@/api/client';
import type { FileTreeResponse, FileContentJsonResponse } from '@/types';

/**
 * 获取目录列表
 * GET /api/mobile/files?scope=root&path={path}
 */
export async function fetchDirectory(
  path: string,
): Promise<FileTreeResponse | null> {
  return apiGet<FileTreeResponse>(
    '/api/mobile/files?scope=root&path=' + encodeURIComponent(path),
  );
}

/**
 * 获取文件文本/JSON 内容
 * GET /api/mobile/files/content?scope=root&path={path}
 *
 * 返回:
 *   - JSON/JSONL 文件: { objects: [...] } (通过 FileContentJsonResponse)
 *   - 文本文件: 可包含 { content: string } 或原始字符串
 *   - 失败: null
 */
export async function fetchFileContent(
  path: string,
): Promise<FileContentJsonResponse | string | null> {
  // 先尝试 asText=false, 让 client 根据 content-type 自动判断
  // 但如果后端总是返回 JSON 包裹, 则走 JSON 路径
  const result = await apiGet<FileContentJsonResponse | string>(
    '/api/mobile/files/content?scope=root&path=' + encodeURIComponent(path),
  );
  return result;
}

/**
 * 获取原始文件 URL (用于 <img>/<audio> src)
 * 不发起请求, 直接返回构造好的 URL
 */
export function getFileRawUrl(path: string): string {
  return (
    '/api/mobile/files/raw?scope=root&path=' +
    encodeURIComponent(path)
  );
}
