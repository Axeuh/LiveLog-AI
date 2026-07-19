/**
 * 类型统一导出入口
 *
 * 使用方式: import type { ApiResponse, HealthSample, ... } from '@/types'
 */

export type {
  ApiResponse,
  LoginRequest,
  LoginResponse,
  SSEEvent,
  SSEPayload,
  SSEProperties,
  SSEMessagePart,
} from './api';

export type {
  HealthSample,
  DailySummary,
  SleepStageType,
  SleepStage,
  SleepData,
  HealthQueryResponse,
  HealthSummary,
  PerceptionSummary,
  BatteryTimelineEntry,
  DashboardResponse,
  BlockSize,
  BlockStat,
  BlockConfig,
  BlockDetailsMap,
  HealthQueryResponse as HealthResult,
  DashboardResponse as DashResult,
} from './health';

export {
  SLEEP_STAGE_COLORS,
  SLEEP_STAGE_LABELS,
  SLEEP_STAGE_ORDER,
} from './health';

export type {
  SessionInfo,
  SessionListResponse,
  CreateSessionRequest,
  CreateSessionResponse,
  SwitchSessionRequest,
  MessageRole,
  MessagePartType,
  MessagePart,
  ChatMessage,
  MessagesResponse,
  TokenUsage,
  StreamPart,
  StreamPartsMap,
  StreamCollapsedMap,
} from './chat';

export type {
  PerceptionObject,
  GpsRawPoint,
  MergedGpsPoint,
  PerceptionFileContent,
  GpsPreviewPoint,
} from './gps';

export type {
  FileEntryType,
  FileIconClass,
  FileEntry,
  FileTreeResponse,
  FileContentJsonResponse,
  FileSearchQuery,
} from './files';

export type {
  ReportTag,
  ReportItem,
  ReportListResponse,
  ReportFilter,
} from './reports';
