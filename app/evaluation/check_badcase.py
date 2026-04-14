"""
Badcase 检查逻辑 — 自动判定 Agent 输出是否构成 badcase

三个核心检查器:
1. check_task_completed(output, query) -> bool
   用户问题是否被真正回答（不是只返回中间数据）

2. check_key_info(output, expected_key_info) -> float
   关键信息命中率 (0.0 ~ 1.0)

3. check_template(output) -> bool
   输出是否模板化严重

组合函数:
- evaluate_output(...) -> 一次跑完所有检查，返回完整评测结果
- auto_classify_badcase(...) -> 自动归类 badcase 类别

检查策略: 关键词 + 正则优先，LLM-judge 兜底（需外部注入）
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Callable, List

logger = logging.getLogger(__name__)


# ==================== 数据结构 ====================


@dataclass
class CheckResult:
    """单个检查项的结果。"""

    passed: bool
    score: float  # 0.0 ~ 1.0
    details: str = ""
    check_name: str = ""


@dataclass
class EvalResult:
    """完整评测结果。"""

    task_completed: CheckResult
    key_info_hit: CheckResult
    template_check: CheckResult
    is_badcase: bool
    categories: List[str] = field(default_factory=list)
    summary: str = ""


# ==================== 检查器 1: 任务完成 ====================

# 表示"未完成"的模式：只返回中间状态，没给结论
_INCOMPLETE_PATTERNS = [
    r"^报告生成中",
    r"^正在处理",
    r"^请稍等",
    r"^数据获取中",
    r"^加载中",
    r"^无数据",
    r"^无法获取",
    r"^未找到",
    r"^抱歉[，,]?(我)?无法",
    r"^Error[:\s]",
    r"^出错了",
]

# 表示"有结论"的模式：给出了建议或判断
_CONCLUSION_PATTERNS = [
    r"(建议|推荐|可以|不可以|能够|不能够|适合|不适合)",
    r"(GO|NO[- ]?GO|可行|不可行)",
    r"(可以降|不能降|可以飞|不能飞|可以起|不能起)",
    r"(条件[良好恶劣充足不足]|风险[高低])",
    r"(满足|不满足|达到|未达到|低于|高于|超出)",
    r"(安全|危险|注意|警惕|谨慎)",
    r"(VFR|MVFR|IFR|LIFR)\s*(条件|标准|天气)",
]

_INCOMPLETE_RE = [re.compile(p, re.IGNORECASE) for p in _INCOMPLETE_PATTERNS]
_CONCLUSION_RE = [re.compile(p, re.IGNORECASE) for p in _CONCLUSION_PATTERNS]


def check_task_completed(
    output: str,
    query: str = "",
    llm_judge: Callable[[str, str], bool] | None = None,
) -> CheckResult:
    """
    判断 Agent 是否完成了用户的问题。

    检查逻辑:
    1. 空输出 → 未完成
    2. 匹配"未完成"模式 → 未完成
    3. 匹配"有结论"模式 → 完成
    4. 输出长度 > 30 且含动词 → 倾向完成
    5. 兜底: 如果注入了 llm_judge，用 LLM 判断

    Args:
        output: Agent 输出文本
        query: 原始用户问题 (可选，供 LLM judge 使用)
        llm_judge: 可选的 LLM 判断函数 (output, query) -> bool

    Returns:
        CheckResult
    """
    output = (output or "").strip()

    # 空输出
    if not output:
        return CheckResult(
            passed=False, score=0.0, details="输出为空", check_name="task_completed"
        )

    # 长度太短
    if len(output) < 10:
        return CheckResult(
            passed=False,
            score=0.1,
            details=f"输出过短 ({len(output)} 字符)",
            check_name="task_completed",
        )

    # 匹配未完成模式
    for pattern in _INCOMPLETE_RE:
        if pattern.search(output):
            return CheckResult(
                passed=False,
                score=0.0,
                details=f"匹配未完成模式: {pattern.pattern}",
                check_name="task_completed",
            )

    # 匹配有结论模式
    conclusion_hits = sum(1 for p in _CONCLUSION_RE if p.search(output))
    if conclusion_hits >= 2:
        return CheckResult(
            passed=True,
            score=min(1.0, 0.6 + conclusion_hits * 0.1),
            details=f"命中 {conclusion_hits} 个结论模式",
            check_name="task_completed",
        )

    if conclusion_hits == 1:
        # 只命中一个，可能只是提到了术语，不算强结论
        return CheckResult(
            passed=True,
            score=0.6,
            details="命中 1 个结论模式，置信度中等",
            check_name="task_completed",
        )

    # 长度足够但没有匹配到结论模式 → 灰区
    if len(output) > 50:
        # 有动词结构，可能是描述性回答
        action_verbs = re.findall(
            r"(分析|评估|判断|提供|说明|建议|推荐|指出|提示)", output
        )
        if action_verbs:
            return CheckResult(
                passed=True,
                score=0.5,
                details=f"输出较长但结论信号弱 (动词: {action_verbs[:3]})",
                check_name="task_completed",
            )

    # 兜底: LLM judge
    if llm_judge is not None:
        try:
            passed = llm_judge(output, query)
            return CheckResult(
                passed=passed,
                score=0.8 if passed else 0.2,
                details="LLM judge 判定",
                check_name="task_completed",
            )
        except Exception as exc:
            logger.warning("LLM judge 调用失败: %s", exc)

    # 无法确定 → 偏向不通过
    return CheckResult(
        passed=False,
        score=0.3,
        details="未匹配任何完成信号，且无 LLM judge 兜底",
        check_name="task_completed",
    )


# ==================== 检查器 2: 关键信息命中 ====================


def _normalize_text(text: str) -> str:
    """文本标准化：去空格、小写化，用于宽松匹配。"""
    text = text.lower().strip()
    # 统一标点
    text = re.sub(r"[，,。.！!？?；;：:]", "", text)
    # 统一空格
    text = re.sub(r"\s+", "", text)
    return text


def _fuzzy_match(keyword: str, text: str) -> bool:
    """
    模糊匹配: 支持数值范围、单位变体等航空气象常见场景。

    例:
    - "能见度800m" 匹配 "能见度800米" / "能见度: 800m"
    - "云底高200ft" 匹配 "云底高 200 ft" / "CEILING 200FT"
    """
    norm_kw = _normalize_text(keyword)
    norm_text = _normalize_text(text)

    # 精确子串匹配
    if norm_kw in norm_text:
        return True

    # 数值匹配: 提取数字部分
    nums_kw = re.findall(r"[\d.]+", keyword)
    if nums_kw:
        # 关键词中有数值：检查数值 + 周围关键词都出现
        # 例如 "能见度800m" → 关键词部分="能见度", 数值="800"
        kw_parts = re.split(r"[\d.]+", keyword)
        kw_parts = [p.strip() for p in kw_parts if p.strip()]

        all_parts_found = True
        for part in kw_parts:
            if _normalize_text(part) not in norm_text:
                all_parts_found = False
                break

        if all_parts_found and nums_kw:
            # 检查数值是否出现在文本中
            for num in nums_kw:
                if num in norm_text:
                    return True

    # 单位变体: m ↔ 米, ft ↔ 英尺, kt ↔ 节
    unit_variants = {
        "m": ["米", "meter", "meters"],
        "米": ["m", "meter", "meters"],
        "ft": ["英尺", "feet", "foot"],
        "英尺": ["ft", "feet", "foot"],
        "kt": ["节", "knot", "knots"],
        "节": ["kt", "knot", "knots"],
        "km": ["公里", "千米"],
        "公里": ["km", "千米"],
    }

    for base_unit, variants in unit_variants.items():
        if base_unit in norm_kw:
            for variant in variants:
                variant_kw = norm_kw.replace(base_unit, variant)
                if variant_kw in norm_text:
                    return True

    return False


def check_key_info(
    output: str,
    expected_key_info: List[str],
) -> CheckResult:
    """
    检查关键信息命中率。

    Args:
        output: Agent 输出
        expected_key_info: 期望命中的关键信息列表

    Returns:
        CheckResult, score = 命中数 / 总数
    """
    if not expected_key_info:
        return CheckResult(
            passed=True,
            score=1.0,
            details="无期望关键信息",
            check_name="key_info_hit",
        )

    output = output or ""
    hits = []
    misses = []

    for info in expected_key_info:
        if _fuzzy_match(info, output):
            hits.append(info)
        else:
            misses.append(info)

    hit_rate = len(hits) / len(expected_key_info)
    passed = hit_rate >= 0.6  # 命中 60% 以上算通过

    details_parts = []
    if hits:
        details_parts.append(f"命中: {hits}")
    if misses:
        details_parts.append(f"缺失: {misses}")
    details_parts.append(f"命中率: {hit_rate:.0%}")

    return CheckResult(
        passed=passed,
        score=hit_rate,
        details="; ".join(details_parts),
        check_name="key_info_hit",
    )


# ==================== 检查器 3: 模板化检测 ====================

# 模板化标记: 这些是旧版固定模板的特征栏目
_TEMPLATE_MARKERS = [
    r"【风险分析】",
    r"【建议措施】",
    r"【角色职责】",
    r"【核心职责】",
    r"【思维链路】",
    r"【输出格式】",
    r"【天气概况】",
    r"【飞行建议】",
    r"【结论】",
    r"## 风险分析",
    r"## 建议措施",
    r"## 角色职责",
    r"## 核心职责",
    r"### 风险分析",
    r"### 建议措施",
]

# 结构化模板特征: 固定的分节 + 符号模式
_STRUCTURAL_PATTERNS = [
    r"(?m)^[\s]*[【\[][^】\]]+[】\]][\s]*$",  # 独行的【xxx】标题
    r"(?m)^[\s]*#{1,3}\s+.+$",  # Markdown 标题行 (连续多个)
    r"(?m)^[\s]*[-*]\s+\*\*[^*]+\*\*[:：]",  # - **标题**: 内容 的列表
]

# 重复性短语 (套话)
_CANNED_PHRASES = [
    r"根据METAR报文分析",
    r"综合以上分析",
    r"综上所述",
    r"以下是.*分析结果",
    r"以下是.*建议",
    r"以下是.*评估",
    r"基于以上数据",
    r"根据当前气象条件",
    r"请参考以下",
    r"希望对您有所帮助",
    r"如有.*请随时",
    r"祝您飞行安全",
]

_TEMPLATE_RE = [re.compile(p, re.IGNORECASE) for p in _TEMPLATE_MARKERS]
_STRUCTURAL_RE = [re.compile(p, re.MULTILINE) for p in _STRUCTURAL_PATTERNS]
_CANNED_RE = [re.compile(p, re.IGNORECASE) for p in _CANNED_PHRASES]


def check_template(output: str) -> CheckResult:
    """
    检查输出是否模板化。

    模板化特征:
    1. 包含旧版固定栏目标记 (【风险分析】等)
    2. 结构化程度过高 (多个 Markdown 标题 + 固定列表)
    3. 包含套话短语

    评分逻辑:
    - 0.0 = 完全自然
    - 1.0 = 纯模板
    - passed = score < 0.5 (模板化程度低于 50%)
    """
    output = (output or "").strip()
    if not output:
        return CheckResult(
            passed=True, score=0.0, details="空输出", check_name="template_check"
        )

    signals = []
    template_score = 0.0

    # 1. 检查固定栏目标记
    marker_hits = []
    for pattern in _TEMPLATE_RE:
        if pattern.search(output):
            marker_hits.append(pattern.pattern)

    if marker_hits:
        # 每个标记命中加 0.15，上限 0.5
        marker_score = min(0.5, len(marker_hits) * 0.15)
        template_score += marker_score
        signals.append(f"固定栏目标记命中 {len(marker_hits)} 个")

    # 2. 检查结构化特征
    structural_hits = 0
    for pattern in _STRUCTURAL_RE:
        structural_hits += len(pattern.findall(output))

    if structural_hits >= 4:
        struct_score = min(0.3, structural_hits * 0.05)
        template_score += struct_score
        signals.append(f"结构化行数: {structural_hits}")

    # 3. 检查套话
    canned_hits = []
    for pattern in _CANNED_RE:
        if pattern.search(output):
            canned_hits.append(pattern.pattern)

    if canned_hits:
        canned_score = min(0.2, len(canned_hits) * 0.05)
        template_score += canned_score
        signals.append(f"套话命中 {len(canned_hits)} 个")

    template_score = min(1.0, template_score)
    is_template = template_score >= 0.5

    details = f"模板化分数: {template_score:.2f}"
    if signals:
        details += f" | 信号: {'; '.join(signals)}"

    return CheckResult(
        passed=not is_template,
        score=template_score,
        details=details,
        check_name="template_check",
    )


# ==================== 组合函数 ====================


def evaluate_output(
    output: str,
    query: str = "",
    expected_key_info: List[str] | None = None,
    must_not_contain: List[str] | None = None,
    llm_judge: Callable[[str, str], bool] | None = None,
) -> EvalResult:
    """
    一次性跑完所有检查，返回完整评测结果。

    Args:
        output: Agent 输出
        query: 用户原始问题
        expected_key_info: 期望关键信息列表
        must_not_contain: 输出中不应包含的内容
        llm_judge: 可选的 LLM 判断函数

    Returns:
        EvalResult
    """
    # 检查 1: 任务完成
    task_result = check_task_completed(output, query, llm_judge=llm_judge)

    # 检查 2: 关键信息命中
    key_info_result = check_key_info(output, expected_key_info or [])

    # 检查 3: 模板化
    template_result = check_template(output)

    # 检查 4: 禁止内容
    forbidden_violations = []
    if must_not_contain:
        for item in must_not_contain:
            if item.lower() in (output or "").lower():
                forbidden_violations.append(item)

    # 归类 badcase
    categories = []
    if not task_result.passed:
        categories.append("task_not_finished")
    if not key_info_result.passed:
        categories.append("critical_info_missed")
    if not template_result.passed:
        categories.append("output_too_template")
    if forbidden_violations:
        categories.append("critical_info_missed")

    is_badcase = len(categories) > 0

    # 生成摘要
    summary_parts = []
    if task_result.passed:
        summary_parts.append("任务完成")
    else:
        summary_parts.append(f"任务未完成: {task_result.details}")

    summary_parts.append(f"关键信息命中率: {key_info_result.score:.0%}")

    if template_result.passed:
        summary_parts.append("输出自然")
    else:
        summary_parts.append(f"模板化({template_result.score:.0%})")

    if forbidden_violations:
        summary_parts.append(f"包含禁止内容: {forbidden_violations}")

    return EvalResult(
        task_completed=task_result,
        key_info_hit=key_info_result,
        template_check=template_result,
        is_badcase=is_badcase,
        categories=categories,
        summary=" | ".join(summary_parts),
    )


def auto_classify_badcase(eval_result: EvalResult) -> str:
    """
    根据评测结果自动归类 badcase 类别。

    优先级: task_not_finished > hallucination > critical_info_missed > output_too_template > other

    Returns:
        分类字符串 (对应 schema.json 的 enum)
    """
    categories = eval_result.categories
    if not categories:
        return "other"

    priority = [
        "task_not_finished",
        "hallucination",
        "critical_info_missed",
        "output_too_template",
    ]

    for cat in priority:
        if cat in categories:
            return cat

    return "other"
