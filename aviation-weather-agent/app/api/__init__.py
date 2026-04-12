"""
API模块
"""
from app.api.routes import router
from app.api.schemas import (
    WeatherAnalyzeRequest,
    WeatherAnalyzeResponse,
    HealthCheckResponse,
    ErrorResponse,
)

__all__ = [
    "router",
    "WeatherAnalyzeRequest",
    "WeatherAnalyzeResponse",
    "HealthCheckResponse",
    "ErrorResponse",
]
