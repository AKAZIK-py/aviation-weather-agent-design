import type {
  AnalyzeRequest,
  AnalyzeResponse,
  HealthResponse,
  MetricsResponse,
  AnalyzeV2Response,
  AirportMetarResponse,
  RoleReport,
  UserRole
} from '@/types/api';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '/api/v1';
const API_V2_BASE = process.env.NEXT_PUBLIC_API_V2_URL || 'http://localhost:8000/api/v2';

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
 * V2 API: 使用原始METAR报文分析
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
