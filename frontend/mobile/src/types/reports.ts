/**
 * 报告类型
 *
 * 对应 /api/mobile/reports 接口及报告卡片渲染
 */

/** 报告标签类型 */
export type ReportTag =
  | '日常报告'
  | '异常报告'
  | '周报'
  | '日志'
  | string;

/** 单条报告条目 */
export interface ReportItem {
  /** 报告标题 */
  title: string;
  /** 报告日期 (YYYY-MM-DD) */
  date: string;
  /** 报告类型 */
  type: string;
  /** 报告标签列表 */
  tags?: ReportTag[];
  /** 文件路径 (用于加载报告详情) */
  path?: string;
  /** Markdown 内容 (内联报告全文) */
  md?: string;
}

/** /api/mobile/reports 响应 */
export interface ReportListResponse {
  reports: ReportItem[];
}

/** 报告筛选参数 */
export interface ReportFilter {
  /** 按标签筛选 */
  tag?: ReportTag;
}
