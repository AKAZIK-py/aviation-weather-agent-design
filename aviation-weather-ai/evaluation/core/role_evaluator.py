"""
航空天气AI系统 - 角色适配评测模块
针对不同用户角色进行定制化评测
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Set
from enum import Enum


class UserRole(Enum):
    """用户角色"""
    ATC = "atc"              # 空管人员
    GROUND = "ground"        # 地勤人员
    OPERATIONS = "operations"  # 运控人员
    MAINTENANCE = "maintenance"  # 机务人员


@dataclass
class RoleConfig:
    """角色配置"""
    role: UserRole
    role_name: str  # 角色名称（中文）
    critical_info: List[str]  # 该角色关注的关键信息
    min_recall_rate: float  # 最低召回率要求
    dangerous_hallucinations: List[str]  # 对该角色最危险的幻觉类型


@dataclass
class RoleEvaluationResult:
    """角色适配评测结果"""
    role: UserRole
    role_name: str
    critical_info_recall: float  # 关键信息召回率
    dangerous_hallucination_count: int  # 危险幻觉数量
    overall_score: float  # 综合得分
    passed: bool  # 是否通过评测
    details: Dict[str, Any] = field(default_factory=dict)  # 详细信息


class RoleEvaluator:
    """
    角色适配评测器
    根据不同用户角色进行定制化评测
    """

    def __init__(self):
        """初始化角色评测器"""
        # 定义各角色的配置
        self.role_configs = {
            UserRole.ATC: RoleConfig(
                role=UserRole.ATC,
                role_name="空管人员",
                critical_info=[
                    "flight_rules",           # 飞行规则
                    "visibility_m",           # 能见度
                    "ceiling_ft",             # 云底高
                    "wind_speed_kt",          # 风速
                    "wind_gust_kt",           # 阵风
                    "weather_phenomena",      # 天气现象（特别是危险天气）
                    "risk_level",             # 风险等级
                ],
                min_recall_rate=0.95,  # 空管人员对信息准确性要求最高
                dangerous_hallucinations=[
                    "flight_rules",           # 飞行规则误判
                    "dangerous_phenomena",    # 危险天气现象误报/漏报
                    "visibility",             # 能见度误判
                    "ceiling",                # 云底高误判
                ]
            ),
            UserRole.GROUND: RoleConfig(
                role=UserRole.GROUND,
                role_name="地勤人员",
                critical_info=[
                    "visibility_m",           # 能见度（影响地面操作）
                    "weather_phenomena",      # 天气现象（雨雪等）
                    "wind_speed_kt",          # 风速（影响地面作业）
                    "wind_gust_kt",           # 阵风
                    "temperature",            # 温度（影响除冰等）
                    "risk_level",             # 风险等级
                ],
                min_recall_rate=0.90,
                dangerous_hallucinations=[
                    "wind_speed",             # 风速误判（影响地面安全）
                    "dangerous_phenomena",    # 危险天气现象
                ]
            ),
            UserRole.OPERATIONS: RoleConfig(
                role=UserRole.OPERATIONS,
                role_name="运控人员",
                critical_info=[
                    "flight_rules",           # 飞行规则
                    "visibility_m",           # 能见度
                    "ceiling_ft",             # 云底高
                    "weather_phenomena",      # 天气现象
                    "wind_speed_kt",          # 风速
                    "risk_level",             # 风险等级
                    "trend",                  # 趋势预报
                ],
                min_recall_rate=0.92,
                dangerous_hallucinations=[
                    "flight_rules",           # 飞行规则误判
                    "trend",                  # 趋势预报错误
                    "risk_level",             # 风险评估错误
                ]
            ),
            UserRole.MAINTENANCE: RoleConfig(
                role=UserRole.MAINTENANCE,
                role_name="机务人员",
                critical_info=[
                    "weather_phenomena",      # 天气现象（影响维修作业）
                    "temperature",            # 温度
                    "wind_speed_kt",          # 风速（影响户外维修）
                    "humidity",               # 湿度（影响维修条件）
                    "risk_level",             # 风险等级
                ],
                min_recall_rate=0.85,
                dangerous_hallucinations=[
                    "wind_speed",             # 风速误判
                    "temperature",            # 温度误判
                ]
            )
        }

        # 危险天气现象列表
        self.dangerous_phenomena = {
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
            "+RA",   # 大雨
            "+SN",   # 大雪
        }

    def evaluate_for_role(
        self,
        system_output: Dict[str, Any],
        golden_answer: Dict[str, Any],
        role: UserRole = UserRole.ATC
    ) -> RoleEvaluationResult:
        """
        针对特定角色进行评测

        Args:
            system_output: AI系统的输出
            golden_answer: 标准答案
            role: 用户角色

        Returns:
            RoleEvaluationResult: 角色适配评测结果
        """
        config = self.role_configs.get(role, self.role_configs[UserRole.ATC])

        # 1. 计算关键信息召回率
        critical_info_recall, recall_details = self._calculate_critical_info_recall(
            system_output, golden_answer, config
        )

        # 2. 检测危险幻觉
        dangerous_hallucination_count, hallucination_details = self._detect_dangerous_hallucinations(
            system_output, golden_answer, config
        )

        # 3. 计算综合得分
        # 召回率权重60%，危险幻觉惩罚40%
        recall_score = critical_info_recall * 60
        hallucination_penalty = dangerous_hallucination_count * 10  # 每个危险幻觉扣10分
        overall_score = max(0, recall_score - hallucination_penalty)

        # 4. 判断是否通过
        passed = (
            critical_info_recall >= config.min_recall_rate and
            dangerous_hallucination_count == 0
        )

        details = {
            "recall_details": recall_details,
            "hallucination_details": hallucination_details,
            "min_recall_required": config.min_recall_rate,
            "critical_info_items": config.critical_info
        }

        return RoleEvaluationResult(
            role=role,
            role_name=config.role_name,
            critical_info_recall=critical_info_recall,
            dangerous_hallucination_count=dangerous_hallucination_count,
            overall_score=overall_score,
            passed=passed,
            details=details
        )

    def _calculate_critical_info_recall(
        self,
        system_output: Dict[str, Any],
        golden_answer: Dict[str, Any],
        config: RoleConfig
    ) -> tuple:
        """
        计算关键信息召回率

        Args:
            system_output: AI系统输出
            golden_answer: 标准答案
            config: 角色配置

        Returns:
            tuple: (召回率, 详细信息)
        """
        expected_elements = golden_answer.get("key_weather_elements", {})
        predicted_elements = system_output.get("key_weather_elements", {})

        recall_results = {}
        total_items = 0
        correct_items = 0

        for info_key in config.critical_info:
            # 处理顶层信息（如flight_rules, risk_level）
            if info_key in ["flight_rules", "risk_level"]:
                expected_val = golden_answer.get(info_key)
                predicted_val = system_output.get(info_key)

                if expected_val is not None:
                    total_items += 1
                    if predicted_val == expected_val:
                        correct_items += 1
                        recall_results[info_key] = {"correct": True, "expected": expected_val, "predicted": predicted_val}
                    else:
                        recall_results[info_key] = {"correct": False, "expected": expected_val, "predicted": predicted_val}

            # 处理嵌套的天气元素信息
            elif info_key in expected_elements:
                expected_val = expected_elements.get(info_key)
                predicted_val = predicted_elements.get(info_key)

                if expected_val is not None:
                    total_items += 1

                    if isinstance(expected_val, list):
                        # 天气现象等列表类型
                        expected_set = set(expected_val)
                        predicted_set = set(predicted_val) if predicted_val else set()

                        if expected_set == predicted_set:
                            correct_items += 1
                            recall_results[info_key] = {"correct": True, "expected": expected_val, "predicted": predicted_val}
                        elif predicted_set >= expected_set:
                            # 预测包含所有期望项，但有多余（部分正确）
                            correct_items += 0.8
                            recall_results[info_key] = {"correct": "partial", "expected": expected_val, "predicted": predicted_val}
                        else:
                            recall_results[info_key] = {"correct": False, "expected": expected_val, "predicted": predicted_val}
                    else:
                        # 数值类型
                        if predicted_val is not None:
                            # 允许一定误差
                            if isinstance(expected_val, (int, float)) and isinstance(predicted_val, (int, float)):
                                # 相对误差容忍
                                tolerance = 0.1 if "visibility" in info_key or "ceiling" in info_key else 0.05
                                if abs(predicted_val - expected_val) / expected_val <= tolerance:
                                    correct_items += 1
                                    recall_results[info_key] = {"correct": True, "expected": expected_val, "predicted": predicted_val}
                                else:
                                    recall_results[info_key] = {"correct": False, "expected": expected_val, "predicted": predicted_val}
                            else:
                                if predicted_val == expected_val:
                                    correct_items += 1
                                    recall_results[info_key] = {"correct": True, "expected": expected_val, "predicted": predicted_val}
                                else:
                                    recall_results[info_key] = {"correct": False, "expected": expected_val, "predicted": predicted_val}
                        else:
                            recall_results[info_key] = {"correct": False, "expected": expected_val, "predicted": None}

        recall_rate = correct_items / total_items if total_items > 0 else 1.0

        return recall_rate, recall_results

    def _detect_dangerous_hallucinations(
        self,
        system_output: Dict[str, Any],
        golden_answer: Dict[str, Any],
        config: RoleConfig
    ) -> tuple:
        """
        检测对该角色最危险的幻觉

        Args:
            system_output: AI系统输出
            golden_answer: 标准答案
            config: 角色配置

        Returns:
            tuple: (危险幻觉数量, 详细信息)
        """
        hallucinations = []

        expected_elements = golden_answer.get("key_weather_elements", {})
        predicted_elements = system_output.get("key_weather_elements", {})

        for hallucination_type in config.dangerous_hallucinations:
            if hallucination_type == "flight_rules":
                # 检测飞行规则误判
                expected_rules = golden_answer.get("flight_rules")
                predicted_rules = system_output.get("flight_rules")

                if expected_rules and predicted_rules and expected_rules != predicted_rules:
                    hallucinations.append({
                        "type": "flight_rules_misjudgment",
                        "description": f"飞行规则误判：预期{expected_rules}，实际{predicted_rules}",
                        "severity": "critical"
                    })

            elif hallucination_type == "dangerous_phenomena":
                # 检测危险天气现象的误报/漏报
                expected_phenomena = set(expected_elements.get("weather_phenomena", []))
                predicted_phenomena = set(predicted_elements.get("weather_phenomena", []))

                # 漏报危险天气
                missed_dangerous = (expected_phenomena & self.dangerous_phenomena) - predicted_phenomena
                if missed_dangerous:
                    hallucinations.append({
                        "type": "missed_dangerous_phenomena",
                        "description": f"漏报危险天气现象：{missed_dangerous}",
                        "severity": "critical",
                        "details": list(missed_dangerous)
                    })

                # 误报危险天气
                false_dangerous = (predicted_phenomena & self.dangerous_phenomena) - expected_phenomena
                if false_dangerous:
                    hallucinations.append({
                        "type": "false_dangerous_phenomena",
                        "description": f"误报危险天气现象：{false_dangerous}",
                        "severity": "moderate",
                        "details": list(false_dangerous)
                    })

            elif hallucination_type in ["visibility", "ceiling", "wind_speed"]:
                # 检测数值参数的严重误判
                param_map = {
                    "visibility": "visibility_m",
                    "ceiling": "ceiling_ft",
                    "wind_speed": "wind_speed_kt"
                }

                param_key = param_map.get(hallucination_type)
                if param_key:
                    expected_val = expected_elements.get(param_key)
                    predicted_val = predicted_elements.get(param_key)

                    if expected_val is not None and predicted_val is not None:
                        # 检查是否严重误判（误差超过50%）
                        error_ratio = abs(predicted_val - expected_val) / expected_val
                        if error_ratio > 0.5:
                            hallucinations.append({
                                "type": f"{hallucination_type}_severe_error",
                                "description": f"{hallucination_type}严重误判：预期{expected_val}，实际{predicted_val}（误差{error_ratio*100:.1f}%）",
                                "severity": "critical",
                                "expected": expected_val,
                                "predicted": predicted_val,
                                "error_ratio": error_ratio
                            })

            elif hallucination_type == "risk_level":
                # 检测风险评估错误
                expected_risk = golden_answer.get("risk_level")
                predicted_risk = system_output.get("risk_level")

                if expected_risk and predicted_risk and expected_risk != predicted_risk:
                    # 判断是否低估了风险
                    risk_order = ["low", "medium", "high", "critical"]
                    try:
                        expected_idx = risk_order.index(expected_risk)
                        predicted_idx = risk_order.index(predicted_risk)

                        if predicted_idx < expected_idx:
                            # 低估风险
                            hallucinations.append({
                                "type": "risk_underestimation",
                                "description": f"低估风险等级：预期{expected_risk}，实际{predicted_risk}",
                                "severity": "critical"
                            })
                    except ValueError:
                        pass

            elif hallucination_type == "trend":
                # 检测趋势预报错误
                expected_trend = golden_answer.get("trend")
                predicted_trend = system_output.get("trend")

                if expected_trend and predicted_trend and expected_trend != predicted_trend:
                    hallucinations.append({
                        "type": "trend_forecast_error",
                        "description": f"趋势预报错误：预期{expected_trend}，实际{predicted_trend}",
                        "severity": "moderate"
                    })

        return len(hallucinations), hallucinations

    def evaluate_all_roles(
        self,
        system_output: Dict[str, Any],
        golden_answer: Dict[str, Any]
    ) -> Dict[UserRole, RoleEvaluationResult]:
        """
        对所有角色进行评测

        Args:
            system_output: AI系统输出
            golden_answer: 标准答案

        Returns:
            Dict[UserRole, RoleEvaluationResult]: 各角色的评测结果
        """
        results = {}

        for role in UserRole:
            results[role] = self.evaluate_for_role(system_output, golden_answer, role)

        return results

    def get_role_weighted_score(
        self,
        results: Dict[UserRole, RoleEvaluationResult]
    ) -> float:
        """
        计算角色加权得分

        Args:
            results: 各角色评测结果

        Returns:
            float: 加权得分
        """
        # 各角色权重（空管和运控更重要）
        weights = {
            UserRole.ATC: 0.35,
            UserRole.OPERATIONS: 0.30,
            UserRole.GROUND: 0.20,
            UserRole.MAINTENANCE: 0.15
        }

        total_score = 0.0
        for role, result in results.items():
            weight = weights.get(role, 0.25)
            total_score += result.overall_score * weight

        return total_score
