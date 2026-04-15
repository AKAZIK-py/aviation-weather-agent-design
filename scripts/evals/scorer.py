#!/usr/bin/env python3
"""
航空气象Agent评测打分引擎

纯脚本逻辑，不调LLM。提供4个核心打分函数:
  - check_task_completed(output, query) -> dict
  - check_key_info(output, expected_key_info) -> dict
  - check_template(output) -> dict
  - check_safety(output, case) -> dict
  - score_case(case, output) -> dict  (汇总函数，被 run_eval.py 调用)
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


# ==========================================================================
# 1. 任务完成率检测
# ==========================================================================

# 未完成模式: 输出中出现这些关键词说明任务没有真正完成
_INCOMPLETE_PATTERNS = [
    r"报告生成中",
    r"正在生成",
    r"请稍[后候等]",
    r"处理中[.。…]",
    r"加载中",
    r"数据获取中",
    r"暂时无法",
    r"无法[回答提供分析]",
    r"抱歉[，,].*无法",
    r"我不[能确定可以]",
]

# 结论模式: 输出中出现这些说明给出了明确结论
_CONCLUSION_PATTERNS = [
    r"建议.*(?:起飞|降落|备降|等待|推迟|取消|绕飞|返航)",
    r"(?:可以|不能|不可以|建议|不建议).{0,6}(?:降[落]|起飞|飞行|执行)",
    r"(?:GO|NO[\s-]?GO|GO[\s-]?AHEAD)",
    r"满足.*(?:标准|条件|要求)",
    r"不满足.*(?:标准|条件|要求)",
    r"(?:低于|高于|达到|超过).{0,10}(?:标准|最低|CAT)",
    r"(?:CRITICAL|WARNING|CAUTION|危险|警告|注意)",
    r"(?:安全|不安全|风险[较]?[高低大])",
    r"(?:推荐|不推荐|不建议|强烈建议)",
    r"(?:可以飞|不能飞|不宜飞|适合飞)",
    r"(?:符合|不符合).{0,6}(?:运行|起降|进近).{0,4}(?:标准|条件)",
    r"(?:天气|气象).{0,6}(?:良好|恶劣|不佳|好转|恶化)",
]


def check_task_completed(output: str, query: str = "") -> Dict[str, Any]:
    """
    检测Agent输出是否真正回答了用户的问题。

    不是只返回了数据就算完成，必须有结论。
    识别"报告生成中"等未完成模式 -> False
    识别"建议/GO/可以降/不能飞/满足"等结论模式 -> True

    Returns:
        {"passed": bool, "confidence": float, "reason": str}
    """
    if not output or not output.strip():
        return {"passed": False, "confidence": 0.95, "reason": "输出为空"}

    text = output.strip()

    # 检查未完成模式
    for pat in _INCOMPLETE_PATTERNS:
        if re.search(pat, text):
            return {
                "passed": False,
                "confidence": 0.9,
                "reason": f"检测到未完成模式: {pat}",
            }

    # 检查结论模式
    conclusion_hits = []
    for pat in _CONCLUSION_PATTERNS:
        if re.search(pat, text):
            conclusion_hits.append(pat)

    if conclusion_hits:
        # 有结论 -> 通过
        confidence = min(0.95, 0.6 + 0.1 * len(conclusion_hits))
        return {
            "passed": True,
            "confidence": round(confidence, 2),
            "reason": f"检测到{len(conclusion_hits)}个结论模式",
        }

    # 没有明确结论但输出有一定长度 -> 低置信度不通过
    if len(text) < 50:
        return {
            "passed": False,
            "confidence": 0.7,
            "reason": "输出过短且无明确结论",
        }

    # 输出较长但没有结论关键词 -> 中等置信度不通过
    return {
        "passed": False,
        "confidence": 0.5,
        "reason": "输出较长但未检测到明确结论",
    }


# ==========================================================================
# 2. 关键信息命中率
# ==========================================================================

# 单位变体映射: 支持 m↔米, ft↔英尺, kt↔节, km↔千米, SM↔英里
_UNIT_ALIASES: Dict[str, List[str]] = {
    "米": ["m", "meter", "meters"],
    "英尺": ["ft", "feet", "foot"],
    "节": ["kt", "kts", "knot", "knots"],
    "千米": ["km", "kilometer", "kilometers", "公里"],
    "英里": ["sm", "statute mile", "statute miles"],
}

# 数值单位对: 用于模糊匹配, 如 800m ≈ 0.8km
_VALUE_UNIT_EQUIVALENTS = [
    # (value, from_unit_patterns, to_unit_patterns, factor)
    # 0.05km = 50m
    {
        "from_regex": r"0\.05\s*(?:km|千米|公里)",
        "to_regex": r"50\s*(?:m|米)",
        "factor": 1,
    },
    # 0.1km = 100m
    {
        "from_regex": r"0\.1\s*(?:km|千米|公里)",
        "to_regex": r"100\s*(?:m|米)",
        "factor": 1,
    },
    # 0.8km = 800m
    {
        "from_regex": r"0\.8\s*(?:km|千米|公里)",
        "to_regex": r"800\s*(?:m|米)",
        "factor": 1,
    },
    # 1km = 1000m
    {
        "from_regex": r"1\s*(?:km|千米|公里)",
        "to_regex": r"1000\s*(?:m|米)",
        "factor": 1,
    },
    # 1.5km = 1500m
    {
        "from_regex": r"1\.5\s*(?:km|千米|公里)",
        "to_regex": r"1500\s*(?:m|米)",
        "factor": 1,
    },
    # 3km = 3000m
    {
        "from_regex": r"3\s*(?:km|千米|公里)",
        "to_regex": r"3000\s*(?:m|米)",
        "factor": 1,
    },
    # 10km = 10000m
    {
        "from_regex": r"10\s*(?:km|千米|公里)",
        "to_regex": r"10000\s*(?:m|米)",
        "factor": 1,
    },
]

# 提取数值+单位的正则
_NUM_UNIT_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*"
    r"(m|米|km|千米|公里|ft|英尺|kt|节|kts|knots?|sm|英里|海里)",
    re.IGNORECASE,
)


def _normalize_text(s: str) -> str:
    """归一化文本: 统一全角/半角、小写化"""
    # 全角数字转半角
    table = str.maketrans("０１２３４５６７８９", "0123456789")
    s = s.translate(table)
    return s.lower()


def _fuzzy_match_value(expected: str, output: str) -> bool:
    """
    模糊数值匹配: 检查 expected 中的数值+单位是否在 output 中以等价形式出现。
    """
    exp_norm = _normalize_text(expected)
    out_norm = _normalize_text(output)

    # 提取 expected 中的数值+单位对
    exp_matches = _NUM_UNIT_RE.findall(exp_norm)
    if not exp_matches:
        # 没有数值+单位, 回退到简单包含匹配
        return False

    for val, unit in exp_matches:
        # 构造在 output 中的搜索模式
        val_float = float(val)
        patterns = []

        # 原始值
        patterns.append(
            rf"{re.escape(val)}\s*(?:{re.escape(unit)}|{_unit_variants_pattern(unit)})"
        )

        # 单位换算变体
        if unit in ("km", "千米", "公里"):
            meters = val_float * 1000
            if meters == int(meters):
                patterns.append(rf"{int(meters)}\s*(?:m|米)")
            else:
                patterns.append(rf"{meters}\s*(?:m|米)")
        elif unit in ("m", "米"):
            km = val_float / 1000
            if km == int(km):
                patterns.append(rf"{int(km)}\s*(?:km|千米|公里)")
            else:
                patterns.append(rf"{km}\s*(?:km|千米|公里)")

        # 尝试匹配
        matched = False
        for pat in patterns:
            if re.search(pat, out_norm):
                matched = True
                break
        if not matched:
            return False

    return True


def _unit_variants_pattern(unit: str) -> str:
    """返回单位的变体正则片段"""
    for canonical, aliases in _UNIT_ALIASES.items():
        if unit == canonical or unit in aliases:
            all_forms = [re.escape(canonical)] + [re.escape(a) for a in aliases]
            return "|".join(all_forms)
    return re.escape(unit)


# 语义关键词映射: expected_key_info → 输出中可能出现的等价表述
_SEMANTIC_EXPANSIONS = {
    "能见度良好": ["能见度", "目视", "vis", "visibility", "6-10", "10km", "良好", "极佳", "优秀", "好"],
    "能见度中等": ["能见度", "目视", "vis", "4000", "5000", "3km", "4km", "5km", "中等"],
    "能见度极差": ["能见度", "低能见度", "雾", "fg", "0400", "0800", "极差", "很差"],
    "云层较高": ["云", "cloud", "散云", "few", "sct", "4000", "5000", "高", "充足"],
    "云底高偏低": ["云", "cloud", "bkn", "ovc", "008", "010", "低云", "偏低"],
    "VFR条件": ["vfr", "目视飞行", "能见度良好", "目视条件"],
    "MVFR": ["mvfr", "边缘", "注意", "marginal"],
    "IFR条件": ["ifr", "仪表飞行", "低能见度", "低云"],
    "LIFR条件": ["lifr", "极差", "条件差", "备降", "改航"],
    "条件极差": ["极差", "很差", "恶劣", "危险", "备降", "改航", "不能降"],
}


def _semantic_match(keyword: str, output: str) -> bool:
    """
    语义级关键词匹配。
    当精确包含匹配失败时，检查输出中是否包含该关键词的语义等价表述。
    """
    kw_lower = keyword.lower().strip()
    out_lower = output.lower()

    # 直接查找映射
    if kw_lower in _SEMANTIC_EXPANSIONS:
        for synonym in _SEMANTIC_EXPANSIONS[kw_lower]:
            if synonym.lower() in out_lower:
                return True

    # 关键词的部分匹配: 将关键词拆成子词，至少命中一半
    subwords = [w for w in re.split(r'[\s/,，、]+', kw_lower) if len(w) >= 2]
    if subwords:
        matched = sum(1 for w in subwords if w in out_lower)
        if matched >= max(1, len(subwords) // 2):
            return True

    return False


def _keyword_in_output(keyword: str, output: str) -> bool:
    """
    检查单个关键词是否在输出中命中。
    支持: 数值模糊匹配、单位变体、语义扩展匹配。
    """
    kw_norm = _normalize_text(keyword)
    out_norm = _normalize_text(output)

    # 简单包含匹配
    if kw_norm in out_norm:
        return True

    # 数值模糊匹配
    if _NUM_UNIT_RE.search(kw_norm):
        return _fuzzy_match_value(keyword, output)

    # 语义扩展匹配
    if _semantic_match(keyword, output):
        return True

    return False


def check_key_info(
    output: str, expected_key_info: Optional[List[str]]
) -> Dict[str, Any]:
    """
    逐条比对 expected_key_info 是否在输出中被提到。

    支持单位变体: m↔米, ft↔英尺, kt↔节
    支持数值模糊匹配: 800≈0.8km

    Returns:
        {"hit_rate": float, "hits": int, "total": int, "missed": list}
    """
    if not expected_key_info:
        return {"hit_rate": 1.0, "hits": 0, "total": 0, "missed": []}

    hits = 0
    missed: List[str] = []

    for info in expected_key_info:
        if _keyword_in_output(info, output):
            hits += 1
        else:
            missed.append(info)

    total = len(expected_key_info)
    hit_rate = hits / total if total > 0 else 1.0

    return {
        "hit_rate": round(hit_rate, 4),
        "hits": hits,
        "total": total,
        "missed": missed,
    }


# ==========================================================================
# 3. 模板化检测
# ==========================================================================

# 旧版固定栏目标题
_TEMPLATE_SECTION_TITLES = [
    "【风险分析】",
    "【建议措施】",
    "【角色职责】",
    "【核心职责】",
    "【思维链路】",
    "【气象分析】",
    "【飞行建议】",
    "【安全评估】",
    "【决策建议】",
    "【执行建议】",
]

# 套话短语
_TEMPLATE_CATCHPHRASES = [
    r"作为资深",
    r"根据您的角色",
    r"以下是",
    r"首先[，,].*其次[，,].*最后",
    r"综上所述[，,]",
    r"总而言之[，,]",
    r"让我为您",
    r"我将[为帮]您",
    r"以下是我的[分析建议评估]",
    r"分[析评]结果如下",
    r"我来为您",
    r"我来[帮为]您",
    r"现在让我",
    r"接下来[，,]",
    r"根据METAR报文[分析解读]",
    r"基于当前",
]

# Markdown 标题模式 (## 或 **加粗标题：**)
_TEMPLATE_MD_HEADERS_RE = re.compile(
    r"(?:^|\n)\s*(?:##\s+\S|\*\*[^*]{2,30}[:：]\*\*)",
    re.MULTILINE,
)

# 连续【xxx】标题的正则
_CONSECUTIVE_BRACKET_TITLES_RE = re.compile(r"(?:【[^】]+】\s*){3,}")

# 连续 markdown 加粗标题 (3个以上)
_CONSECUTIVE_BOLD_HEADERS_RE = re.compile(r"(?:\*\*[^*]{2,30}[:：]\*\*\s*\n?){3,}")


def check_template(output: str) -> Dict[str, Any]:
    """
    检测输出是否在套固定模板。

    - 旧版固定栏目: 【风险分析】【建议措施】等
    - 结构化特征: 连续3个以上【xxx】格式标题
    - 套话短语: "作为资深""根据您的角色""以下是"

    Returns:
        {"is_template": bool, "score": float, "reasons": list}
    """
    if not output or not output.strip():
        return {"is_template": False, "score": 0.0, "reasons": ["输出为空"]}

    reasons: List[str] = []
    template_score = 0.0

    # 检查固定栏目标题
    section_hits = []
    for title in _TEMPLATE_SECTION_TITLES:
        if title in output:
            section_hits.append(title)
    if section_hits:
        reasons.append(f"包含固定栏目: {', '.join(section_hits[:3])}")
        template_score += 0.3 * min(len(section_hits), 3) / 3

    # 检查连续【xxx】标题
    if _CONSECUTIVE_BRACKET_TITLES_RE.search(output):
        reasons.append("包含连续3个以上【xxx】标题")
        template_score += 0.4

    # 检查连续 **加粗标题：** (3个以上)
    if _CONSECUTIVE_BOLD_HEADERS_RE.search(output):
        reasons.append("包含连续3个以上**加粗标题**")
        template_score += 0.4

    # 检查 ## markdown 标题 (2个以上)
    md_headers = _TEMPLATE_MD_HEADERS_RE.findall(output)
    if len(md_headers) >= 2:
        reasons.append(f"包含{len(md_headers)}个markdown标题")
        template_score += 0.2 * len(md_headers)

    # 检查套话短语
    cliche_hits = []
    for pat in _TEMPLATE_CATCHPHRASES:
        if re.search(pat, output):
            cliche_hits.append(pat)
    if cliche_hits:
        reasons.append(f"包含套话短语: {len(cliche_hits)}处")
        template_score += 0.15 * min(len(cliche_hits), 3) / 3

    template_score = min(template_score, 1.0)
    is_template = template_score >= 0.4

    return {
        "is_template": is_template,
        "score": round(template_score, 4),
        "reasons": reasons,
    }


# ==========================================================================
# 4. 安全检查
# ==========================================================================

# CRITICAL 条件定义
_CRITICAL_CONDITIONS = [
    {
        "name": "visibility_below_1km",
        "description": "能见度<1km",
        "patterns": [
            r"能见度.{0,5}(?:0\.\d|[1-9])\s*(?:km|千米|公里)",
            r"能见度.{0,5}(?:[1-9]\d{0,2})\s*(?:m|米)",
            r"VIS\s*(?:<|less\s*than)\s*\d{1,3}(?:m|ft)?",
            r"(?:低于|不足|不到).{0,5}(?:1\s*km|1000\s*m|一千米|一公里)",
        ],
        "must_mark": ["CRITICAL", "RED", "红色", "危险", "严重警告", "⚠️", "🚨"],
    },
    {
        "name": "thunderstorm",
        "description": "雷暴天气",
        "patterns": [
            r"雷暴",
            r"TS(?:RA|SN|SH)?\b",
            r"CB\b",
            r"积雨云",
            r"雷[电雨]",
            r"thunderstorm",
        ],
        "must_mark": ["CRITICAL", "RED", "红色", "危险", "严重警告", "⚠️", "🚨"],
    },
    {
        "name": "windshear",
        "description": "风切变",
        "patterns": [
            r"风切变",
            r"windshear",
            r"wind\s*shear",
            r"WS\b",
            r"LLWS",
            r"低空风切变",
        ],
        "must_mark": ["CRITICAL", "RED", "红色", "危险", "严重警告", "⚠️", "🚨"],
    },
    {
        "name": "severe_turbulence",
        "description": "严重颠簸",
        "patterns": [
            r"严重颠簸",
            r"severe\s*turbulence",
            r"\bSEV\s*TURB\b",
        ],
        "must_mark": ["CRITICAL", "RED", "红色", "危险", "严重警告", "⚠️", "🚨"],
    },
    {
        "name": "volcanic_ash",
        "description": "火山灰",
        "patterns": [
            r"火山灰",
            r"volcanic\s*ash",
            r"\bVA\b",
        ],
        "must_mark": ["CRITICAL", "RED", "红色", "危险", "严重警告", "⚠️", "🚨"],
    },
]


def check_safety(output: str, case: Dict[str, Any]) -> Dict[str, Any]:
    """
    安全检查: CRITICAL风险是否被正确标记。

    通过解析METAR和case中的parsed信息来判断是否存在CRITICAL条件，
    然后检查输出中是否正确标记。

    Returns:
        {"passed": bool, "missed_criticals": list}
    """
    if not output or not output.strip():
        return {"passed": False, "missed_criticals": ["输出为空"]}

    # 从 case 中提取关键气象参数
    metar = case.get("metar", "")
    parsed = case.get("parsed", {})

    # 组合待检查文本: METAR + parsed 信息
    check_text = metar
    if parsed:
        # 添加 parsed 中的文本表示
        check_text += " " + _parsed_to_text(parsed)

    # 检查 case 是否存在 CRITICAL 条件
    active_criticals: List[Dict[str, Any]] = []
    for cond in _CRITICAL_CONDITIONS:
        found = False
        for pat in cond["patterns"]:
            if re.search(pat, check_text, re.IGNORECASE):
                found = True
                break
        # 额外检查 parsed 字段
        if not found and parsed:
            found = _check_critical_in_parsed(parsed, cond["name"])
        if found:
            active_criticals.append(cond)

    if not active_criticals:
        # case 本身没有 CRITICAL 条件, 通过
        return {"passed": True, "missed_criticals": []}

    # 有 CRITICAL 条件, 检查输出中是否正确标记
    missed_criticals = []
    for cond in active_criticals:
        marked = False
        for marker in cond["must_mark"]:
            if marker.lower() in output.lower():
                marked = True
                break
        if not marked:
            missed_criticals.append(cond["description"])

    return {
        "passed": len(missed_criticals) == 0,
        "missed_criticals": missed_criticals,
    }


def _parsed_to_text(parsed: Dict[str, Any]) -> str:
    """将 parsed dict 转为可搜索的文本表示。

    注意: 只输出对安全检查有意义的结构化信息，
    不输出"能见度XXXXkm"这种会被关键值正则误匹配的文本。
    能见度/云底高的安全判定由 _check_critical_in_parsed 负责。
    """
    parts = []

    for wx in parsed.get("present_weather", []):
        code = wx.get("code", "")
        desc = wx.get("description", "")
        parts.append(f"{code} {desc}")

    for cloud in parsed.get("cloud_layers", []):
        ctype = cloud.get("type", "")
        height = cloud.get("height_feet")
        if height is not None:
            parts.append(f"{ctype}{height}ft")

    fl = parsed.get("flight_rules", "")
    if fl:
        parts.append(fl)

    return " ".join(parts)


def _check_critical_in_parsed(parsed: Dict[str, Any], condition_name: str) -> bool:
    """基于 parsed 结构化数据检查 CRITICAL 条件"""
    if condition_name == "visibility_below_1km":
        vis = parsed.get("visibility")
        if vis is not None and vis < 1.0:
            return True

    if condition_name == "thunderstorm":
        for wx in parsed.get("present_weather", []):
            code = wx.get("code", "")
            if code in ("TS", "TSRA", "TSSN", "TSGR", "TSPL", "CB"):
                return True

    if condition_name == "windshear":
        # METAR 中的 WS 不常见于 parsed, 但检查一下
        return False  # 需要从原始 METAR 检查

    if condition_name == "severe_turbulence":
        return False  # 需要从 SIGMET 检查

    if condition_name == "volcanic_ash":
        return False

    return False


# ==========================================================================
# 5. 汇总函数: score_case
# ==========================================================================


def score_case(case: Dict[str, Any], output: str) -> Dict[str, Any]:
    """
    汇总函数，一次跑完所有打分项。

    注意: run_eval.py 调用方式为 score_fn(case, answer)，所以参数顺序为 (case, output)。

    Input: case dict (含 query, expected_key_info, scoring_criteria) + Agent输出
    Output: {
        "task_completed": bool,
        "key_info_hit_rate": float,
        "is_template": bool,
        "overall_score": float,
        "details": {
            "task_check": {...},
            "key_info": {...},
            "template_check": {...},
            "safety_check": {...},
        }
    }
    """
    query = case.get("query", "")
    expected_key_info = case.get("expected_key_info", [])

    # 1. 任务完成率
    task_result = check_task_completed(output, query)

    # 2. 关键信息命中率
    key_info_result = check_key_info(output, expected_key_info)

    # 3. 模板化检测
    template_result = check_template(output)

    # 4. 安全检查
    safety_result = check_safety(output, case)

    # 计算综合分数 (0-1)
    # 权重: 任务完成 40%, 关键信息 30%, 非模板 20%, 安全 10%
    task_score = 1.0 if task_result["passed"] else 0.0
    key_info_score = key_info_result["hit_rate"]
    template_score = 1.0 - template_result["score"]  # 非模板得分
    safety_score = 1.0 if safety_result["passed"] else 0.0

    overall_score = (
        0.40 * task_score
        + 0.30 * key_info_score
        + 0.20 * template_score
        + 0.10 * safety_score
    )

    return {
        "task_completed": task_result["passed"],
        "key_info_hit_rate": key_info_result["hit_rate"],
        "is_template": template_result["is_template"],
        "overall_score": round(overall_score, 4),
        "details": {
            "task_check": task_result,
            "key_info": key_info_result,
            "template_check": template_result,
            "safety_check": safety_result,
        },
    }
