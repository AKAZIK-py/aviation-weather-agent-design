// API Types - 匹配后端 schemas (四角色体系)

export interface METARData {
  raw_text: string;
  icao_code?: string;
  observation_time?: string;
  temperature?: number;
  dewpoint?: number;
  wind_direction?: number | null;
  wind_speed?: number | null;
  wind_gust?: number | null;
  visibility?: number;
  altimeter?: number | null;
  present_weather?: Array<{
    code: string;
    description: string;
    intensity?: string;
  }>;
  cloud_layers?: Array<{
    cover: string;
    height_feet: number;
    cloud_type?: string;
  }>;
  flight_rules?: string | null;
}

export interface AnalyzeRequest {
  metar_raw?: string;  // 可选：直接输入METAR报文
  airport_icao?: string;  // 可选：选择机场ICAO代码
  role?: UserRole;  // 可选：用户角色
  user_query?: string;
  session_id?: string;
}

// 风险等级 - 四级体系
export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

// 角色类型 - 四角色体系
export type UserRole = 'pilot' | 'dispatcher' | 'forecaster' | 'ground_crew';

export interface AnalyzeResponse {
  success: boolean;
  metar_parsed?: METARData;
  metar_metadata?: {
    source: string;  // 'manual' | 'realtime'
    icao_code?: string;
    fetched_at?: string;
    raw_text?: string;
  };
  airport_name?: string;
  detected_role?: UserRole;
  risk_level?: RiskLevel;
  risk_factors?: string[];
  risk_reasoning?: string;
  structured_output?: Record<string, any>; // LLM生成的结构化输出
  basic_explanation?: string; // 基础解释（备份）
  intervention_required: boolean;
  intervention_reason?: string;
  reasoning_trace?: string[];
  llm_calls: number;
  processing_time_ms: number;
  timestamp: string;
  error?: string | null;
}

export interface HealthResponse {
  status: string;
  version: string;
  llm_available: boolean;
  timestamp: string;
}

export interface MetricsResponse {
  requests_total: number;
  requests_success: number;
  requests_failed: number;
  avg_processing_time_ms: number;
  llm_calls_total: number;
}

// 角色配置接口
export interface RoleConfig {
  id: UserRole;
  label: string;
  description: string;
  icon: string;
  focusAreas: string[];
}

// 角色配置常量
export const ROLES: RoleConfig[] = [
  {
    id: "pilot",
    label: "飞行员",
    description: "关注飞行安全与起降决策",
    icon: "✈️",
    focusAreas: ["决断高", "进近方式", "侧风标准", "复飞决策"],
  },
  {
    id: "dispatcher",
    label: "签派管制",
    description: "关注航班运行效率与决策支持",
    icon: "📋",
    focusAreas: ["航班正常性", "备降决策", "油量计算", "签派放行"],
  },
  {
    id: "forecaster",
    label: "预报员",
    description: "关注天气趋势分析与预报",
    icon: "🌡️",
    focusAreas: ["气压系统", "气团特征", "对流发展", "数值预报"],
  },
  {
    id: "ground_crew",
    label: "地勤",
    description: "关注地面作业安全与保障效率",
    icon: "🚜",
    focusAreas: ["作业时间", "设备限制", "人员安全", "保障流程"],
  },
];

// 风险等级颜色映射
export const RISK_LEVEL_COLORS: Record<RiskLevel, string> = {
  LOW: "bg-green-100 text-green-800 border-green-200",
  MEDIUM: "bg-yellow-100 text-yellow-800 border-yellow-200",
  HIGH: "bg-orange-100 text-orange-800 border-orange-200",
  CRITICAL: "bg-red-100 text-red-800 border-red-200",
};

// 风险等级中文映射
export const RISK_LEVEL_LABELS: Record<RiskLevel, string> = {
  LOW: "低风险",
  MEDIUM: "中风险",
  HIGH: "高风险",
  CRITICAL: "极高风险",
};

// ========== 工作流类型 ==========

// 工作流步骤
export type WorkflowStep = 'airport_selection' | 'data_fetch' | 'analysis' | 'report';

// 工作流步骤配置
export const WORKFLOW_STEPS: Array<{
  id: WorkflowStep;
  label: string;
  icon: string;
}> = [
  { id: 'airport_selection', label: '机场选择', icon: '✈️' },
  { id: 'data_fetch', label: '数据获取', icon: '📡' },
  { id: 'analysis', label: '大模型分析', icon: '🤖' },
  { id: 'report', label: '报告分发', icon: '📊' },
];

// 告警严重程度
export type AlertSeverity = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';

// 天气告警
export interface WeatherAlert {
  id: string;
  severity: AlertSeverity;
  title: string;
  description: string;
  recommended_action?: string;
  timestamp: string;
}

// 角色摘要
export interface RoleSummary {
  headlines: string[];
  decision: "GO" | "CAUTION" | "NO-GO";
  confidence: string;
}

// 角色专属报告
export interface RoleReport {
  role: UserRole;
  role_cn?: string;
  airport_icao?: string;
  observation_time?: string;
  risk_level: RiskLevel;
  summary: string;
  role_summary?: RoleSummary;
  disclaimer?: string;
  alerts: WeatherAlert[];
  recommendations: string[];
  detailed_analysis?: Record<string, any>;
  structured_analysis?: Record<string, any> | null;
  generated_at: string;
  model_used?: string;
}

// 分析进度状态
export interface AnalysisProgress {
  current_step: WorkflowStep;
  step_progress: number; // 0-100
  status_message: string;
  estimated_time_remaining?: number; // seconds
}

// V2 API 响应类型
export interface AnalyzeV2Response {
  success: boolean;
  metar_raw?: string;
  metar_parsed?: METARData;
  metar_metadata?: {
    source: string;
    icao_code?: string;
    fetched_at?: string;
    raw_text?: string;
  };
  airport_name?: string;
  detected_role?: UserRole;
  risk_level?: RiskLevel;
  risk_factors?: string[];
  role_report?: RoleReport;
  role_summary?: RoleSummary;
  disclaimer?: string;
  error?: string | null;
  llm_calls: number;
  processing_time_ms: number;
  timestamp: string;
}

// 机场METAR响应
export interface AirportMetarResponse {
  icao: string;
  airport_name: string;
  metar_raw: string;
  metar_parsed: METARData;
  fetched_at: string;
  source: string;
}

// ========== V3 Chat 类型 ==========

// SSE 事件类型
export type SSEEventType = 'thinking' | 'tool_call' | 'tool_result' | 'answer' | 'eval' | 'error' | 'done';

export interface SSEEvent {
  type: SSEEventType;
  tool?: string;
  args?: Record<string, unknown>;
  result?: string;
  content?: string;
  status?: string;
  session_id?: string;
  message?: string;
  // eval event 字段（直接在顶层，不是嵌套在 scores 里）
  task_complete?: boolean;
  key_info_hit?: string;
  output_usable?: boolean;
  hallucination_rate?: number;
}

export interface EvalScores {
  task_complete: boolean;
  key_info_hit: string;       // "3/12"
  output_usable: boolean;
  hallucination_rate: number; // 0.0 ~ 1.0
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  toolCalls?: ToolCallTrace[];
  evalScores?: EvalScores;
  timestamp: string;
}

export interface ToolCallTrace {
  tool: string;
  args: Record<string, unknown>;
  result: string;
  durationMs?: number;
}

export interface Session {
  id: string;
  title: string;
  role: UserRole;
  messageCount: number;
  lastMessage: string;
  updatedAt: string;
}

export interface SessionDetail {
  id: string;
  title: string;
  role: UserRole;
  messages: Message[];
  createdAt: string;
  updatedAt: string;
}

export interface AirportSearchResult {
  icao: string;
  iata?: string;
  name: string;
  city: string;
}

// ========== 指标面板类型 ==========

export interface SystemMetrics {
  total_requests: number;
  success_rate: number;
  avg_latency_ms: number;
  task_completion_rate: number;
  output_usability_rate: number;
  hallucination_rate: number;
  badcase_count: number;
  role_distribution: Record<string, number>;
  daily_trend: DailyTrend[];
  // Token 统计
  total_prompt_tokens: number;
  total_completion_tokens: number;
  total_tokens: number;
  avg_tokens_per_request: number;
  provider_distribution: Record<string, number>;
}

export interface DailyTrend {
  date: string;
  requests: number;
  task_completion: number;
  hallucination: number;
  avg_latency_ms: number;
  total_tokens: number;
  avg_tokens: number;
}

export interface Badcase {
  case_id: string;
  query: string;
  role: string;
  failure_category: string;
  failure_detail: string;
  timestamp: string;
  status: string;
}
