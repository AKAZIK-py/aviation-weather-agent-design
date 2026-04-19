import type {
  AnalyzeRequest,
  AnalyzeResponse,
  HealthResponse,
  MetricsResponse,
  AnalyzeV2Response,
  AirportMetarResponse,
  RoleReport,
  UserRole,
  SSEEvent,
  AirportSearchResult,
  Session,
  SessionDetail,
  SystemMetrics,
  Badcase,
} from '@/types/api';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '/api/v1';
const API_V2_BASE = process.env.NEXT_PUBLIC_API_V2_URL || 'http://localhost:8000/api/v2';
const API_V3_BASE = process.env.NEXT_PUBLIC_API_V3_URL || 'http://localhost:8000/api/v3';

class ApiService {
  private baseUrl: string;
  private baseUrlV2: string;

  constructor(baseUrl: string = API_BASE, baseUrlV2: string = API_V2_BASE) {
    this.baseUrl = baseUrl;
    this.baseUrlV2 = baseUrlV2;
  }

  private async fetchWithError<T>(
    endpoint: string,
    options?: RequestInit,
    useV2 = false
  ): Promise<T> {
    const baseUrl = useV2 ? this.baseUrlV2 : this.baseUrl;
    const response = await fetch(`${baseUrl}${endpoint}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Network error' }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response.json();
  }

  /**
   * 分析METAR报文
   */
  async analyzeMetar(request: AnalyzeRequest): Promise<AnalyzeResponse> {
    return this.fetchWithError<AnalyzeResponse>('/analyze', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  /**
   * 健康检查
   */
  async checkHealth(): Promise<HealthResponse> {
    return this.fetchWithError<HealthResponse>('/health');
  }

  /**
   * 获取评测指标
   */
  async getMetrics(): Promise<MetricsResponse> {
    return this.fetchWithError<MetricsResponse>('/metrics');
  }

  /**
   * V2 API: 分析METAR（增强版）
   * 后端路由: POST /api/v2/analyze  body: { airport_icao, user_role }
   */
  async analyzeV2(icao: string, role: UserRole): Promise<AnalyzeV2Response> {
    return this.fetchWithError<AnalyzeV2Response>(`/analyze`, {
      method: 'POST',
      body: JSON.stringify({ airport_icao: icao, user_role: role }),
    }, true);
  }

  /**
   * V2 API: 获取机场METAR
   * 后端路由: GET /api/v2/airports/{icao}/metar
   */
  async getAirportMetar(icao: string): Promise<AirportMetarResponse> {
    return this.fetchWithError<AirportMetarResponse>(`/airports/${icao}/metar`, undefined, true);
  }

  /**
   * V2 API: 获取角色专属报告
   * 后端路由: GET /api/v2/airports/{icao}/report/{role}
   */
  async getRoleReport(icao: string, role: UserRole): Promise<RoleReport> {
    return this.fetchWithError<RoleReport>(`/airports/${icao}/report/${role}`, undefined, true);
  }
}

// 单例导出
export const apiService = new ApiService();

// 便捷方法
export const analyzeMetar = (request: AnalyzeRequest) => apiService.analyzeMetar(request);
export const checkHealth = () => apiService.checkHealth();
export const getMetrics = () => apiService.getMetrics();

// V2 API便捷方法
export const analyzeV2 = (icao: string, role: UserRole) => apiService.analyzeV2(icao, role);
export const getAirportMetar = (icao: string) => apiService.getAirportMetar(icao);
export const getRoleReport = (icao: string, role: UserRole) => apiService.getRoleReport(icao, role);

/**
/** V2 API: 使用原始METAR报文分析
 * 后端路由: POST /api/v2/analyze  body: { metar_raw, user_role }
 */
export const analyzeMetarWithRaw = async (metarRaw: string, role: UserRole): Promise<AnalyzeV2Response> => {
  const response = await fetch(`${API_V2_BASE}/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ metar_raw: metarRaw, user_role: role }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Network error' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
};

// ========== V3 API ==========

/**
 * SSE 流式对话 — 逐事件 yield
 * 后端路由: POST /api/v3/chat/stream
 */
export async function* chatStream(
  query: string,
  role: UserRole,
  sessionId?: string
): AsyncGenerator<SSEEvent> {
  const response = await fetch(`${API_V3_BASE}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, role, session_id: sessionId }),
  });

  if (!response.ok || !response.body) {
    throw new Error(`SSE request failed: ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    // SSE 格式: "event: xxx\ndata: {...}\n\n"
    const parts = buffer.split('\n\n');
    buffer = parts.pop() || '';

    for (const part of parts) {
      const lines = part.split('\n');
      let eventType = '';
      let data = '';
      for (const line of lines) {
        if (line.startsWith('event: ')) {
          eventType = line.slice(7).trim();
        } else if (line.startsWith('data: ')) {
          data = line.slice(6);
        }
      }
      if (eventType && data) {
        try {
          const parsed = JSON.parse(data);
          yield { type: eventType as SSEEvent['type'], ...parsed } as SSEEvent;
        } catch {
          yield { type: eventType as SSEEvent['type'], content: data } as SSEEvent;
        }
      }
    }
  }
}

/**
 * 搜索机场
 * 后端路由: GET /api/v3/airports/search?q=xxx
 */
export async function searchAirports(q: string): Promise<AirportSearchResult[]> {
  const response = await fetch(`${API_V3_BASE}/airports/search?q=${encodeURIComponent(q)}`);
  if (!response.ok) {
    throw new Error(`Airport search failed: ${response.status}`);
  }
  const data = await response.json();
  return data.results || [];
}

/**
 * 获取会话列表
 * 后端路由: GET /api/v3/sessions
 */
export async function listSessions(userId?: string, limit: number = 10): Promise<Session[]> {
  const params = new URLSearchParams();
  if (userId) params.set('user_id', userId);
  params.set('limit', String(limit));
  const response = await fetch(`${API_V3_BASE}/sessions?${params}`);
  if (!response.ok) {
    throw new Error(`List sessions failed: ${response.status}`);
  }
  const data = await response.json();
  // 后端返回 session_id/message_count/last_active → 前端期望 id/messageCount/updatedAt
  return (data.sessions || []).map((s: Record<string, unknown>) => ({
    id: s.session_id as string,
    title: (s.title as string) || "未命名对话",
    role: "pilot" as UserRole,
    messageCount: (s.message_count as number) || 0,
    lastMessage: (s.last_message as string) || "",
    updatedAt: (s.last_active as string) || "",
  }));
}

/**
 * 获取会话详情
 * 后端路由: GET /api/v3/sessions/{sessionId}
 */
export async function getSession(sessionId: string): Promise<SessionDetail> {
  const response = await fetch(`${API_V3_BASE}/sessions/${sessionId}`);
  if (!response.ok) {
    throw new Error(`Get session failed: ${response.status}`);
  }
  const data = await response.json();
  // 后端返回 { session_id, messages: [{role, content, timestamp}], created_at, last_active }
  // 前端期望 { id, messages: [{id, role, content, timestamp}], createdAt, updatedAt }
  return {
    id: data.session_id || sessionId,
    title: "",
    role: "pilot" as UserRole,
    messages: (data.messages || []).map((m: Record<string, unknown>, i: number) => ({
      id: `${i}-${Date.now()}`,
      role: m.role as "user" | "assistant",
      content: m.content as string,
      timestamp: (m.timestamp as string) || new Date().toISOString(),
    })),
    createdAt: data.created_at || "",
    updatedAt: data.last_active || "",
  };
}

/**
 * 获取系统评测指标
 * 后端路由: GET /api/v3/metrics
 */
export async function getSystemMetrics(days: number = 7): Promise<SystemMetrics> {
  const response = await fetch(`${API_V3_BASE}/metrics?days=${days}`);
  if (!response.ok) {
    throw new Error(`Get metrics failed: ${response.status}`);
  }
  return response.json();
}

/**
 * 获取 badcase 列表
 * 后端路由: GET /api/v3/badcases
 */
export async function getBadcases(limit: number = 20): Promise<Badcase[]> {
  const response = await fetch(`${API_V3_BASE}/badcases?limit=${limit}`);
  if (!response.ok) {
    throw new Error(`Get badcases failed: ${response.status}`);
  }
  const data = await response.json();
  return (data.badcases || []).map((b: Record<string, unknown>) => ({
    case_id: b.case_id as string,
    query: (b.input as Record<string, unknown>)?.query as string || "",
    role: (b.input as Record<string, unknown>)?.role as string || "",
    failure_category: b.category as string || "",
    failure_detail: b.notes as string || "",
    timestamp: b.timestamp as string || "",
    status: b.fixed ? "已修复" : "待修复",
  }));
}

/**
 * 删除会话
 * 后端路由: DELETE /api/v3/sessions/{sessionId}
 */
export async function deleteSession(sessionId: string): Promise<void> {
  const response = await fetch(`${API_V3_BASE}/sessions/${sessionId}`, {
    method: 'DELETE',
  });
  if (!response.ok) {
    throw new Error(`Delete session failed: ${response.status}`);
  }
}
