"""
航空天气AI系统 - 精确率/召回率计算模块
计算AI输出的精确率、召回率和F1分数
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple
import statistics


@dataclass
class MetricsResult:
    """评测指标结果"""
    precision: float
    recall: float
    f1_score: float
    true_positives: int
    false_positives: int
    false_negatives: int
    tolerance_used: Dict[str, float] = field(default_factory=dict)


@dataclass
class DimensionScores:
    """D1-D5各维度得分"""
    d1_boundary_identification: float  # D1: 边界天气识别能力
    d2_parameter_accuracy: float        # D2: 参数提取准确性
    d3_phenomena_detection: float       # D3: 天气现象检测
    d4_flight_rules_judgment: float     # D4: 飞行规则判断
    d5_risk_assessment: float           # D5: 风险评估
    overall_score: float                # 综合得分


class MetricsCalculator:
    """
    评测指标计算器
    计算精确率、召回率、F1分数等指标
    """

    def __init__(self):
        """初始化指标计算器"""
        # 定义各参数的容差范围
        self.tolerances = {
            "visibility": 0.10,    # 能见度 ±10%
            "ceiling": 0.10,       # 云底高 ±10%
            "wind_speed": 2.0,     # 风速 ±2节（绝对值）
            "wind_gust": 2.0,      # 阵风 ±2节（绝对值）
        }

        # 定义飞行规则边界值（用于边界天气检测）
        self.flight_rule_boundaries = {
            "visibility": {
                "IFR": 5000,       # 能见度<5000m为IFR边界
                "MVFR": 8000,      # 能见度<8000m为MVFR边界
            },
            "ceiling": {
                "IFR": 1000,       # 云底高<1000ft为IFR边界
                "MVFR": 3000,      # 云底高<3000ft为MVFR边界
            }
        }

    def calculate_precision_recall_f1(
        self,
        predicted: Dict[str, Any],
        expected: Dict[str, Any],
        tolerance: Optional[Dict[str, float]] = None
    ) -> MetricsResult:
        """
        计算精确率、召回率和F1分数

        Args:
            predicted: AI系统预测的结果
            expected: 标准答案
            tolerance: 自定义容差（可选）

        Returns:
            MetricsResult: 评测指标结果
        """
        # 合并默认容差和自定义容差
        tol = {**self.tolerances, **(tolerance or {})}

        true_positives = 0
        false_positives = 0
        false_negatives = 0

        # 1. 计算飞行规则的精确率/召回率
        if "flight_rules" in expected and "flight_rules" in predicted:
            expected_rules = expected["flight_rules"]
            predicted_rules = predicted["flight_rules"]

            if expected_rules == predicted_rules:
                true_positives += 1
            else:
                false_positives += 1
                false_negatives += 1

        # 2. 计算天气现象的精确率/召回率
        expected_elements = expected.get("key_weather_elements", {})
        predicted_elements = predicted.get("key_weather_elements", {})

        expected_phenomena = set(expected_elements.get("weather_phenomena", []))
        predicted_phenomena = set(predicted_elements.get("weather_phenomena", []))

        # 天气现象精确率/召回率
        if expected_phenomena or predicted_phenomena:
            tp_phenomena = len(expected_phenomena & predicted_phenomena)
            fp_phenomena = len(predicted_phenomena - expected_phenomena)
            fn_phenomena = len(expected_phenomena - predicted_phenomena)

            true_positives += tp_phenomena
            false_positives += fp_phenomena
            false_negatives += fn_phenomena

        # 3. 计算数值参数的精确率/召回率（考虑容差）
        numeric_params = ["visibility_m", "ceiling_ft", "wind_speed_kt", "wind_gust_kt"]

        for param in numeric_params:
            expected_val = expected_elements.get(param)
            predicted_val = predicted_elements.get(param)

            # 处理None值
            if expected_val is None and predicted_val is None:
                continue
            elif expected_val is None and predicted_val is not None:
                false_positives += 1
            elif expected_val is not None and predicted_val is None:
                false_negatives += 1
            else:
                # 都不为None，计算是否在容差范围内
                if self._is_within_tolerance(param, expected_val, predicted_val, tol):
                    true_positives += 1
                else:
                    false_positives += 1
                    false_negatives += 1

        # 4. 计算风险等级的精确率/召回率
        if "risk_level" in expected and "risk_level" in predicted:
            expected_risk = expected["risk_level"]
            predicted_risk = predicted["risk_level"]

            if expected_risk == predicted_risk:
                true_positives += 1
            else:
                false_positives += 1
                false_negatives += 1

        # 计算精确率、召回率、F1
        precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0.0
        recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0.0
        f1_score = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

        return MetricsResult(
            precision=precision,
            recall=recall,
            f1_score=f1_score,
            true_positives=true_positives,
            false_positives=false_positives,
            false_negatives=false_negatives,
            tolerance_used=tol
        )

    def _is_within_tolerance(
        self,
        param: str,
        expected: float,
        predicted: float,
        tolerance: Dict[str, float]
    ) -> bool:
        """
        判断预测值是否在容差范围内

        Args:
            param: 参数名
            expected: 标准值
            predicted: 预测值
            tolerance: 容差配置

        Returns:
            bool: 是否在容差范围内
        """
        # 确定容差类型和值
        if "visibility" in param:
            tol_value = tolerance.get("visibility", 0.10)
            # 百分比容差
            return abs(predicted - expected) / expected <= tol_value
        elif "ceiling" in param:
            tol_value = tolerance.get("ceiling", 0.10)
            # 百分比容差
            if expected == 0:
                return predicted == 0
            return abs(predicted - expected) / expected <= tol_value
        elif "wind" in param:
            tol_value = tolerance.get("wind_speed", 2.0)
            if "gust" in param:
                tol_value = tolerance.get("wind_gust", 2.0)
            # 绝对值容差
            return abs(predicted - expected) <= tol_value

        # 默认使用5%容差
        if expected == 0:
            return predicted == 0
        return abs(predicted - expected) / expected <= 0.05

    def calculate_d1_through_d5(self, all_results: List[Dict[str, Any]]) -> DimensionScores:
        """
        计算D1-D5各维度的得分

        Args:
            all_results: 所有测试结果列表，每个元素包含：
                - predicted: AI预测结果
                - expected: 标准答案
                - category: 天气类别（VFR/MVFR/IFR/LIFR/SEVERE）

        Returns:
            DimensionScores: 各维度得分
        """
        if not all_results:
            return DimensionScores(
                d1_boundary_identification=0.0,
                d2_parameter_accuracy=0.0,
                d3_phenomena_detection=0.0,
                d4_flight_rules_judgment=0.0,
                d5_risk_assessment=0.0,
                overall_score=0.0
            )

        # D1: 边界天气识别能力
        d1_scores = []
        for result in all_results:
            d1_score = self._calculate_d1_boundary_identification(
                result.get("predicted", {}),
                result.get("expected", {}),
                result.get("category", "")
            )
            d1_scores.append(d1_score)
        d1_avg = statistics.mean(d1_scores) if d1_scores else 0.0

        # D2: 参数提取准确性
        d2_scores = []
        for result in all_results:
            d2_score = self._calculate_d2_parameter_accuracy(
                result.get("predicted", {}),
                result.get("expected", {})
            )
            d2_scores.append(d2_score)
        d2_avg = statistics.mean(d2_scores) if d2_scores else 0.0

        # D3: 天气现象检测
        d3_scores = []
        for result in all_results:
            d3_score = self._calculate_d3_phenomena_detection(
                result.get("predicted", {}),
                result.get("expected", {})
            )
            d3_scores.append(d3_score)
        d3_avg = statistics.mean(d3_scores) if d3_scores else 0.0

        # D4: 飞行规则判断
        d4_scores = []
        for result in all_results:
            d4_score = self._calculate_d4_flight_rules_judgment(
                result.get("predicted", {}),
                result.get("expected", {})
            )
            d4_scores.append(d4_score)
        d4_avg = statistics.mean(d4_scores) if d4_scores else 0.0

        # D5: 风险评估
        d5_scores = []
        for result in all_results:
            d5_score = self._calculate_d5_risk_assessment(
                result.get("predicted", {}),
                result.get("expected", {})
            )
            d5_scores.append(d5_score)
        d5_avg = statistics.mean(d5_scores) if d5_scores else 0.0

        # 计算综合得分（加权平均）
        weights = {
            "d1": 0.25,  # 边界天气识别最重要
            "d2": 0.20,
            "d3": 0.20,
            "d4": 0.20,
            "d5": 0.15
        }

        overall_score = (
            weights["d1"] * d1_avg +
            weights["d2"] * d2_avg +
            weights["d3"] * d3_avg +
            weights["d4"] * d4_avg +
            weights["d5"] * d5_avg
        )

        return DimensionScores(
            d1_boundary_identification=d1_avg,
            d2_parameter_accuracy=d2_avg,
            d3_phenomena_detection=d3_avg,
            d4_flight_rules_judgment=d4_avg,
            d5_risk_assessment=d5_avg,
            overall_score=overall_score
        )

    def _calculate_d1_boundary_identification(
        self,
        predicted: Dict[str, Any],
        expected: Dict[str, Any],
        category: str
    ) -> float:
        """
        D1: 边界天气识别能力评分
        重点评估系统对边界天气条件的识别能力
        """
        # 边界天气包括：MVFR和IFR
        boundary_categories = {"MVFR", "IFR", "LIFR"}

        if category not in boundary_categories:
            # 非边界天气，检查是否误报
            expected_rules = expected.get("flight_rules", "")
            predicted_rules = predicted.get("flight_rules", "")

            # 正常天气不应被误判为边界天气
            if expected_rules in {"VFR"} and predicted_rules in boundary_categories:
                return 0.0  # 误报，得0分
            elif expected_rules == predicted_rules:
                return 100.0
            else:
                return 50.0  # 部分正确

        # 边界天气，检查识别准确性
        expected_elements = expected.get("key_weather_elements", {})
        predicted_elements = predicted.get("key_weather_elements", {})

        # 检查边界参数识别
        boundary_params_correct = 0
        boundary_params_total = 0

        # 检查能见度边界
        expected_vis = expected_elements.get("visibility_m")
        predicted_vis = predicted_elements.get("visibility_m")

        if expected_vis is not None:
            boundary_params_total += 1
            if predicted_vis is not None:
                if self._is_within_tolerance("visibility_m", expected_vis, predicted_vis, self.tolerances):
                    boundary_params_correct += 1

        # 检查云底高边界
        expected_ceil = expected_elements.get("ceiling_ft")
        predicted_ceil = predicted_elements.get("ceiling_ft")

        if expected_ceil is not None:
            boundary_params_total += 1
            if predicted_ceil is not None:
                if self._is_within_tolerance("ceiling_ft", expected_ceil, predicted_ceil, self.tolerances):
                    boundary_params_correct += 1

        # 计算边界参数识别准确率
        param_score = (boundary_params_correct / boundary_params_total * 100) if boundary_params_total > 0 else 100.0

        # 飞行规则判断占50%权重
        expected_rules = expected.get("flight_rules", "")
        predicted_rules = predicted.get("flight_rules", "")
        rules_score = 100.0 if expected_rules == predicted_rules else 0.0

        # 综合得分
        return param_score * 0.5 + rules_score * 0.5

    def _calculate_d2_parameter_accuracy(
        self,
        predicted: Dict[str, Any],
        expected: Dict[str, Any]
    ) -> float:
        """
        D2: 参数提取准确性评分
        评估数值参数的提取精度
        """
        expected_elements = expected.get("key_weather_elements", {})
        predicted_elements = predicted.get("key_weather_elements", {})

        # 要检查的参数列表
        params_to_check = [
            ("visibility_m", "visibility"),
            ("ceiling_ft", "ceiling"),
            ("wind_speed_kt", "wind_speed"),
            ("wind_gust_kt", "wind_gust")
        ]

        correct_params = 0
        total_params = 0

        for param_name, tol_key in params_to_check:
            expected_val = expected_elements.get(param_name)
            predicted_val = predicted_elements.get(param_name)

            if expected_val is not None:
                total_params += 1
                if predicted_val is not None:
                    if self._is_within_tolerance(param_name, expected_val, predicted_val, self.tolerances):
                        correct_params += 1

        return (correct_params / total_params * 100) if total_params > 0 else 100.0

    def _calculate_d3_phenomena_detection(
        self,
        predicted: Dict[str, Any],
        expected: Dict[str, Any]
    ) -> float:
        """
        D3: 天气现象检测评分
        评估天气现象的检测能力
        """
        expected_elements = expected.get("key_weather_elements", {})
        predicted_elements = predicted.get("key_weather_elements", {})

        expected_phenomena = set(expected_elements.get("weather_phenomena", []))
        predicted_phenomena = set(predicted_elements.get("weather_phenomena", []))

        if not expected_phenomena and not predicted_phenomena:
            # 两边都为空，正确
            return 100.0

        if not expected_phenomena:
            # 标准答案为空，但预测了现象（误报）
            return 0.0

        if not predicted_phenomena:
            # 预测为空，但标准答案有现象（漏报）
            return 0.0

        # 计算Jaccard相似度
        intersection = len(expected_phenomena & predicted_phenomena)
        union = len(expected_phenomena | predicted_phenomena)

        return (intersection / union * 100) if union > 0 else 100.0

    def _calculate_d4_flight_rules_judgment(
        self,
        predicted: Dict[str, Any],
        expected: Dict[str, Any]
    ) -> float:
        """
        D4: 飞行规则判断评分
        评估飞行规则判断的准确性
        """
        expected_rules = expected.get("flight_rules")
        predicted_rules = predicted.get("flight_rules")

        if not expected_rules or not predicted_rules:
            return 0.0

        if expected_rules == predicted_rules:
            return 100.0

        # 根据错误程度扣分
        rules_order = ["VFR", "MVFR", "IFR", "LIFR"]

        try:
            expected_idx = rules_order.index(expected_rules)
            predicted_idx = rules_order.index(predicted_rules)
            distance = abs(expected_idx - predicted_idx)

            # 差1级扣30分，差2级扣60分，差3级扣90分
            return max(0, 100 - distance * 30)
        except ValueError:
            return 0.0

    def _calculate_d5_risk_assessment(
        self,
        predicted: Dict[str, Any],
        expected: Dict[str, Any]
    ) -> float:
        """
        D5: 风险评估评分
        评估风险等级评估的准确性
        """
        expected_risk = expected.get("risk_level")
        predicted_risk = predicted.get("risk_level")

        if not expected_risk or not predicted_risk:
            return 0.0

        if expected_risk == predicted_risk:
            return 100.0

        # 根据错误程度扣分
        risk_order = ["low", "medium", "high", "critical"]

        try:
            expected_idx = risk_order.index(expected_risk)
            predicted_idx = risk_order.index(predicted_risk)
            distance = abs(expected_idx - predicted_idx)

            return max(0, 100 - distance * 30)
        except ValueError:
            return 0.0
