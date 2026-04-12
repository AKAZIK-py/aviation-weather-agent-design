"""
航空天气AI系统 - 幻觉检测模块
检测AI输出中的幻觉和错误信息
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Any, Optional, Set
import re


class Severity(Enum):
    """幻觉严重程度"""
    CRITICAL = -5   # 严重幻觉，可能导致安全事故
    MODERATE = -2   # 中等幻觉，影响决策质量
    MINOR = -1      # 轻微幻觉，影响较小


@dataclass
class HallucinationItem:
    """单个幻觉检测结果"""
    category: str           # 幻觉类别
    description: str        # 详细描述
    severity: Severity      # 严重程度
    system_output: Any      # AI系统的输出值
    golden_answer: Any      # 标准答案值
    impact: str             # 影响说明


@dataclass
class HallucinationReport:
    """幻觉检测报告"""
    total_items: int
    hallucination_count: int
    critical_count: int
    moderate_count: int
    minor_count: int
    penalty_score: float
    items: List[HallucinationItem] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)


class HallucinationDetector:
    """
    幻觉检测器
    检测AI输出中是否存在虚假信息、错误判断等幻觉现象
    """

    def __init__(self):
        """初始化幻觉检测器"""
        # 定义关键天气现象代码（这些现象的误判会导致严重后果）
        self.critical_phenomena = {
            "FG",    # 雾
            "TS",    # 雷暴
            "TSRA",  # 雷暴伴雨
            "+TSRA", # 强雷暴伴雨
            "GR",    # 冰雹
            "GS",    # 软雹
            "FC",    # 漏斗云/龙卷
            "SQ",    # 飑
            "SS",    # 沙暴
            "DS",    # 尘暴
        }

        # 定义飞行规则边界值
        self.flight_rule_thresholds = {
            "LIFR": {"visibility_min": 0, "visibility_max": 1600, "ceiling_min": 0, "ceiling_max": 500},
            "IFR": {"visibility_min": 1600, "visibility_max": 5000, "ceiling_min": 500, "ceiling_max": 1000},
            "MVFR": {"visibility_min": 5000, "visibility_max": 8000, "ceiling_min": 1000, "ceiling_max": 3000},
            "VFR": {"visibility_min": 8000, "visibility_max": 99999, "ceiling_min": 3000, "ceiling_max": 99999},
        }

        # 风险等级定义
        self.risk_levels = ["low", "medium", "high", "critical"]

    def detect(self, system_output: Dict[str, Any], golden_answer: Dict[str, Any]) -> HallucinationReport:
        """
        执行完整的幻觉检测

        Args:
            system_output: AI系统的输出
            golden_answer: 标准答案

        Returns:
            HallucinationReport: 幻觉检测报告
        """
        hallucinations: List[HallucinationItem] = []

        # 1. 检测虚构的天气数据
        hallucinations.extend(self._detect_invented_weather_data(system_output, golden_answer))

        # 2. 检测错误的飞行规则判断
        hallucinations.extend(self._detect_wrong_flight_rules(system_output, golden_answer))

        # 3. 检测虚假的天气现象
        hallucinations.extend(self._detect_fabricated_phenomena(system_output, golden_answer))

        # 4. 检测错误的风险评估
        hallucinations.extend(self._detect_wrong_risk_assessment(system_output, golden_answer))

        # 5. 检测虚假的建议
        hallucinations.extend(self._detect_fabricated_recommendations(system_output, golden_answer))

        # 生成报告
        critical_count = sum(1 for h in hallucinations if h.severity == Severity.CRITICAL)
        moderate_count = sum(1 for h in hallucinations if h.severity == Severity.MODERATE)
        minor_count = sum(1 for h in hallucinations if h.severity == Severity.MINOR)

        penalty_score = sum(h.severity.value for h in hallucinations)

        summary = {
            "has_critical_hallucination": critical_count > 0,
            "hallucination_rate": len(hallucinations) / max(1, len(hallucinations)),
            "penalty_score": penalty_score,
            "severity_breakdown": {
                "critical": critical_count,
                "moderate": moderate_count,
                "minor": minor_count
            }
        }

        return HallucinationReport(
            total_items=len(hallucinations),
            hallucination_count=len(hallucinations),
            critical_count=critical_count,
            moderate_count=moderate_count,
            minor_count=minor_count,
            penalty_score=penalty_score,
            items=hallucinations,
            summary=summary
        )

    def _detect_invented_weather_data(self, system_output: Dict[str, Any],
                                       golden_answer: Dict[str, Any]) -> List[HallucinationItem]:
        """
        检测虚构的天气数据
        当AI输出了标准答案中不存在的数据时，视为幻觉
        """
        hallucinations = []

        # 获取关键的天气元素
        expected_elements = golden_answer.get("key_weather_elements", {})
        actual_elements = system_output.get("key_weather_elements", {})

        # 检查能见度
        expected_vis = expected_elements.get("visibility_m")
        actual_vis = actual_elements.get("visibility_m")

        if expected_vis is not None and actual_vis is not None:
            # 检查是否虚构了极端值
            if expected_vis >= 9000 and actual_vis < 3000:
                # 标准答案是好能见度，但系统报告了很差能见度
                hallucinations.append(HallucinationItem(
                    category="虚构能见度数据",
                    description=f"系统报告能见度{actual_vis}m，但实际应为{expected_vis}m（良好能见度）",
                    severity=Severity.CRITICAL,
                    system_output=actual_vis,
                    golden_answer=expected_vis,
                    impact="可能导致飞行员错误判断飞行条件，引发安全事故"
                ))

            elif expected_vis < 3000 and actual_vis >= 9000:
                # 标准答案是很差能见度，但系统报告了好能见度
                hallucinations.append(HallucinationItem(
                    category="遗漏能见度警告",
                    description=f"系统未正确识别低能见度（实际{expected_vis}m，系统报告{actual_vis}m）",
                    severity=Severity.CRITICAL,
                    system_output=actual_vis,
                    golden_answer=expected_vis,
                    impact="未能识别危险天气条件，可能导致飞行员在恶劣条件下飞行"
                ))

        # 检查云底高
        expected_ceil = expected_elements.get("ceiling_ft")
        actual_ceil = actual_elements.get("ceiling_ft")

        if expected_ceil is not None and actual_ceil is not None:
            if expected_ceil >= 3000 and actual_ceil < 1000:
                hallucinations.append(HallucinationItem(
                    category="虚构云底高数据",
                    description=f"系统报告云底高{actual_ceil}ft，但实际应为{expected_ceil}ft",
                    severity=Severity.CRITICAL,
                    system_output=actual_ceil,
                    golden_answer=expected_ceil,
                    impact="错误的云底高判断可能导致飞行规则误判"
                ))

            elif expected_ceil is not None and expected_ceil < 1000 and actual_ceil is None:
                # 标准答案有低云，但系统未检测到
                hallucinations.append(HallucinationItem(
                    category="遗漏云底高警告",
                    description=f"系统未检测到低云（实际云底高{expected_ceil}ft）",
                    severity=Severity.CRITICAL,
                    system_output=None,
                    golden_answer=expected_ceil,
                    impact="未识别低云条件，可能导致飞行规则误判"
                ))

        # 检查风速
        expected_wind = expected_elements.get("wind_speed_kt")
        actual_wind = actual_elements.get("wind_speed_kt")

        if expected_wind is not None and actual_wind is not None:
            # 检查是否虚构了阵风
            expected_gust = expected_elements.get("wind_gust_kt")
            actual_gust = actual_elements.get("wind_gust_kt")

            if expected_gust is None and actual_gust is not None and actual_gust > 20:
                # 标准答案无阵风，但系统报告了强阵风
                hallucinations.append(HallucinationItem(
                    category="虚构阵风数据",
                    description=f"系统报告阵风{actual_gust}kt，但实际无阵风报告",
                    severity=Severity.MODERATE,
                    system_output=actual_gust,
                    golden_answer=expected_gust,
                    impact="虚假的阵风警告可能导致航班不必要的延误"
                ))

        return hallucinations

    def _detect_wrong_flight_rules(self, system_output: Dict[str, Any],
                                    golden_answer: Dict[str, Any]) -> List[HallucinationItem]:
        """
        检测错误的飞行规则判断
        这是关键安全问题
        """
        hallucinations = []

        expected_rules = golden_answer.get("flight_rules")
        actual_rules = system_output.get("flight_rules")

        if expected_rules and actual_rules:
            if expected_rules != actual_rules:
                # 判断错误的严重程度
                expected_idx = list(self.flight_rule_thresholds.keys()).index(expected_rules)
                actual_idx = list(self.flight_rule_thresholds.keys()).index(actual_rules)

                # 计算差距
                distance = abs(expected_idx - actual_idx)

                if distance >= 2:
                    # 跨度2级以上，例如VFR误判为IFR或反之
                    severity = Severity.CRITICAL
                    impact = "严重的飞行规则误判可能导致飞行员在不适飞条件下起飞"
                elif distance == 1:
                    severity = Severity.MODERATE
                    impact = "飞行规则判断偏差，可能影响飞行计划"
                else:
                    severity = Severity.MINOR
                    impact = "轻微的飞行规则判断偏差"

                hallucinations.append(HallucinationItem(
                    category="飞行规则误判",
                    description=f"系统判断为{actual_rules}，但实际应为{expected_rules}",
                    severity=severity,
                    system_output=actual_rules,
                    golden_answer=expected_rules,
                    impact=impact
                ))

        return hallucinations

    def _detect_fabricated_phenomena(self, system_output: Dict[str, Any],
                                      golden_answer: Dict[str, Any]) -> List[HallucinationItem]:
        """
        检测虚假的天气现象
        特别是危险天气现象的误报和漏报
        """
        hallucinations = []

        expected_elements = golden_answer.get("key_weather_elements", {})
        actual_elements = system_output.get("key_weather_elements", {})

        expected_phenomena = set(expected_elements.get("weather_phenomena", []))
        actual_phenomena = set(actual_elements.get("weather_phenomena", []))

        # 检测虚构的天气现象（误报）
        fabricated = actual_phenomena - expected_phenomena
        for phenomenon in fabricated:
            # 判断是否为危险天气现象
            if phenomenon in self.critical_phenomena:
                hallucinations.append(HallucinationItem(
                    category="虚构危险天气现象",
                    description=f"系统报告了{phenomenon}，但实际不存在此天气现象",
                    severity=Severity.CRITICAL,
                    system_output=phenomenon,
                    golden_answer=None,
                    impact="虚假的危险天气警告可能导致航班不必要的延误或取消"
                ))
            else:
                hallucinations.append(HallucinationItem(
                    category="虚构天气现象",
                    description=f"系统报告了{phenomenon}，但实际不存在此天气现象",
                    severity=Severity.MODERATE,
                    system_output=phenomenon,
                    golden_answer=None,
                    impact="虚假的天气现象可能影响飞行计划制定"
                ))

        # 检测遗漏的危险天气现象（漏报）
        missed_critical = expected_phenomena & self.critical_phenomena - actual_phenomena
        for phenomenon in missed_critical:
            hallucinations.append(HallucinationItem(
                category="遗漏危险天气现象",
                description=f"系统未报告{phenomenon}，但实际存在此危险天气",
                severity=Severity.CRITICAL,
                system_output=None,
                golden_answer=phenomenon,
                impact="遗漏危险天气警告可能导致飞行安全事故"
            ))

        return hallucinations

    def _detect_wrong_risk_assessment(self, system_output: Dict[str, Any],
                                       golden_answer: Dict[str, Any]) -> List[HallucinationItem]:
        """
        检测错误的风险评估
        """
        hallucinations = []

        expected_risk = golden_answer.get("risk_level")
        actual_risk = system_output.get("risk_level")

        if expected_risk and actual_risk:
            if expected_risk != actual_risk:
                expected_idx = self.risk_levels.index(expected_risk) if expected_risk in self.risk_levels else -1
                actual_idx = self.risk_levels.index(actual_risk) if actual_risk in self.risk_levels else -1

                if expected_idx >= 0 and actual_idx >= 0:
                    distance = abs(expected_idx - actual_idx)

                    if distance >= 2:
                        severity = Severity.CRITICAL
                        impact = "严重的风险评估错误可能导致决策失误"
                    elif distance == 1:
                        severity = Severity.MODERATE
                        impact = "风险评估偏差可能影响飞行计划"
                    else:
                        severity = Severity.MINOR
                        impact = "轻微的风险评估偏差"

                    hallucinations.append(HallucinationItem(
                        category="风险评估错误",
                        description=f"系统评估风险等级为{actual_risk}，但实际应为{expected_risk}",
                        severity=severity,
                        system_output=actual_risk,
                        golden_answer=expected_risk,
                        impact=impact
                    ))

        return hallucinations

    def _detect_fabricated_recommendations(self, system_output: Dict[str, Any],
                                            golden_answer: Dict[str, Any]) -> List[HallucinationItem]:
        """
        检测虚假的建议或解释
        """
        hallucinations = []

        # 检查是否有不应该出现的建议
        recommendations = system_output.get("recommendations", [])
        if isinstance(recommendations, list):
            for rec in recommendations:
                # 检查是否包含不合理的建议
                if isinstance(rec, str):
                    # 检查是否建议在恶劣天气下飞行
                    risk_level = golden_answer.get("risk_level", "")
                    if risk_level in ["high", "critical"]:
                        if any(keyword in rec for keyword in ["建议起飞", "可以飞行", "安全"]):
                            hallucinations.append(HallucinationItem(
                                category="危险建议",
                                description=f"在高风险天气条件下给出了不安全的建议：{rec}",
                                severity=Severity.CRITICAL,
                                system_output=rec,
                                golden_answer=f"风险等级: {risk_level}",
                                impact="可能误导飞行员在危险条件下飞行"
                            ))

        # 检查解释内容
        explanation = system_output.get("explanation", "")
        if isinstance(explanation, str) and len(explanation) > 0:
            # 检查是否包含明显的虚假陈述
            expected_elements = golden_answer.get("key_weather_elements", {})

            # 检查是否虚构了天气现象
            expected_phenomena = set(expected_elements.get("weather_phenomena", []))

            # 在解释中查找天气现象关键词
            for phenomenon in self.critical_phenomena:
                if phenomenon in explanation and phenomenon not in expected_phenomena:
                    hallucinations.append(HallucinationItem(
                        category="解释中包含虚假天气信息",
                        description=f"解释中提到了{phenomenon}，但实际不存在此天气现象",
                        severity=Severity.MODERATE,
                        system_output=explanation[:200],
                        golden_answer=list(expected_phenomena),
                        impact="错误的天气解释可能影响决策判断"
                    ))

        return hallucinations

    def get_hallucination_score(self, report: HallucinationReport) -> float:
        """
        计算幻觉评分（0-100分，越高越好）

        Args:
            report: 幻觉检测报告

        Returns:
            float: 幻觉评分
        """
        if report.total_items == 0:
            return 100.0

        # 基础分
        base_score = 100.0

        # 根据幻觉扣分
        for item in report.items:
            if item.severity == Severity.CRITICAL:
                base_score += item.severity.value  # -5
            elif item.severity == Severity.MODERATE:
                base_score += item.severity.value  # -2
            else:
                base_score += item.severity.value  # -1

        # 确保分数在0-100之间
        return max(0.0, min(100.0, base_score))
