"""
API请求/响应模型
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class WeatherAnalyzeRequest(BaseModel):
    """天气分析请求"""
    metar_raw: Optional[str] = Field(None, description="原始METAR报文（可选，与airport_icao二选一）", max_length=500)
    airport_icao: Optional[str] = Field(None, description="机场ICAO代码（可选，与metar_raw二选一）", min_length=4, max_length=4)
    user_query: Optional[str] = Field("", description="用户问题（可选）", max_length=200)
    role: str = Field("pilot", description="用户角色：pilot/dispatcher/forecaster/ground_crew")
    session_id: Optional[str] = Field(None, description="会话ID（可选）")
    # 多维度个性化可选字段
    flight_phase: Optional[str] = Field(None, description="飞行阶段：pre_departure/en_route/approach/diversion")
    aircraft_type: Optional[str] = Field(None, description="机型：heavy/regional/helicopter")
    urgency: Optional[str] = Field(None, description="紧迫性：normal/urgent/critical")
    
    def validate_request(self) -> tuple[bool, str]:
        """验证请求参数"""
        if not self.metar_raw and not self.airport_icao:
            return False, "必须提供metar_raw或airport_icao其中之一"
        if self.metar_raw and self.airport_icao:
            return False, "metar_raw和airport_icao只能提供其中之一"
        if self.airport_icao:
            self.airport_icao = self.airport_icao.upper()
        return True, ""
    
    class Config:
        json_schema_extra = {
            "example": {
                "metar_raw": "ZBAA 110530Z 35008MPS 9999 FEW040 12/M05 Q1018 NOSIG",
                "user_query": "当前天气适合起降吗？",
                "role": "pilot",
                "session_id": "session-123",
                "flight_phase": "approach",
                "aircraft_type": "heavy",
                "urgency": "normal",
            }
        }


class WeatherAnalyzeResponse(BaseModel):
    """天气分析响应"""
    success: bool = Field(..., description="处理是否成功")
    metar_parsed: Optional[Dict[str, Any]] = Field(None, description="解析后的METAR数据")
    metar_metadata: Optional[Dict[str, Any]] = Field(None, description="METAR获取元数据（仅从ICAO获取时）")
    detected_role: Optional[str] = Field(None, description="识别的用户角色")
    risk_level: Optional[str] = Field(None, description="风险等级")
    risk_factors: Optional[List[str]] = Field(default=[], description="风险因素列表")
    explanation: Optional[str] = Field(None, description="个性化解释")
    intervention_required: bool = Field(False, description="是否需要人工干预")
    intervention_reason: Optional[str] = Field(None, description="干预原因")
    reasoning_trace: Optional[List[str]] = Field(default=[], description="推理轨迹")
    llm_calls: int = Field(0, description="LLM调用次数")
    processing_time_ms: float = Field(..., description="处理耗时（毫秒）")
    timestamp: datetime = Field(default_factory=datetime.now, description="响应时间戳")
    error: Optional[str] = Field(None, description="错误信息（如果有）")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "metar_parsed": {
                    "icao_code": "ZBAA",
                    "observation_time": "2024-01-11T05:30:00Z",
                    "wind_direction": 350,
                    "wind_speed": 8,
                    "visibility": 9999,
                    "clouds": [{"amount": "FEW", "height": 4000}],
                    "temperature": 12,
                    "dewpoint": -5,
                    "qnh": 1018,
                    "flight_rules": "VFR"
                },
                "detected_role": "空管",
                "risk_level": "LOW",
                "risk_factors": [],
                "explanation": "当前北京首都机场天气条件良好...",
                "intervention_required": False,
                "intervention_reason": None,
                "reasoning_trace": ["[parse_metar_node] 解析成功", "..."],
                "llm_calls": 1,
                "processing_time_ms": 1250.5,
                "timestamp": "2024-01-11T05:35:00Z",
                "error": None
            }
        }


class HealthCheckResponse(BaseModel):
    """健康检查响应"""
    status: str = Field(..., description="服务状态")
    version: str = Field(..., description="服务版本")
    llm_available: bool = Field(..., description="LLM服务是否可用")
    timestamp: datetime = Field(default_factory=datetime.now)


class ErrorResponse(BaseModel):
    """错误响应"""
    error: str = Field(..., description="错误类型")
    message: str = Field(..., description="错误详情")
    timestamp: datetime = Field(default_factory=datetime.now)


class FeedbackRequest(BaseModel):
    """用户反馈请求"""
    session_id: str = Field(..., description="会话ID", min_length=1, max_length=100)
    rating: int = Field(..., description="评分 (1-5)", ge=1, le=5)
    report_id: Optional[str] = Field(None, description="报告ID（可选）")
    corrections: Optional[Dict[str, Any]] = Field(None, description="更正数据")
    safety_issue: bool = Field(False, description="是否涉及安全问题")
    comment: Optional[str] = Field(None, description="用户评论", max_length=1000)
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "session-123",
                "rating": 4,
                "report_id": "report-456",
                "corrections": {
                    "field": "wind_speed",
                    "original": "15KT",
                    "corrected": "18KT"
                },
                "safety_issue": False,
                "comment": "风速解析准确，但建议考虑阵风因素"
            }
        }


class FeedbackResponse(BaseModel):
    """用户反馈响应"""
    success: bool = Field(..., description="处理是否成功")
    feedback_id: str = Field(..., description="反馈ID")
    message: str = Field(..., description="响应消息")
    timestamp: datetime = Field(default_factory=datetime.now, description="响应时间戳")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "feedback_id": "f1a2b3c4-d5e6-7890-abcd-ef1234567890",
                "message": "反馈已提交成功",
                "timestamp": "2024-01-11T05:35:00Z"
            }
        }
