"""
轻量自动评测模块 — Phase 1 规则判定

不需要调 LLM-as-Judge，仅基于关键词和启发式规则。
Phase 3 再升级为 LLM-as-Judge。
"""

import re
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# 关键气象信息关键词
_WEATHER_KEYWORDS = [
    "能见度",
    "visibility",
    "云底高",
    "ceiling",
    "风",
    "wind",
    "飞行规则",
    "flight_rules",
    "IFR",
    "VFR",
    "LIFR",
    "MVFR",
    "温度",
    "temperature",
    "露点",
    "dewpoint",
    "气压",
    "altimeter",
    "QNH",
    "RVR",
    "跑道视程",
]

# 结论性语言关键词
_CONCLUSION_KEYWORDS = [
    # 决策类
    "建议",
    "可以",
    "不宜",
    "需要",
    "注意",
    "适合",
    "不适合",
    "可以起飞",
    "可以降落",
    "能降",
    "能飞",
    "GO",
    "NO-GO",
    "CAUTION",
    "综合来看",
    "综上",
    "总的来说",
    "结论",
    "recommend",
    "suggest",
    "conclude",
    # 描述类 — Agent 用自然语言描述天气状态也算完成
    "良好",
    "正常",
    "条件",
    "天气",
    "能见度",
    "云底",
    "风向",
    "飞行规则",
    "VFR",
    "IFR",
    "LIFR",
    "MVFR",
    "CAVOK",
    "运行",
    "安全",
    "风险",
    "雷暴",
    "雾",
    "低能见",
]


def _count_key_info_hits(answer: str) -> tuple[int, int]:
    """统计回答中命中关键气象信息的数量。

    Returns:
        (hits, total) — 命中数 / 关键词总数
    """
    answer_lower = answer.lower()
    hits = 0
    for kw in _WEATHER_KEYWORDS:
        if kw.lower() in answer_lower:
            hits += 1
    return hits, len(_WEATHER_KEYWORDS)


def _has_conclusion(answer: str) -> bool:
    """检测回答是否包含结论性语言。"""
    for kw in _CONCLUSION_KEYWORDS:
        if kw in answer:
            return True
    return False


def _is_output_usable(answer: str, min_length: int = 50) -> bool:
    """检测输出是否合理可用（非空壳）。"""
    if not answer or not answer.strip():
        return False
    # 去掉空白后长度过短
    cleaned = re.sub(r"\s+", "", answer)
    if len(cleaned) < min_length:
        return False
    # 检测是否是模板式回复（全是 "N/A" / "无数据" 之类）
    template_patterns = [
        r"^(N/?A|无数据|暂无|未知|不清楚).{0,20}$",
        r"^.{0,30}$",  # 极短
    ]
    for pattern in template_patterns:
        if re.match(pattern, answer.strip(), re.IGNORECASE | re.DOTALL):
            return False
    return True


def _detect_hallucination(answer: str, tool_calls: List[Dict[str, Any]]) -> float:
    """简单幻觉检测。

    检查回答中是否提到了工具调用中不存在的机场/数据。
    Returns: 幻觉率 0.0 ~ 1.0
    """
    if not answer:
        return 0.0

    # 从 tool_calls 中提取实际查询的 ICAO 代码
    queried_icao: set[str] = set()
    for tc in tool_calls:
        args = tc.get("args", {})
        icao = args.get("icao") or args.get("airport_icao") or args.get("icao_code")
        if icao:
            queried_icao.add(icao.upper())

    # 如果没有工具调用，无法判断幻觉
    if not tool_calls:
        return 0.0

    # 提取回答中出现的所有 4 字母 ICAO 代码
    answer_upper = answer.upper()
    mentioned_icao = set(re.findall(r"\b[A-Z]{4}\b", answer_upper))

    # 过滤掉常见非 ICAO 的 4 字母缩写
    _NON_ICAO = {"JSON", "HTTP", "HTTPS", "HTML", "NULL", "TRUE", "FALSE", "N/A"}
    mentioned_icao -= _NON_ICAO

    # 如果提到了未查询过的 ICAO，记为幻觉
    if not queried_icao:
        return 0.0

    hallucinated = mentioned_icao - queried_icao
    if not hallucinated:
        return 0.0

    # 按比例计算（1个幻觉机场 = 0.5）
    rate = min(len(hallucinated) / len(mentioned_icao) if mentioned_icao else 0.0, 1.0)
    return round(rate, 2)


def evaluate_response(
    query: str,
    answer: str,
    role: str,
    tool_calls: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """轻量评测，返回 4 个指标。

    Args:
        query: 用户查询
        answer: Agent 的回答
        role: 用户角色
        tool_calls: 工具调用列表

    Returns:
        {
            "task_complete": bool,      — 回答是否包含结论性语言
            "key_info_hit": str,        — "命中数/总关键词数"
            "output_usable": bool,      — 输出长度是否合理
            "hallucination_rate": float — 0.0 ~ 1.0
        }
    """
    task_complete = _has_conclusion(answer)
    hits, total = _count_key_info_hits(answer)
    output_usable = _is_output_usable(answer)
    hallucination_rate = _detect_hallucination(answer, tool_calls)

    return {
        "task_complete": task_complete,
        "key_info_hit": f"{hits}/{total}",
        "output_usable": output_usable,
        "hallucination_rate": hallucination_rate,
    }
