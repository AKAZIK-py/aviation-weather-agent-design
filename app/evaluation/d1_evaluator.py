"""
D1 评测维度细化模块
将 D1 解析准确率拆解为 6 个子维度进行独立评测
"""

from typing import Dict, Any


class D1DetailedEvaluator:
    """D1 详细评测器"""

    def __init__(self, tolerance: float = 0.1):
        """
        初始化评测器

        Args:
            tolerance: 数值比较的容差比例（默认 10%）
        """
        self.tolerance = tolerance

    def evaluate(
        self, parsed_data: Dict[str, Any], reference_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        执行完整的 D1 评测

        Args:
            parsed_data: 解析后的 METAR 数据
            reference_data: 参考标准数据

        Returns:
            评测报告字典
        """
        report = {
            "d1_overall": True,  # 总体通过状态
            "d1_sub_dimensions": {},
            "summary": {"total_sub_dimensions": 6, "passed": 0, "failed": 0},
        }

        # 执行各子维度评测
        d1_1_result = self.evaluate_visibility(parsed_data, reference_data)
        d1_2_result = self.evaluate_cloud_base(parsed_data, reference_data)
        d1_3_result = self.evaluate_wind(parsed_data, reference_data)
        d1_4_result = self.evaluate_weather_phenomena(parsed_data, reference_data)
        d1_5_result = self.evaluate_temperature_dewpoint(parsed_data, reference_data)
        d1_6_result = self.evaluate_flight_rules(parsed_data, reference_data)

        # 汇总结果
        sub_dimensions = {
            "D1.1_visibility": d1_1_result,
            "D1.2_cloud_base": d1_2_result,
            "D1.3_wind": d1_3_result,
            "D1.4_weather_phenomena": d1_4_result,
            "D1.5_temperature_dewpoint": d1_5_result,
            "D1.6_flight_rules": d1_6_result,
        }

        report["d1_sub_dimensions"] = sub_dimensions

        # 计算通过/失败数量
        passed_count = sum(1 for result in sub_dimensions.values() if result["passed"])
        failed_count = 6 - passed_count

        report["summary"]["passed"] = passed_count
        report["summary"]["failed"] = failed_count
        report["d1_overall"] = failed_count == 0

        return report

    def evaluate_visibility(
        self, parsed_data: Dict[str, Any], reference_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """D1.1: 能见度解析准确率"""
        parsed_vis = parsed_data.get("visibility")
        reference_vis = reference_data.get("visibility")

        if parsed_vis is None and reference_vis is None:
            return {"passed": True, "message": "两者都无能见度数据"}

        if parsed_vis is None or reference_vis is None:
            return {"passed": False, "message": "能见度数据缺失"}

        # 检查数值是否在容差范围内
        if self._is_within_tolerance(parsed_vis, reference_vis):
            return {
                "passed": True,
                "message": f"能见度匹配: {parsed_vis} ≈ {reference_vis} km",
            }
        else:
            return {
                "passed": False,
                "message": f"能见度不匹配: {parsed_vis} vs {reference_vis} km",
            }

    def evaluate_cloud_base(
        self, parsed_data: Dict[str, Any], reference_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """D1.2: 云底高解析准确率"""
        parsed_layers = parsed_data.get("cloud_layers", [])
        reference_layers = reference_data.get("cloud_layers", [])

        if not parsed_layers and not reference_layers:
            return {"passed": True, "message": "两者都无云层数据"}

        if len(parsed_layers) != len(reference_layers):
            return {
                "passed": False,
                "message": f"云层数量不匹配: {len(parsed_layers)} vs {len(reference_layers)}",
            }

        # 逐层比较
        for i, (parsed_layer, ref_layer) in enumerate(
            zip(parsed_layers, reference_layers)
        ):
            # 比较云层类型
            if parsed_layer.get("type") != ref_layer.get("type"):
                return {
                    "passed": False,
                    "message": f"第{i + 1}层云类型不匹配: {parsed_layer.get('type')} vs {ref_layer.get('type')}",
                }

            # 比较云底高度
            parsed_height = parsed_layer.get("height_feet")
            ref_height = ref_layer.get("height_feet")

            if parsed_height is None or ref_height is None:
                return {"passed": False, "message": f"第{i + 1}层云高度数据缺失"}

            if not self._is_within_tolerance(parsed_height, ref_height):
                return {
                    "passed": False,
                    "message": f"第{i + 1}层云高度不匹配: {parsed_height} vs {ref_height} ft",
                }

        return {"passed": True, "message": f"云层数据匹配，共{len(parsed_layers)}层"}

    def evaluate_wind(
        self, parsed_data: Dict[str, Any], reference_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """D1.3: 风速风向解析准确率"""
        # 风向比较
        parsed_dir = parsed_data.get("wind_direction")
        ref_dir = reference_data.get("wind_direction")

        # 风速比较
        parsed_speed = parsed_data.get("wind_speed")
        ref_speed = reference_data.get("wind_speed")

        # 阵风比较
        parsed_gust = parsed_data.get("wind_gust")
        ref_gust = reference_data.get("wind_gust")

        messages = []
        passed = True

        # 风向检查（允许 VRB 和具体度数的差异）
        if parsed_dir is None and ref_dir is None:
            messages.append("风向: 两者都无数据")
        elif parsed_dir is None or ref_dir is None:
            messages.append("风向: 数据缺失")
            passed = False
        elif parsed_dir == "VRB" or ref_dir == "VRB":
            # 如果任一为 VRB，另一个也应为 VRB 或 None
            if not (parsed_dir == "VRB" and (ref_dir == "VRB" or ref_dir is None)):
                messages.append(f"风向不匹配: {parsed_dir} vs {ref_dir}")
                passed = False
            else:
                messages.append("风向: VRB 匹配")
        else:
            # 比较具体度数（允许 ±10 度差异）
            if abs(parsed_dir - ref_dir) <= 10 or abs(parsed_dir - ref_dir) >= 350:
                messages.append(f"风向匹配: {parsed_dir}° ≈ {ref_dir}°")
            else:
                messages.append(f"风向不匹配: {parsed_dir}° vs {ref_dir}°")
                passed = False

        # 风速检查
        if parsed_speed is None and ref_speed is None:
            messages.append("风速: 两者都无数据")
        elif parsed_speed is None or ref_speed is None:
            messages.append("风速: 数据缺失")
            passed = False
        elif self._is_within_tolerance(parsed_speed, ref_speed):
            messages.append(f"风速匹配: {parsed_speed} ≈ {ref_speed} KT")
        else:
            messages.append(f"风速不匹配: {parsed_speed} vs {ref_speed} KT")
            passed = False

        # 阵风检查
        if parsed_gust is None and ref_gust is None:
            messages.append("阵风: 两者都无数据")
        elif parsed_gust is None or ref_gust is None:
            messages.append("阵风: 数据不一致（一个有，一个无）")
            passed = False
        elif self._is_within_tolerance(parsed_gust, ref_gust):
            messages.append(f"阵风匹配: {parsed_gust} ≈ {ref_gust} KT")
        else:
            messages.append(f"阵风不匹配: {parsed_gust} vs {ref_gust} KT")
            passed = False

        return {"passed": passed, "message": "; ".join(messages)}

    def evaluate_weather_phenomena(
        self, parsed_data: Dict[str, Any], reference_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """D1.4: 天气现象识别准确率"""
        parsed_weather = parsed_data.get("present_weather", [])
        reference_weather = reference_data.get("present_weather", [])

        if not parsed_weather and not reference_weather:
            return {"passed": True, "message": "两者都无天气现象"}

        if len(parsed_weather) != len(reference_weather):
            return {
                "passed": False,
                "message": f"天气现象数量不匹配: {len(parsed_weather)} vs {len(reference_weather)}",
            }

        # 提取天气代码进行比较
        parsed_codes = {w.get("code") for w in parsed_weather if w.get("code")}
        reference_codes = {w.get("code") for w in reference_weather if w.get("code")}

        if parsed_codes == reference_codes:
            return {
                "passed": True,
                "message": f"天气现象匹配: {', '.join(sorted(parsed_codes))}",
            }
        else:
            missing = reference_codes - parsed_codes
            extra = parsed_codes - reference_codes
            messages = []
            if missing:
                messages.append(f"遗漏: {', '.join(sorted(missing))}")
            if extra:
                messages.append(f"多余: {', '.join(sorted(extra))}")
            return {
                "passed": False,
                "message": f"天气现象不匹配: {'; '.join(messages)}",
            }

    def evaluate_temperature_dewpoint(
        self, parsed_data: Dict[str, Any], reference_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """D1.5: 温度露点解析准确率"""
        parsed_temp = parsed_data.get("temperature")
        ref_temp = reference_data.get("temperature")
        parsed_dew = parsed_data.get("dewpoint")
        ref_dew = reference_data.get("dewpoint")

        messages = []
        passed = True

        # 温度检查（允许 ±1°C 差异）
        if parsed_temp is None and ref_temp is None:
            messages.append("温度: 两者都无数据")
        elif parsed_temp is None or ref_temp is None:
            messages.append("温度: 数据缺失")
            passed = False
        elif abs(parsed_temp - ref_temp) <= 1:
            messages.append(f"温度匹配: {parsed_temp}°C ≈ {ref_temp}°C")
        else:
            messages.append(f"温度不匹配: {parsed_temp}°C vs {ref_temp}°C")
            passed = False

        # 露点检查
        if parsed_dew is None and ref_dew is None:
            messages.append("露点: 两者都无数据")
        elif parsed_dew is None or ref_dew is None:
            messages.append("露点: 数据缺失")
            passed = False
        elif abs(parsed_dew - ref_dew) <= 1:
            messages.append(f"露点匹配: {parsed_dew}°C ≈ {ref_dew}°C")
        else:
            messages.append(f"露点不匹配: {parsed_dew}°C vs {ref_dew}°C")
            passed = False

        return {"passed": passed, "message": "; ".join(messages)}

    def evaluate_flight_rules(
        self, parsed_data: Dict[str, Any], reference_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """D1.6: 飞行规则计算准确率"""
        parsed_rules = parsed_data.get("flight_rules")
        reference_rules = reference_data.get("flight_rules")

        if parsed_rules is None and reference_rules is None:
            return {"passed": True, "message": "两者都无飞行规则数据"}

        if parsed_rules is None or reference_rules is None:
            return {"passed": False, "message": "飞行规则数据缺失"}

        if parsed_rules == reference_rules:
            return {"passed": True, "message": f"飞行规则匹配: {parsed_rules}"}
        else:
            return {
                "passed": False,
                "message": f"飞行规则不匹配: {parsed_rules} vs {reference_rules}",
            }

    def _is_within_tolerance(self, value1: float, value2: float) -> bool:
        """检查两个数值是否在容差范围内"""
        if value1 == value2:
            return True

        # 使用相对容差
        max_val = max(abs(value1), abs(value2))
        if max_val == 0:
            return True

        diff = abs(value1 - value2)
        return diff <= max_val * self.tolerance


def evaluate_d1_detailed(
    parsed_data: Dict[str, Any], reference_data: Dict[str, Any], tolerance: float = 0.1
) -> Dict[str, Any]:
    """
    便捷函数：执行 D1 详细评测

    Args:
        parsed_data: 解析后的 METAR 数据
        reference_data: 参考标准数据
        tolerance: 数值比较的容差比例

    Returns:
        评测报告
    """
    evaluator = D1DetailedEvaluator(tolerance)
    return evaluator.evaluate(parsed_data, reference_data)
