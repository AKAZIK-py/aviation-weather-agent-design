"""
工具定义层 - 将现有服务包装为 LLM 可调用的 Tool
"""
from app.tools.weather_tools import get_all_tools, TOOL_REGISTRY

__all__ = ["get_all_tools", "TOOL_REGISTRY"]
