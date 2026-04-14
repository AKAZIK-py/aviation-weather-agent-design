"""
数据模型定义 - Pydantic Schemas
"""
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


# ==================== 枚举类型 ====================

class UserRole(str, Enum):
    """用户角色枚举"""
    ATC = "空管"        # 空中交通管制员
    GROUND = "地勤"     # 地面服务人员
    OPERATIONS = "运控" # 运行控制人员
    MAINTENANCE = "机务" # 维修人员


class RiskLevel(str, Enum):
    """风险等级枚举"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class WeatherPhenomenon(str, Enum):
    """天气现象枚举"""
    THUNDERSTORM = "TS"      # 雷暴
    HEAVY_RAIN = "+RA"       # 大雨
    LIGHT_RAIN = "-RA"       # 小雨
    FOG = "FG"               # 雾
    MIST = "BR"              # 轻雾
    HAZE = "HZ"              # 霾
    SNOW = "SN"              # 雪
    ICING = "FZ"             # 结冰
    TURBULENCE = "TURB"      # 湍流
    WIND_SHEAR = "WS"        # 风切变


# ==================== METAR解析模型 ====================

class METARData(BaseModel):
    """METAR解析后的结构化数据"""
    raw_text: str = Field(..., description="原始METAR报文")
    icao_code: str = Field(..., description="机场ICAO代码")
    observation_time: datetime = Field(..., description="观测时间")
    temperature: Optional[int] = Field(None, description="温度(摄氏度)")
    dewpoint: Optional[int] = Field(None, description="露点温度(摄氏度)")
    wind_direction: Optional[int] = Field(None, description="风向(度)")
    wind_speed: Optional[int] = Field(None, description="风速(节)")
    wind_gust: Optional[int] = Field(None, description="阵风风速(节)")
    visibility: Optional[float] = Field(None, description="能见度(公里)")
    altimeter: Optional[float] = Field(None, description="高度表设定(英寸汞柱)")
    present_weather: List[str] = Field(default_factory=list, description="当前天气现象")
    cloud_layers: List[Dict[str, Any]] = Field(default_factory=list, description="云层信息")
    flight_rules: Optional[str] = Field(None, description="飞行规则(VFR/MVFR/IFR/LIFR)")
    parsed_successfully: bool = Field(..., description="是否解析成功")
    parse_errors: List[str] = Field(default_factory=list, description="解析错误信息")


# ==================== Agent状态模型 ====================

class AgentState(BaseModel):
    """Agent工作流状态"""
    # 输入
    metar_raw: str = Field(..., description="原始METAR报文")
    user_query: Optional[str] = Field(None, description="用户自然语言查询")
    user_role: Optional[UserRole] = Field(None, description="用户角色")
    
    # 中间状态
    metar_parsed: Optional[METARData] = Field(None, description="解析后的METAR数据")
    detected_role: Optional[UserRole] = Field(None, description="检测到的用户角色")
    risk_level: Optional[RiskLevel] = Field(None, description="风险评估等级")
    safety_check_passed: Optional[bool] = Field(None, description="安全边界检查是否通过")
    safety_violations: List[str] = Field(default_factory=list, description="安全违规信息")
    
    # 输出
    explanation: Optional[str] = Field(None, description="生成的气象解释")
    confidence_score: Optional[float] = Field(None, description="置信度分数")
    reasoning_trace: List[str] = Field(default_factory=list, description="推理过程追踪")
    
    # 元数据
    processing_time: Optional[float] = Field(None, description="处理时间(秒)")
    llm_calls: int = Field(default=0, description="LLM调用次数")
    token_usage: Dict[str, int] = Field(default_factory=dict, description="Token使用统计")


# ==================== 请求/响应模型 ====================

class AnalyzeRequest(BaseModel):
    """气象分析请求"""
    metar: str = Field(..., description="METAR报文", max_length=2000)
    query: Optional[str] = Field(None, description="自然语言查询", max_length=500)
    role: Optional[UserRole] = Field(None, description="用户角色")
    request_id: Optional[str] = Field(None, description="请求ID")


class AnalyzeResponse(BaseModel):
    """气象分析响应"""
    success: bool = Field(..., description="是否成功")
    explanation: Optional[str] = Field(None, description="气象解释")
    risk_level: Optional[RiskLevel] = Field(None, description="风险等级")
    detected_role: Optional[UserRole] = Field(None, description="检测到的角色")
    confidence_score: Optional[float] = Field(None, description="置信度")
    reasoning_trace: List[str] = Field(default_factory=list, description="推理过程")
    safety_violations: List[str] = Field(default_factory=list, description="安全违规")
    processing_time: float = Field(..., description="处理时间(秒)")
    request_id: Optional[str] = Field(None, description="请求ID")
    error: Optional[str] = Field(None, description="错误信息")


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str = Field(..., description="服务状态")
    version: str = Field(..., description="版本号")
    llm_provider: str = Field(..., description="当前LLM Provider")
    uptime: float = Field(..., description="运行时间(秒)")


# ==================== 评测相关模型 ====================

class EvaluationMetrics(BaseModel):
    """评测指标"""
    # D1: 规则映射准确率
    d1_rule_mapping_accuracy: float = Field(..., ge=0, le=1)
    
    # D2: 角色匹配准确率
    d2_role_matching_accuracy: float = Field(..., ge=0, le=1)
    
    # D3: 安全边界召回率 (必须=1.0)
    d3_safety_recall: float = Field(..., ge=0, le=1)
    
    # D4: 幻觉率 (必须<=0.05)
    d4_hallucination_rate: float = Field(..., ge=0, le=1)
    
    # D5: 越权表达率 (必须=0.0)
    d5_authority_violation_rate: float = Field(..., ge=0, le=1)
    
    # 其他指标
    avg_response_time: float = Field(..., description="平均响应时间(秒)")
    avg_confidence_score: float = Field(..., description="平均置信度")
    total_test_cases: int = Field(..., description="测试用例总数")
    pass_rate: float = Field(..., ge=0, le=1, description="通过率")


class TestCase(BaseModel):
    """测试用例"""
    test_id: str = Field(..., description="测试ID")
    category: str = Field(..., description="测试类别(D1-D5)")
    metar: str = Field(..., description="METAR报文")
    query: Optional[str] = Field(None, description="查询")
    expected_role: Optional[UserRole] = Field(None, description="期望角色")
    expected_risk: Optional[RiskLevel] = Field(None, description="期望风险等级")
    expected_safety_violation: Optional[bool] = Field(None, description="是否期望安全违规")
    ground_truth: str = Field(..., description="标准答案")
    evaluation_criteria: Dict[str, Any] = Field(default_factory=dict, description="评测标准")


class EvaluationResult(BaseModel):
    """评测结果"""
    test_id: str = Field(..., description="测试ID")
    passed: bool = Field(..., description="是否通过")
    actual_output: str = Field(..., description="实际输出")
    expected_output: str = Field(..., description="期望输出")
    scores: Dict[str, float] = Field(default_factory=dict, description="各维度得分")
    reasoning: str = Field(..., description="判定理由")
    llm_judge_score: Optional[float] = Field(None, description="LLM评分")
