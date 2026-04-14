"""
配置管理模块 - 支持多LLM Provider切换和环境变量管理
参考cc-switch设计模式
"""
from typing import Optional, Literal, Dict, Any
from pydantic import Field
from pydantic_settings import BaseSettings
from functools import lru_cache
import yaml
import os


class Settings(BaseSettings):
    """应用配置"""
    
    # 应用基础配置
    app_name: str = "Aviation Weather Agent"
    app_version: str = "1.0.0"
    debug: bool = Field(False, env="DEBUG")
    
    # API配置
    api_host: str = Field("0.0.0.0", env="API_HOST")
    api_port: int = Field(8000, env="API_PORT")
    
    # LLM Provider配置
    llm_provider: Literal["qianfan", "openai", "anthropic", "deepseek", "moonshot"] = Field(
        "qianfan", env="LLM_PROVIDER"
    )
    
    # 百度千帆配置
    qianfan_api_key: Optional[str] = Field(None, env="QIANFAN_API_KEY")
    qianfan_secret_key: Optional[str] = Field(None, env="QIANFAN_SECRET_KEY")
    qianfan_model: str = Field("ERNIE-4.0-8K", env="QIANFAN_MODEL")
    qianfan_api_base_url: Optional[str] = Field(None, env="QIANFAN_API_BASE_URL")
    
    # OpenAI配置
    openai_api_key: Optional[str] = Field(None, env="OPENAI_API_KEY")
    openai_model: str = Field("gpt-4", env="OPENAI_MODEL")
    openai_base_url: Optional[str] = Field(None, env="OPENAI_BASE_URL")
    
    # Anthropic配置
    anthropic_api_key: Optional[str] = Field(None, env="ANTHROPIC_API_KEY")
    anthropic_model: str = Field("claude-3-sonnet-20240229", env="ANTHROPIC_MODEL")
    anthropic_base_url: Optional[str] = Field(None, env="ANTHROPIC_BASE_URL")
    
    # DeepSeek配置
    deepseek_api_key: Optional[str] = Field(None, env="DEEPSEEK_API_KEY")
    deepseek_model: str = Field("deepseek-chat", env="DEEPSEEK_MODEL")
    deepseek_base_url: str = Field("https://api.deepseek.com/v1", env="DEEPSEEK_BASE_URL")
    
    # Moonshot (Kimi)配置
    moonshot_api_key: Optional[str] = Field(None, env="MOONSHOT_API_KEY")
    moonshot_model: str = Field("moonshot-v1-8k", env="MOONSHOT_MODEL")
    
    # LLM参数配置
    llm_temperature: float = Field(0.1, env="LLM_TEMPERATURE")
    llm_max_tokens: int = Field(2000, env="LLM_MAX_TOKENS")
    llm_request_timeout: int = Field(30, env="LLM_REQUEST_TIMEOUT")
    
    # 数据源配置
    metar_api_base_url: str = Field(
        "https://aviationweather.gov/api/data/metar",
        env="METAR_API_BASE_URL"
    )
    
    # Rate Limiting配置
    rate_limit_requests: int = Field(100, env="RATE_LIMIT_REQUESTS")
    rate_limit_window: int = Field(3600, env="RATE_LIMIT_WINDOW")  # 秒
    
    # 安全配置
    max_metar_length: int = 2000  # METAR报文最大长度
    max_query_length: int = 500   # 用户查询最大长度
    
    # CORS配置
    cors_origins: str = Field('["http://localhost:3000"]', env="CORS_ORIGINS")
    
    # 监控配置
    enable_observability: bool = Field(True, env="ENABLE_OBSERVABILITY")
    enable_metrics: bool = Field(True, env="ENABLE_METRICS")
    metrics_port: int = Field(9090, env="METRICS_PORT")
    otel_enabled: bool = Field(True, env="OTEL_ENABLED")
    otel_service_name: str = Field("aviation-weather-agent", env="OTEL_SERVICE_NAME")
    otel_service_namespace: str = Field("aviation-weather", env="OTEL_SERVICE_NAMESPACE")
    otel_environment: str = Field("development", env="OTEL_ENVIRONMENT")
    otel_exporter_otlp_endpoint: str = Field(
        "http://localhost:4318",
        env="OTEL_EXPORTER_OTLP_ENDPOINT",
    )
    otel_export_timeout_ms: int = Field(10000, env="OTEL_EXPORT_TIMEOUT_MS")
    otel_excluded_urls: str = Field(
        "metrics,docs,redoc,openapi.json",
        env="OTEL_EXCLUDED_URLS",
    )
    phoenix_project_name: str = Field(
        "aviation-weather-agent",
        env="PHOENIX_PROJECT_NAME",
    )
    langfuse_enabled: bool = Field(True, env="LANGFUSE_ENABLED")
    langfuse_public_key: Optional[str] = Field(None, env="LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key: Optional[str] = Field(None, env="LANGFUSE_SECRET_KEY")
    langfuse_base_url: str = Field("http://localhost:3000", env="LANGFUSE_BASE_URL")
    
    # 日志配置
    log_level: str = Field("INFO", env="LOG_LEVEL")
    
    # 航空标准配置
    aviation_standard: Literal["icao", "golden_set"] = Field("icao", env="AVIATION_STANDARD")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # 忽略未定义的环境变量


def load_yaml_config(config_path: str = None) -> Dict[str, Any]:
    """
    从 YAML 文件加载配置
    
    Args:
        config_path: 配置文件路径，默认为 config/agent_config.yaml
    
    Returns:
        配置字典
    """
    if config_path is None:
        # 默认配置路径
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
                                   "config", "agent_config.yaml")
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            return config or {}
    except FileNotFoundError:
        print(f"警告: 配置文件 {config_path} 不存在，使用默认配置")
        return {}
    except yaml.YAMLError as e:
        print(f"警告: 配置文件解析错误: {e}，使用默认配置")
        return {}


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()


# 配置验证函数
def validate_llm_config(settings: Settings) -> None:
    """验证LLM配置是否完整"""
    provider = settings.llm_provider
    
    if provider == "qianfan":
        # V2 API only requires api_key (Bearer token), secret_key is optional for V1 OAuth
        if not settings.qianfan_api_key:
            raise ValueError(
                "Qianfan API配置不完整，需要设置QIANFAN_API_KEY"
            )
    elif provider == "openai":
        if not settings.openai_api_key:
            raise ValueError("OpenAI API配置不完整，需要设置OPENAI_API_KEY")
    elif provider == "anthropic":
        if not settings.anthropic_api_key:
            raise ValueError("Anthropic API配置不完整，需要设置ANTHROPIC_API_KEY")
    elif provider == "deepseek":
        if not settings.deepseek_api_key:
            raise ValueError("DeepSeek API配置不完整，需要设置DEEPSEEK_API_KEY")
    elif provider == "moonshot":
        if not settings.moonshot_api_key:
            raise ValueError("Moonshot API配置不完整，需要设置MOONSHOT_API_KEY")
    else:
        raise ValueError(f"不支持的LLM Provider: {provider}")


# LLM配置获取函数
def get_llm_config(settings: Settings) -> dict:
    """获取当前LLM Provider的配置"""
    provider = settings.llm_provider
    
    configs = {
        "qianfan": {
            "api_key": settings.qianfan_api_key,
            "secret_key": settings.qianfan_secret_key,
            "model": settings.qianfan_model,
            "base_url": settings.qianfan_api_base_url,
        },
        "openai": {
            "api_key": settings.openai_api_key,
            "model": settings.openai_model,
            "base_url": settings.openai_base_url,
        },
        "anthropic": {
            "api_key": settings.anthropic_api_key,
            "model": settings.anthropic_model,
            "base_url": settings.anthropic_base_url,
        },
        "deepseek": {
            "api_key": settings.deepseek_api_key,
            "model": settings.deepseek_model,
            "base_url": settings.deepseek_base_url,
        },
        "moonshot": {
            "api_key": settings.moonshot_api_key,
            "model": settings.moonshot_model,
        },
    }
    
    return configs.get(provider, {})


# 全局配置实例（供其他模块直接导入）
settings = get_settings()
