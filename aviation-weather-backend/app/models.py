"""
数据模型定义
Pydantic Models for Request/Response
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum


class RoleType(str, Enum):
    """用户角色类型"""
    DISPATCHER = "dispatcher"      # 签派员
    GROUND = "ground"              # 地面保障人员
    CONTROLLER = "controller"      # 空中交通管制员
    METEOROLOGIST = "meteorologist" # 专业气象员


class RiskLevel(str, Enum):
    """风险等级"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class WindData(BaseModel):
    """风数据模型"""
    direction: Optional[int] = None
    speed: Optional[int] = None
    gust: Optional[int] = None
    unit: str = "MPS"


class VisibilityData(BaseModel):
    """能见度数据模型"""
    value: Optional[int] = None
    unit: str = "M"


class CloudData(BaseModel):
    """云层数据模型"""
    coverage: str
    height: int
    type: Optional[str] = None


class WeatherPhenomenon(BaseModel):
    """天气现象模型"""
    code: str
    intensity: str = "moderate"


class ParsedMETAR(BaseModel):
    """解析后的METAR数据"""
    raw: str
    station: str = ""
    time: str = ""
    wind: WindData = Field(default_factory=WindData)
    visibility: VisibilityData = Field(default_factory=VisibilityData)
    clouds: List[CloudData] = Field(default_factory=list)
    weather: List[WeatherPhenomenon] = Field(default_factory=list)
    temperature: Optional[int] = None
    dewpoint: Optional[int] = None
    qnh: Optional[int] = None
    trends: List[str] = Field(default_factory=list)


class RiskAssessment(BaseModel):
    """风险评估结果"""
    level: RiskLevel
    score: int = 0
    warnings: List[str] = Field(default_factory=list)


class RoleExplanation(BaseModel):
    """角色解释结果"""
    role: RoleType
    explanation: str
    confidence: float = 0.85


# ========== API请求/响应模型 ==========

class AnalysisRequest(BaseModel):
    """分析请求"""
    metar: str = Field(..., description="METAR报文")
    taf: Optional[str] = Field(None, description="TAF报文（可选）")
    role: RoleType = Field(RoleType.DISPATCHER, description="用户角色")


class AnalysisResponse(BaseModel):
    """分析响应"""
    parsed_metar: ParsedMETAR
    risk_assessment: RiskAssessment
    role_explanation: RoleExplanation
    processing_time_ms: float


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str = "healthy"
    version: str = "1.0.0"
    model: str = "ERNIE-4.0"
