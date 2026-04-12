"""
D1 根因分析模块
对 golden_set 中的解析差异进行根因分类和修复建议
"""
import json
import os
import re
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

from app.nodes.parse_metar_node import METARParser
from app.evaluation.d1_evaluator import D1DetailedEvaluator


class RootCauseType(Enum):
    """根因分类枚举"""
    VISIBILITY_BOUNDARY_MISMATCH = "Type 1: visibility_boundary_mismatch"
    CEILING_DEFINITION_DISPUTE = "Type 2: ceiling_definition_dispute"
    VV_PRIORITY_CONFLICT = "Type 3: vv_priority_conflict"
    ANNOTATION_ERROR = "Type 4: annotation_error"
    RULE_LOGIC_ERROR = "Type 5: rule_logic_error"
    UNCLASSIFIED = "Unclassified"


@dataclass
class DimensionAccuracy:
    """单维度准确率"""
    dimension: str
    total: int = 0
    correct: int = 0
    accuracy: float = 0.0
    mismatches: List[str] = field(default_factory=list)

    def update(self):
        if self.total > 0:
            self.accuracy = self.correct / self.total


@dataclass
class InconsistentCase:
    """不一致 case 分析"""
    case_id: str
    metar: str
    predicted: Dict[str, Any]
    expected: Dict[str, Any]
    failed_dimensions: List[str]
    root_cause: RootCauseType
    threshold_gap: str
    fix_suggestion: str


class D1RootCauseAnalyzer:
    """D1 根因分析器"""

    def __init__(self, golden_set_path: Optional[str] = None):
        self.parser = METARParser()
        self.evaluator = D1DetailedEvaluator(tolerance=0.1)
        self.golden_set_path = golden_set_path or self._default_golden_set_path()
        self.golden_set: List[Dict[str, Any]] = []
        self.dimension_stats: Dict[str, DimensionAccuracy] = {
            "D1.1_visibility": DimensionAccuracy("D1.1 能见度解析"),
            "D1.2_cloud_base": DimensionAccuracy("D1.2 云底高解析"),
            "D1.3_wind": DimensionAccuracy("D1.3 风速风向解析"),
            "D1.4_weather_phenomena": DimensionAccuracy("D1.4 天气现象识别"),
            "D1.5_temperature_dewpoint": DimensionAccuracy("D1.5 温度露点解析"),
            "D1.6_flight_rules": DimensionAccuracy("D1.6 飞行规则计算"),
        }
        self.inconsistent_cases: List[InconsistentCase] = []

    def _default_golden_set_path(self) -> str:
        return os.path.join(os.path.dirname(__file__), "golden_set.json")

    def load_golden_set(self) -> List[Dict[str, Any]]:
        """加载 Golden Set"""
        with open(self.golden_set_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.golden_set = data.get("cases", [])
        return self.golden_set

    def run_analysis(self) -> Dict[str, Any]:
        """对所有 case 运行分析"""
        if not self.golden_set:
            self.load_golden_set()

        self.inconsistent_cases = []
        for dim in self.dimension_stats.values():
            dim.total = 0
            dim.correct = 0
            dim.mismatches = []

        total_cases = len(self.golden_set)
        consistent_count = 0
        inconsistent_count = 0

        for case in self.golden_set:
            case_id = case.get("id", "UNKNOWN")
            metar = case.get("metar", "")
            expected_data = case.get("parsed", {})

            # 运行 ICAO 标准解析
            predicted_data, success, errors = self.parser.parse(metar, standard="icao")

            if not success:
                # 解析失败直接归为规则逻辑错误
                self.inconsistent_cases.append(InconsistentCase(
                    case_id=case_id,
                    metar=metar,
                    predicted=predicted_data,
                    expected=expected_data,
                    failed_dimensions=["ALL"],
                    root_cause=RootCauseType.RULE_LOGIC_ERROR,
                    threshold_gap="解析失败",
                    fix_suggestion=f"修复解析错误: {', '.join(errors)}"
                ))
                inconsistent_count += 1
                continue

            # 执行 D1 评测
            eval_report = self.evaluator.evaluate(predicted_data, expected_data)

            # 更新各维度统计
            sub_dims = eval_report.get("d1_sub_dimensions", {})
            case_failed_dims = []

            for dim_key, dim_result in sub_dims.items():
                self.dimension_stats[dim_key].total += 1
                if dim_result.get("passed", False):
                    self.dimension_stats[dim_key].correct += 1
                else:
                    self.dimension_stats[dim_key].mismatches.append(
                        f"{case_id}: {dim_result.get('message', '')}"
                    )
                    case_failed_dims.append(dim_key)

            # 更新准确率
            for dim in self.dimension_stats.values():
                dim.update()

            if eval_report.get("d1_overall", False):
                consistent_count += 1
            else:
                inconsistent_count += 1
                root_cause, threshold_gap, fix_suggestion = self._classify_root_cause(
                    case_id, metar, predicted_data, expected_data, case_failed_dims
                )
                self.inconsistent_cases.append(InconsistentCase(
                    case_id=case_id,
                    metar=metar,
                    predicted=predicted_data,
                    expected=expected_data,
                    failed_dimensions=case_failed_dims,
                    root_cause=root_cause,
                    threshold_gap=threshold_gap,
                    fix_suggestion=fix_suggestion,
                ))

        return {
            "total_cases": total_cases,
            "consistent": consistent_count,
            "inconsistent": inconsistent_count,
            "dimension_stats": self.dimension_stats,
            "inconsistent_cases": self.inconsistent_cases,
        }

    def _classify_root_cause(
        self,
        case_id: str,
        metar: str,
        predicted: Dict[str, Any],
        expected: Dict[str, Any],
        failed_dims: List[str],
    ) -> Tuple[RootCauseType, str, str]:
        """对不一致 case 进行根因分类"""

        # 检查 VV 优先级冲突
        has_vv = predicted.get("vertical_visibility") is not None
        exp_has_vv = expected.get("vertical_visibility") is not None
        if "D1.2_cloud_base" in failed_dims or "D1.6_flight_rules" in failed_dims:
            if has_vv or exp_has_vv:
                # 检查 VV 相关的差异
                pred_fr = predicted.get("flight_rules")
                exp_fr = expected.get("flight_rules")
                pred_vv = predicted.get("vertical_visibility")
                exp_vv = expected.get("vertical_visibility")
                gap = f"VV: predicted={pred_vv}ft vs expected={exp_vv}ft, flight_rules: {pred_fr} vs {exp_fr}"
                if pred_vv != exp_vv or pred_fr != exp_fr:
                    return (
                        RootCauseType.VV_PRIORITY_CONFLICT,
                        gap,
                        "检查 VV 优先级处理逻辑：VV 是否正确转换为云底高、VV 与普通能见度共存时的处理",
                    )

        # 检查能见度边界值差异
        if "D1.1_visibility" in failed_dims or "D1.6_flight_rules" in failed_dims:
            pred_vis = predicted.get("visibility")
            exp_vis = expected.get("visibility")
            if pred_vis is not None and exp_vis is not None:
                diff_m = abs(pred_vis - exp_vis) * 1000
                if diff_m <= 100:
                    gap = f"能见度差距: {diff_m:.0f}m (predicted={pred_vis}km vs expected={exp_vis}km)"
                    return (
                        RootCauseType.VISIBILITY_BOUNDARY_MISMATCH,
                        gap,
                        "能见度换算精度问题：检查 m→km 转换、SM→km 转换、9999/CAVOK 处理、边界值截断",
                    )

        # 检查 ceiling 定义争议
        if "D1.2_cloud_base" in failed_dims or "D1.6_flight_rules" in failed_dims:
            pred_layers = predicted.get("cloud_layers", [])
            exp_layers = expected.get("cloud_layers", [])
            pred_types = {l.get("type") for l in pred_layers}
            exp_types = {l.get("type") for l in exp_layers}

            # 检查 FEW/SCT 是否被误判为 ceiling
            if ("FEW" in pred_types or "SCT" in pred_types) and pred_types != exp_types:
                pred_fr = predicted.get("flight_rules")
                exp_fr = expected.get("flight_rules")
                if pred_fr != exp_fr:
                    return (
                        RootCauseType.CEILING_DEFINITION_DISPUTE,
                        f"FEW/SCT ceiling 争议: predicted={pred_fr} vs expected={exp_fr}",
                        "FEW(1-2okta)和SCT(3-4okta)不构成ceiling，仅BKN(5-7)和OVC(8)算ceiling",
                    )

        # 检查天气现象差异
        if "D1.4_weather_phenomena" in failed_dims:
            pred_weather = {w.get("code") for w in predicted.get("present_weather", [])}
            exp_weather = {w.get("code") for w in expected.get("present_weather", [])}
            extra = pred_weather - exp_weather
            missing = exp_weather - pred_weather
            if extra or missing:
                gap = f"extra={extra}, missing={missing}"
                # 如果期望中有 METAR 中不存在的现象，可能是标注错误
                metar_upper = metar.upper()
                annotation_issues = []
                for code in missing:
                    if code not in metar_upper:
                        annotation_issues.append(code)
                if annotation_issues:
                    return (
                        RootCauseType.ANNOTATION_ERROR,
                        gap,
                        f"Golden Set 标注可能有误: {annotation_issues} 不在 METAR 原文中",
                    )
                return (
                    RootCauseType.RULE_LOGIC_ERROR,
                    gap,
                    "天气现象提取规则有 bug，检查正则表达式和 WEATHER_CODES 映射",
                )

        # 检查温度差异
        if "D1.5_temperature_dewpoint" in failed_dims:
            pred_temp = predicted.get("temperature")
            exp_temp = expected.get("temperature")
            pred_dew = predicted.get("dewpoint")
            exp_dew = expected.get("dewpoint")
            gap = f"temp: {pred_temp} vs {exp_temp}, dew: {pred_dew} vs {exp_dew}"
            return (
                RootCauseType.RULE_LOGIC_ERROR,
                gap,
                "温度解析规则有误：检查 M前缀 vs -前缀处理、双重负号处理",
            )

        # 默认归为规则逻辑错误
        return (
            RootCauseType.RULE_LOGIC_ERROR,
            f"failed_dims={failed_dims}",
            "需要人工复核，可能是代码逻辑 bug",
        )

    def generate_markdown_report(self) -> str:
        """生成完整的根因分析 Markdown 报告"""
        if not self.inconsistent_cases and not any(
            d.total > 0 for d in self.dimension_stats.values()
        ):
            self.run_analysis()

        lines = []
        lines.append("# D1 根因分析报告")
        lines.append(f"\n生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"Golden Set 路径: {self.golden_set_path}")
        lines.append(f"评测标准: ICAO Annex 3 + 中国民航标准")
        lines.append("")

        # === 总体概览 ===
        lines.append("## 1. 总体概览")
        total = len(self.golden_set) if self.golden_set else 0
        consistent = total - len(self.inconsistent_cases)
        lines.append(f"- Golden Set 总 case 数: {total}")
        lines.append(f"- 一致 case 数: {consistent}")
        lines.append(f"- 不一致 case 数: {len(self.inconsistent_cases)}")
        if total > 0:
            lines.append(f"- 一致率: {consistent/total*100:.1f}%")
        lines.append("")

        # === 各维度准确率 ===
        lines.append("## 2. D1.1-D1.5 各维度准确率")
        lines.append("")
        lines.append("| 维度 | 总数 | 正确 | 准确率 |")
        lines.append("|------|------|------|--------|")
        for dim_key, dim in self.dimension_stats.items():
            acc_str = f"{dim.accuracy*100:.1f}%" if dim.total > 0 else "N/A"
            lines.append(f"| {dim.dimension} | {dim.total} | {dim.correct} | {acc_str} |")
        lines.append("")

        # === 各维度不匹配详情 ===
        lines.append("## 3. 各维度不匹配详情")
        for dim_key, dim in self.dimension_stats.items():
            if dim.mismatches:
                lines.append(f"\n### {dim.dimension}")
                for m in dim.mismatches:
                    lines.append(f"- {m}")
        lines.append("")

        # === 根因分类统计 ===
        lines.append("## 4. 根因分类统计")
        cause_counts = {}
        for ic in self.inconsistent_cases:
            cause_name = ic.root_cause.value
            cause_counts[cause_name] = cause_counts.get(cause_name, 0) + 1
        if cause_counts:
            lines.append("")
            lines.append("| 根因类型 | 数量 | 占比 |")
            lines.append("|----------|------|------|")
            ic_total = len(self.inconsistent_cases)
            for cause, count in sorted(cause_counts.items()):
                pct = count / ic_total * 100 if ic_total > 0 else 0
                lines.append(f"| {cause} | {count} | {pct:.1f}% |")
        else:
            lines.append("\n所有 case 均一致，无根因分析。")
        lines.append("")

        # === 详细 case 分析 ===
        if self.inconsistent_cases:
            lines.append("## 5. 不一致 case 详细分析")
            for i, ic in enumerate(self.inconsistent_cases, 1):
                lines.append(f"\n### Case {i}: {ic.case_id}")
                lines.append(f"**METAR 原文:** `{ic.metar}`")
                lines.append("")

                lines.append("**预测值:**")
                pred_vis = ic.predicted.get("visibility")
                pred_fr = ic.predicted.get("flight_rules")
                pred_vv = ic.predicted.get("vertical_visibility")
                pred_temp = ic.predicted.get("temperature")
                pred_wind = ic.predicted.get("wind_speed")
                pred_weather = [w.get("code") for w in ic.predicted.get("present_weather", [])]
                pred_layers = ic.predicted.get("cloud_layers", [])
                lines.append(f"  - 能见度: {pred_vis} km")
                lines.append(f"  - 飞行规则: {pred_fr}")
                lines.append(f"  - VV: {pred_vv} ft" if pred_vv else "  - VV: None")
                lines.append(f"  - 温度: {pred_temp}°C")
                lines.append(f"  - 风速: {pred_wind} kt")
                lines.append(f"  - 天气现象: {pred_weather}")
                lines.append(f"  - 云层: {[{'type': l.get('type'), 'h': l.get('height_feet')} for l in pred_layers]}")
                lines.append("")

                lines.append("**期望值:**")
                exp_vis = ic.expected.get("visibility")
                exp_fr = ic.expected.get("flight_rules")
                exp_vv = ic.expected.get("vertical_visibility")
                exp_temp = ic.expected.get("temperature")
                exp_wind = ic.expected.get("wind_speed")
                exp_weather = [w.get("code") for w in ic.expected.get("present_weather", [])]
                exp_layers = ic.expected.get("cloud_layers", [])
                lines.append(f"  - 能见度: {exp_vis} km")
                lines.append(f"  - 飞行规则: {exp_fr}")
                lines.append(f"  - VV: {exp_vv} ft" if exp_vv else "  - VV: None")
                lines.append(f"  - 温度: {exp_temp}°C")
                lines.append(f"  - 风速: {exp_wind} kt")
                lines.append(f"  - 天气现象: {exp_weather}")
                lines.append(f"  - 云层: {[{'type': l.get('type'), 'h': l.get('height_feet')} for l in exp_layers]}")
                lines.append("")

                lines.append(f"**失败维度:** {', '.join(ic.failed_dimensions)}")
                lines.append(f"**根因分类:** {ic.root_cause.value}")
                lines.append(f"**阈值差距:** {ic.threshold_gap}")
                lines.append(f"**修复建议:** {ic.fix_suggestion}")
                lines.append("")
                lines.append("---")
        else:
            lines.append("## 5. 不一致 case 详细分析")
            lines.append("\n所有 case 均一致，无需详细分析。")
        lines.append("")

        # === 总结与建议 ===
        lines.append("## 6. 总结与建议")
        if cause_counts:
            # 找到最多根因类型
            max_cause = max(cause_counts, key=cause_counts.get)
            lines.append(f"- 最主要的根因类型: **{max_cause}** ({cause_counts[max_cause]} 个)")
            lines.append("")

            lines.append("### 优先修复建议:")
            if "Type 1" in max_cause:
                lines.append("1. 统一能见度换算精度，保留足够小数位")
                lines.append("2. 处理 9999→10km、CAVOK→10km 边界转换")
                lines.append("3. SM→km 换算使用精确系数 1.60934")
            elif "Type 2" in max_cause:
                lines.append("1. 明确 FEW/SCT 不构成 ceiling 的规则")
                lines.append("2. VV 作为 ceiling 处理时统一标准")
            elif "Type 3" in max_cause:
                lines.append("1. 优化 VV 优先级处理逻辑")
                lines.append("2. VV 与普通能见度共存时的决策树")
                lines.append("3. VV 转 ceiling 的高度阈值统一")
            elif "Type 4" in max_cause:
                lines.append("1. 复核 Golden Set 标注数据")
                lines.append("2. 验证天气现象是否在 METAR 原文中")
            elif "Type 5" in max_cause:
                lines.append("1. 排查解析规则中的逻辑 bug")
                lines.append("2. 检查正则表达式边界条件")
        else:
            lines.append("- 当前 Golden Set 所有 case 均解析一致，系统表现良好。")
        lines.append("")

        return "\n".join(lines)


def run_root_cause_analysis(golden_set_path: Optional[str] = None) -> str:
    """便捷函数：运行根因分析并返回报告"""
    analyzer = D1RootCauseAnalyzer(golden_set_path)
    analyzer.load_golden_set()
    analyzer.run_analysis()
    return analyzer.generate_markdown_report()


if __name__ == "__main__":
    report = run_root_cause_analysis()
    print(report)
