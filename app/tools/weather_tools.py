"""
航空气象工具集 - 将现有服务包装为 LLM 可调用的 Tool

每个工具：
- 输入：结构化参数（Pydantic model）
- 输出：结构化 dict（JSON可序列化）
- 失败：返回 {"error": "具体错误信息"} 而非抛异常
"""

import asyncio
import functools
import logging
import time
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field

from app.nodes.parse_metar_node import parse_metar_node
from app.nodes.assess_risk_node import assess_risk_node
from app.utils.visibility import format_visibility_range
from app.core.metrics import get_metrics
from app.core.telemetry import get_tracer, mark_span_error

logger = logging.getLogger(__name__)
metrics = get_metrics()
tracer = get_tracer(__name__)


def observable_tool(tool_name: str, model_class: type = None):
    """为工具增加 Prometheus + OTel 埋点。

    Args:
        tool_name: 工具名称
        model_class: 参数的 Pydantic 模型类，用于将 kwargs 转换为模型实例
    """

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(params=None, **kwargs):
            start = time.perf_counter()

            # 处理参数：如果传入了 kwargs 且没有 params，用 model_class 构造
            if params is None and kwargs and model_class:
                params = model_class(**kwargs)
            elif params is None and not kwargs:
                raise ValueError(
                    f"Tool {tool_name} requires either params or keyword arguments"
                )

            with tracer.start_as_current_span(f"tool.{tool_name}") as span:
                span.set_attribute("tool.name", tool_name)
                span.set_attribute(
                    "tool.param_keys", list(params.model_dump(exclude_none=True).keys())
                )
                try:
                    result = await func(params)
                    status = (
                        "error"
                        if isinstance(result, dict) and result.get("error")
                        else "success"
                    )
                    metrics.record_tool_call(
                        tool=tool_name,
                        status=status,
                        duration_seconds=time.perf_counter() - start,
                        error_type=tool_name if status == "error" else None,
                    )
                    if status == "error":
                        error_message = str(result.get("error", "tool returned error"))
                        span.set_attribute("tool.error", error_message[:200])
                        mark_span_error(span, message=error_message[:200])
                    return result
                except Exception as exc:
                    metrics.record_tool_call(
                        tool=tool_name,
                        status="exception",
                        duration_seconds=time.perf_counter() - start,
                        error_type=exc.__class__.__name__,
                    )
                    mark_span_error(span, exc)
                    raise

        return wrapper

    return decorator


# ==================== Tool Schema 定义 ====================


class FetchMetarParams(BaseModel):
    """获取指定ICAO机场的实时METAR报文"""

    icao: str = Field(description="4字母ICAO机场代码，如 ZBAA、ZSPD")


class ParseMetarParams(BaseModel):
    """解析原始METAR报文为结构化数据，包含飞行规则、风、能见度、云层等"""

    raw_metar: str = Field(description="原始METAR报文文本")


class GetFlightRulesParams(BaseModel):
    """根据能见度和云底高计算ICAO Annex 3飞行规则"""

    visibility_km: float = Field(description="能见度，单位千米")
    ceiling_ft: Optional[float] = Field(
        default=None,
        description="云底高（最低BKN/OVC层），单位英尺。FEW和SCT不算ceiling。无云底时传null",
    )


class AssessRiskParams(BaseModel):
    """多维度风险评估：能见度、风、天气现象、风切变、云底高"""

    metar_parsed: Dict[str, Any] = Field(
        description="parse_metar工具返回的结构化METAR数据"
    )


class GetApproachMinimaParams(BaseModel):
    """获取机场指定跑道的进近最低标准（DH/MDA）"""

    icao: str = Field(description="4字母ICAO机场代码")
    runway: Optional[str] = Field(
        default=None, description="跑道号，如 '01'、'19L'。不指定则返回所有跑道"
    )


class FormatVisibilityParams(BaseModel):
    """将能见度精确值转换为区间化描述（对外展示用）"""

    visibility_km: float = Field(description="能见度精确值，单位千米")


class FetchTafParams(BaseModel):
    """获取指定ICAO机场的TAF预报报文"""

    icao: str = Field(description="4字母ICAO机场代码，如 ZBAA、ZSPD")


class GetFullWeatherParams(BaseModel):
    """获取机场完整气象信息（METAR实况 + TAF预报），联合分析用"""

    icao: str = Field(description="4字母ICAO机场代码，如 ZBAA、ZSPD")


# ==================== Tool 执行函数 ====================


@observable_tool("fetch_metar", FetchMetarParams)
async def _fetch_metar(params: FetchMetarParams) -> Dict[str, Any]:
    """获取实时METAR"""
    from app.services.metar_fetcher import fetch_metar_for_airport, MetarFetchError

    try:
        raw_metar, metadata = await fetch_metar_for_airport(params.icao)
        return {
            "icao": params.icao.upper(),
            "raw_metar": raw_metar,
            "metadata": metadata,
        }
    except MetarFetchError as e:
        return {"error": f"获取{params.icao}的METAR失败: {str(e)}"}
    except Exception as e:
        return {"error": f"网络或服务异常: {str(e)}"}


@observable_tool("parse_metar", ParseMetarParams)
async def _parse_metar(params: ParseMetarParams) -> Dict[str, Any]:
    """解析METAR报文"""
    try:
        state = {"metar_raw": params.raw_metar}
        result = await parse_metar_node(state, None)
        if result.get("parse_error"):
            return {"error": f"解析失败: {result['parse_error']}"}
        return {
            "metar_parsed": result.get("metar_parsed", {}),
            "parse_success": result.get("parse_success", False),
        }
    except Exception as e:
        return {"error": f"METAR解析异常: {str(e)}"}


@observable_tool("get_flight_rules", GetFlightRulesParams)
async def _get_flight_rules(params: GetFlightRulesParams) -> Dict[str, Any]:
    """计算飞行规则"""
    vis_sm = params.visibility_km / 1.60934
    ceiling_ft = params.ceiling_ft

    # ICAO Annex 3 标准
    # 取能见度和ceiling中较差的类别
    def _vis_category(v_sm):
        if v_sm < 1:
            return "LIFR"
        elif v_sm < 3:
            return "IFR"
        elif v_sm < 5:
            return "MVFR"
        else:
            return "VFR"

    def _ceil_category(c_ft):
        if c_ft is None:
            return "VFR"
        elif c_ft < 500:
            return "LIFR"
        elif c_ft < 1000:
            return "IFR"
        elif c_ft < 3000:
            return "MVFR"
        else:
            return "VFR"

    cats = [_vis_category(vis_sm)]
    if ceiling_ft is not None:
        cats.append(_ceil_category(ceiling_ft))

    order = {"LIFR": 0, "IFR": 1, "MVFR": 2, "VFR": 3}
    worst = min(cats, key=lambda c: order.get(c, 3))

    return {
        "flight_rules": worst,
        "visibility_sm": round(vis_sm, 2),
        "ceiling_ft": ceiling_ft,
        "visibility_category": _vis_category(vis_sm),
        "ceiling_category": _ceil_category(ceiling_ft) if ceiling_ft else None,
    }


@observable_tool("assess_risk", AssessRiskParams)
async def _assess_risk(params: AssessRiskParams) -> Dict[str, Any]:
    """风险评估"""
    try:
        state = {"metar_parsed": params.metar_parsed}
        result = await assess_risk_node(state, None)
        return {
            "risk_level": result.get("risk_level", "LOW"),
            "risk_factors": result.get("risk_factors", []),
            "risk_reasoning": result.get("risk_reasoning", ""),
        }
    except Exception as e:
        return {"error": f"风险评估异常: {str(e)}"}


@observable_tool("get_approach_minima", GetApproachMinimaParams)
async def _get_approach_minima(params: GetApproachMinimaParams) -> Dict[str, Any]:
    """获取进近最低标准"""
    from app.utils.approach import get_decision_heights

    try:
        icao = params.icao.upper()
        runway = params.runway

        # 返回标准进近最低值参考（不依赖外部数据）
        info = get_decision_heights(cloud_ceiling_ft=None)

        lines = [f"{icao} 标准进近最低值参考："]
        for approach_type, entry in info["approaches"].items():
            dh_label = "DH" if entry["type"] == "DH" else "MDA"
            lines.append(f"  - {entry['description']}: {dh_label} {entry['value_ft']}ft")

        if runway:
            lines.append(f"\n跑道 {runway} 的具体进近标准请查阅航图（Jeppesen/NAIP）。")

        return {
            "icao": icao,
            "runway": runway,
            "approach_minima": "\n".join(lines),
        }
    except Exception as e:
        return {"error": f"获取进近标准失败: {str(e)}"}


@observable_tool("format_visibility", FormatVisibilityParams)
async def _format_visibility(params: FormatVisibilityParams) -> Dict[str, Any]:
    """能见度区间化"""
    range_str = format_visibility_range(params.visibility_km)
    return {
        "exact_km": params.visibility_km,
        "range_description": range_str,
    }


@observable_tool("fetch_taf", FetchTafParams)
async def _fetch_taf(params: FetchTafParams) -> Dict[str, Any]:
    """获取TAF预报"""
    from app.services.metar_fetcher import fetch_taf_for_airport, MetarFetchError

    try:
        raw_taf, metadata = await fetch_taf_for_airport(params.icao)
        return {
            "icao": params.icao.upper(),
            "raw_taf": raw_taf,
            "metadata": metadata,
        }
    except MetarFetchError as e:
        return {"error": f"获取{params.icao}的TAF失败: {str(e)}"}
    except Exception as e:
        return {"error": f"网络或服务异常: {str(e)}"}


@observable_tool("get_full_weather", GetFullWeatherParams)
async def _get_full_weather(params: GetFullWeatherParams) -> Dict[str, Any]:
    """获取METAR+TAF联合数据"""
    from app.services.metar_fetcher import (
        fetch_metar_for_airport,
        fetch_taf_for_airport,
        MetarFetchError,
    )

    icao = params.icao.upper()
    result = {"icao": icao}

    # 获取METAR
    try:
        raw_metar, metar_meta = await fetch_metar_for_airport(icao)
        result["metar"] = {"raw": raw_metar, "metadata": metar_meta}
    except MetarFetchError as e:
        result["metar"] = {"error": str(e)}
    except Exception as e:
        result["metar"] = {"error": f"网络异常: {str(e)}"}

    # 获取TAF
    try:
        raw_taf, taf_meta = await fetch_taf_for_airport(icao)
        result["taf"] = {"raw": raw_taf, "metadata": taf_meta}
    except MetarFetchError as e:
        result["taf"] = {"error": str(e)}
    except Exception as e:
        result["taf"] = {"error": f"网络异常: {str(e)}"}

    return result


# ==================== 工具失败降级链 ====================

# 缓存层: 简单内存缓存 (生产环境可替换为 Redis)
_weather_cache: Dict[str, Dict[str, Any]] = {}
CACHE_TTL_SECONDS = 300  # 5分钟


def _get_cache(key: str) -> Optional[Dict[str, Any]]:
    """从缓存获取数据"""
    entry = _weather_cache.get(key)
    if entry and (time.time() - entry.get("_cached_at", 0)) < CACHE_TTL_SECONDS:
        logger.info("[fallback] 使用缓存数据: %s", key)
        return entry.get("data")
    return None


def _set_cache(key: str, data: Dict[str, Any]) -> None:
    """写入缓存"""
    _weather_cache[key] = {"data": data, "_cached_at": time.time()}


def _rule_engine_fallback(icao: str) -> Dict[str, Any]:
    """规则引擎降级: 当 API 和缓存都不可用时，返回通用安全建议"""
    logger.warning("[fallback] 使用规则引擎降级: %s", icao)
    return {
        "icao": icao.upper(),
        "fallback": True,
        "source": "rule_engine",
        "message": f"无法获取{icao}实时气象数据。请查阅航图和NOTAM获取最新信息。建议联系ATC确认天气条件。",
    }


async def _fetch_with_fallback(icao: str, fetch_func) -> Dict[str, Any]:
    """
    带降级链的数据获取: API → 缓存 → 规则引擎

    Args:
        icao: 机场代码
        fetch_func: 实际的 fetch 函数
    """
    cache_key = f"metar:{icao.upper()}"

    # 第一层: 尝试 API
    try:
        result = await fetch_func(icao)
        if result and not result.get("error"):
            _set_cache(cache_key, result)
            return result
        logger.warning("[fallback] API 返回错误: %s", result.get("error", "unknown"))
    except Exception as e:
        logger.warning("[fallback] API 异常: %s", e)

    # 第二层: 尝试缓存
    cached = _get_cache(cache_key)
    if cached:
        return {**cached, "_from_cache": True}

    # 第三层: 规则引擎降级
    return _rule_engine_fallback(icao)


# ==================== 并行工具 ====================


class FetchWeatherParallelParams(BaseModel):
    """并行获取机场的METAR+解析+风险评估，一步到位"""

    icao: str = Field(description="4字母ICAO机场代码，如 ZBAA、ZSPD")
    fetch_taf: bool = Field(
        default=False,
        description="是否同时获取TAF预报。适合需要分析趋势的场景。",
    )


@observable_tool("fetch_weather_parallel", FetchWeatherParallelParams)
async def _fetch_weather_parallel(params: FetchWeatherParallelParams) -> Dict[str, Any]:
    """
    并行获取完整气象数据: METAR + 解析 + 风险评估 (+ 可选 TAF)

    使用 asyncio.gather 并行执行多个独立操作，减少总延迟。
    当任何操作失败时自动降级到缓存/规则引擎。
    """
    icao = params.icao.upper()

    async def _do_fetch_metar():
        return await _fetch_with_fallback(icao, _do_metar_fetch_inner)

    async def _do_metar_fetch_inner(icao_code):
        from app.services.metar_fetcher import fetch_metar_for_airport
        raw, meta = await fetch_metar_for_airport(icao_code)
        return {"raw_metar": raw, "metadata": meta}

    async def _do_parse(raw_metar: str):
        state = {"metar_raw": raw_metar}
        result = await parse_metar_node(state, None)
        if result.get("parse_error"):
            return {"error": f"解析失败: {result['parse_error']}"}
        return {"metar_parsed": result.get("metar_parsed", {}), "parse_success": result.get("parse_success", False)}

    async def _do_risk(metar_parsed: Dict):
        state = {"metar_parsed": metar_parsed}
        result = await assess_risk_node(state, None)
        return {
            "risk_level": result.get("risk_level", "LOW"),
            "risk_factors": result.get("risk_factors", []),
        }

    async def _do_taf():
        if not params.fetch_taf:
            return None
        try:
            from app.services.metar_fetcher import fetch_taf_for_airport
            raw, meta = await fetch_taf_for_airport(icao)
            return {"raw_taf": raw, "metadata": meta}
        except Exception as e:
            return {"error": f"TAF获取失败: {e}"}

    result = {"icao": icao}

    # 第一步: 获取 METAR (可能降级)
    metar_result = await _fetch_with_fallback(icao, _do_metar_fetch_inner)
    raw_metar = metar_result.get("raw_metar", "")
    result["metar"] = metar_result

    if metar_result.get("fallback"):
        result["parse"] = {"error": "无METAR数据，跳过解析"}
        result["risk"] = {"error": "无METAR数据，跳过风险评估"}
        if params.fetch_taf:
            result["taf"] = await _do_taf()
        return result

    # 第二步: 并行执行解析 + TAF
    parse_task = _do_parse(raw_metar)
    taf_task = _do_taf() if params.fetch_taf else asyncio.sleep(0)

    results = await asyncio.gather(parse_task, taf_task, return_exceptions=True)

    parse_result = results[0] if not isinstance(results[0], Exception) else {"error": str(results[0])}
    result["parse"] = parse_result

    if params.fetch_taf:
        taf_result = results[1] if not isinstance(results[1], Exception) else {"error": str(results[1])}
        result["taf"] = taf_result

    # 第三步: 风险评估 (依赖解析结果)
    metar_parsed = parse_result.get("metar_parsed")
    if metar_parsed:
        risk_result = await _do_risk(metar_parsed)
        result["risk"] = risk_result
    else:
        result["risk"] = {"error": "无解析数据，跳过风险评估"}

    return result


# ==================== Tool 注册表 ====================

TOOL_REGISTRY = {
    "fetch_weather_parallel": {
        "function": _fetch_weather_parallel,
        "schema": FetchWeatherParallelParams,
        "description": "并行获取机场的完整气象数据(METAR+解析+风险评估)。一步到位，比分别调用fetch_metar/parse_metar/assess_risk更快。推荐用于需要综合分析的场景。支持TAF预报(设置fetch_taf=true)。",
    },
    "fetch_metar": {
        "function": _fetch_metar,
        "schema": FetchMetarParams,
        "description": "获取指定ICAO机场的实时METAR报文。输入4字母机场代码，返回原始METAR文本和元数据。",
    },
    "parse_metar": {
        "function": _parse_metar,
        "schema": ParseMetarParams,
        "description": "解析原始METAR报文为结构化数据。包含飞行规则、风向风速、能见度、云层、温度、天气现象等。",
    },
    "get_flight_rules": {
        "function": _get_flight_rules,
        "schema": GetFlightRulesParams,
        "description": "根据能见度(km)和云底高(ft)计算ICAO Annex 3飞行规则(VFR/MVFR/IFR/LIFR)。FEW/SCT不算ceiling。",
    },
    "assess_risk": {
        "function": _assess_risk,
        "schema": AssessRiskParams,
        "description": "多维度风险评估。检查危险天气、风切变、低能见度(<1km=CRITICAL)、低云底高、强风等。",
    },
    "get_approach_minima": {
        "function": _get_approach_minima,
        "schema": GetApproachMinimaParams,
        "description": "获取机场指定跑道的进近最低标准(DH/MDA)。包含ILS CAT I/II/III和VOR进近。",
    },
    "format_visibility": {
        "function": _format_visibility,
        "schema": FormatVisibilityParams,
        "description": "将能见度精确值转换为区间化描述(如'6-10km')。对外展示用，避免暴露精确值。",
    },
    "fetch_taf": {
        "function": _fetch_taf,
        "schema": FetchTafParams,
        "description": "获取指定ICAO机场的TAF预报报文。返回原始TAF文本和结构化预报数据（各时段风、能见度、天气、云层）。",
    },
    "get_full_weather": {
        "function": _get_full_weather,
        "schema": GetFullWeatherParams,
        "description": "一次获取机场的METAR实况+TAF预报。适合需要联合分析当前天气和未来趋势的场景。METAR和TAF任一获取失败不会阻断另一个。",
    },
}


def get_all_tools() -> List[Dict[str, Any]]:
    """
    获取所有工具定义，适配 LangChain Tool 格式
    """
    from langchain_core.tools import StructuredTool

    tools = []
    for name, info in TOOL_REGISTRY.items():
        tool = StructuredTool(
            name=name,
            description=info["description"],
            args_schema=info["schema"],
            coroutine=info["function"],
            handle_tool_error=True,
        )
        tools.append(tool)

    return tools
