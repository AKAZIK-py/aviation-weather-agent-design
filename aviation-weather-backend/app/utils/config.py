"""
配置管理模块
Configuration Management Module
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """应用配置"""
    
    # 应用基础配置
    APP_NAME: str = "航空气象智能分发系统"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    
    # API服务器配置
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    
    # 百度千帆配置
    QIANFAN_API_KEY: Optional[str] = None
    QIANFAN_SECRET_KEY: Optional[str] = None
    QIANFAN_MODEL: str = "ERNIE-4.0"
    
    # 防滥用配置
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW: int = 3600  # 秒
    
    # 日志配置
    LOG_LEVEL: str = "INFO"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# 全局配置实例
settings = Settings()
