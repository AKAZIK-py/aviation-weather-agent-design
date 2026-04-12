"""
航空天气AI系统 - 评测报告生成器
生成Markdown格式的评测报告
"""

import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path

from .evaluator import EvaluationReport, EvaluationResult
from .golden_set_generator import TestCase, TestType, WeatherCategory


class ReportGenerator:
    """评测报告生成器"""
    
    def __init__(self, output_dir: str = None):
        """初始化报告生成器"""
        if output_dir is None:
            # 使用项目本地输出目录
            self.output_dir = Path(__file__).parent.parent / "outputs"
        else:
            self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_markdown_report(self, report: EvaluationReport, test_cases: List[TestCase]) -> str:
        """生成Markdown格式的评测报告"""
        md_lines = []
        
        # 标题
        md_lines.append("# 航空天气AI系统评测报告")
        md_lines.append("")
        md_lines.append(f"**生成时间**: {report.timestamp}")
        md_lines.append("")
        
        # 执行摘要
        md_lines.append("## 📊 执行摘要")
        md_lines.append("")
        md_lines.append(f"- **总测试案例数**: {report.total_cases}")
        md_lines.append(f"- **通过案例数**: {report.passed_cases} ✅")
        md_lines.append(f"- **失败案例数**: {report.failed_cases} ❌")
        md_lines.append(f"- **整体准确率**: {report.overall_accuracy * 100:.2f}%")
        md_lines.append("")
        
        # 关键指标
        md_lines.append("## 🎯 关键评测指标")
        md_lines.append("")
        md_lines.append("| 指标 | 数值 | 权重 | 状态 |")
        md_lines.append("|------|------|------|------|")
        
        boundary_status = "✅ 达标" if report.boundary_weather_recall >= 0.95 else "❌ 未达标"
        md_lines.append(f"| 边界天气召回率 | {report.boundary_weather_recall * 100:.2f}% | 25% | {boundary_status} |")
        
        normal_status = "✅ 达标" if report.normal_weather_precision >= 0.90 else "❌ 未达标"
        md_lines.append(f"| 正常天气精确度 | {report.normal_weather_precision * 100:.2f}% | 20% | {normal_status} |")
        
        overall_status = "✅ 达标" if report.overall_accuracy >= 0.85 else "❌ 未达标"
        md_lines.append(f"| 整体准确率 | {report.overall_accuracy * 100:.2f}% | 35% | {overall_status} |")
        
        edge_status = "✅ 达标" if report.edge_case_handling_rate >= 0.80 else "❌ 未达标"
        md_lines.append(f"| 边缘案例处理率 | {report.edge_case_handling_rate * 100:.2f}% | 20% | {edge_status} |")
        
        md_lines.append("")
        
        # 详细结果
        md_lines.append("## 📋 详细评测结果")
        md_lines.append("")
        
        boundary_results = [(r, tc) for r, tc in zip(report.results, test_cases) 
                           if tc.test_type == TestType.BOUNDARY_WEATHER]
        normal_results = [(r, tc) for r, tc in zip(report.results, test_cases) 
                         if tc.test_type == TestType.NORMAL_WEATHER]
        edge_results = [(r, tc) for r, tc in zip(report.results, test_cases) 
                       if tc.test_type == TestType.EDGE_CASE]
        
        # 边界天气测试
        md_lines.append("### 1️⃣ 边界天气测试 (Boundary Weather)")
        md_lines.append("")
        passed = len([r for r, _ in boundary_results if r.passed])
        total = len(boundary_results)
        md_lines.append(f"**通过率**: {passed}/{total}")
        md_lines.append("")
        md_lines.append("| 测试ID | 描述 | 状态 | 关键指标 |")
        md_lines.append("|--------|------|------|----------|")
        
        for result, test_case in boundary_results:
            status = "✅ 通过" if result.passed else "❌ 失败"
            metrics_str = self._format_metrics(result.accuracy_metrics)
            md_lines.append(f"| {test_case.test_id} | {test_case.description} | {status} | {metrics_str} |")
        
        md_lines.append("")
        
        # 正常天气测试
        md_lines.append("### 2️⃣ 正常天气测试 (Normal Weather)")
        md_lines.append("")
        passed = len([r for r, _ in normal_results if r.passed])
        total = len(normal_results)
        md_lines.append(f"**通过率**: {passed}/{total}")
        md_lines.append("")
        
        for result, test_case in normal_results:
            status = "✅ 通过" if result.passed else "❌ 失败"
            md_lines.append(f"- **{test_case.test_id}**: {test_case.description} - {status}")
        
        md_lines.append("")
        
        # 边缘案例测试
        md_lines.append("### 3️⃣ 边缘案例测试 (Edge Cases)")
        md_lines.append("")
        passed = len([r for r, _ in edge_results if r.passed])
        total = len(edge_results)
        md_lines.append(f"**通过率**: {passed}/{total}")
        md_lines.append("")
        
        for result, test_case in edge_results:
            status = "✅ 通过" if result.passed else "❌ 失败"
            md_lines.append(f"- **{test_case.test_id}**: {test_case.description} - {status}")
        
        md_lines.append("")
        
        # 失败案例分析
        failed_results = [(r, tc) for r, tc in zip(report.results, test_cases) if not r.passed]
        
        if failed_results:
            md_lines.append("## ❌ 失败案例分析")
            md_lines.append("")
            
            for result, test_case in failed_results:
                md_lines.append(f"### {test_case.test_id}: {test_case.description}")
                md_lines.append("")
                md_lines.append(f"**测试类型**: {test_case.test_type.value}")
                md_lines.append(f"**天气类别**: {test_case.category.value}")
                md_lines.append("")
                
                md_lines.append("**预期结果**:")
                md_lines.append("```json")
                md_lines.append(json.dumps(result.expected, ensure_ascii=False, indent=2))
                md_lines.append("```")
                md_lines.append("")
                
                md_lines.append("**实际结果**:")
                md_lines.append("```json")
                md_lines.append(json.dumps(result.actual, ensure_ascii=False, indent=2))
                md_lines.append("```")
                md_lines.append("")
                
                if result.error_details:
                    md_lines.append(f"**错误详情**: {result.error_details}")
                    md_lines.append("")
                
                md_lines.append("**准确度指标**:")
                for metric, value in result.accuracy_metrics.items():
                    md_lines.append(f"- {metric}: {value:.4f}")
                md_lines.append("")
        
        # 优化建议
        md_lines.append("## 💡 优化建议")
        md_lines.append("")
        suggestions = self._generate_optimization_suggestions(report, test_cases)
        for i, suggestion in enumerate(suggestions, 1):
            md_lines.append(f"{i}. {suggestion}")
        
        md_lines.append("")
        
        # 附录
        md_lines.append("## 📈 附录：统计信息")
        md_lines.append("")
        md_lines.append("```json")
        md_lines.append(json.dumps(report.summary, ensure_ascii=False, indent=2))
        md_lines.append("```")
        
        return "\n".join(md_lines)
    
    def _format_metrics(self, metrics: Dict[str, float]) -> str:
        """格式化准确度指标"""
        if not metrics:
            return "N/A"
        
        key_metrics = ["boundary_flag_accuracy", "visibility_boundary_flag_accuracy", 
                      "ceiling_boundary_flag_accuracy", "wind_boundary_flag_accuracy"]
        
        formatted = []
        for key in key_metrics:
            if key in metrics:
                value = metrics[key]
                formatted.append(f"{key.split('_')[0]}: {value * 100:.0f}%")
        
        return ", ".join(formatted) if formatted else "准确度指标已记录"
    
    def _generate_optimization_suggestions(self, report: EvaluationReport, test_cases: List[TestCase]) -> List[str]:
        """生成优化建议"""
        suggestions = []
        
        if report.boundary_weather_recall < 0.95:
            suggestions.append(
                f"**提升边界天气召回率** (当前: {report.boundary_weather_recall * 100:.2f}%): "
                "重点优化能见度、云底高、风速的边界值识别逻辑，确保临界值案例能够正确触发边界天气标识。"
            )
        
        if report.normal_weather_precision < 0.90:
            suggestions.append(
                f"**降低误报率** (当前精确度: {report.normal_weather_precision * 100:.2f}%): "
                "调整阈值判断逻辑，避免将正常天气误判为边界天气。"
            )
        
        if report.edge_case_handling_rate < 0.80:
            suggestions.append(
                f"**增强边缘案例处理能力** (当前: {report.edge_case_handling_rate * 100:.2f}%): "
                "完善数据验证和异常处理机制，确保系统能够优雅处理缺失数据和特殊格式。"
            )
        
        failed_boundary = [(r, tc) for r, tc in zip(report.results, test_cases) 
                          if not r.passed and tc.test_type == TestType.BOUNDARY_WEATHER]
        
        if failed_boundary:
            visibility_failures = [tc for r, tc in failed_boundary 
                                  if tc.category == WeatherCategory.VISIBILITY]
            ceiling_failures = [tc for r, tc in failed_boundary 
                               if tc.category == WeatherCategory.CEILING]
            wind_failures = [tc for r, tc in failed_boundary 
                            if tc.category == WeatherCategory.WIND]
            
            if visibility_failures:
                count = len(visibility_failures)
                suggestions.append(
                    f"**能见度识别优化**: 有{count}个能见度相关案例失败。"
                    "建议检查能见度解析逻辑，特别是1500-2000米区间的边界判断。"
                )
            
            if ceiling_failures:
                count = len(ceiling_failures)
                suggestions.append(
                    f"**云底高识别优化**: 有{count}个云底高相关案例失败。"
                    "建议检查云层高度解析和边界标识逻辑，特别是VV（垂直能见度）情况的处理。"
                )
            
            if wind_failures:
                count = len(wind_failures)
                suggestions.append(
                    f"**风速识别优化**: 有{count}个风速相关案例失败。"
                    "建议检查风速和阵风的边界判断，特别是接近17m/s临界值的案例。"
                )
        
        if not suggestions:
            suggestions.append("✅ 系统表现良好！继续保持当前评测标准，建议定期运行评测以监控性能稳定性。")
        
        return suggestions
    
    def save_report(self, report: EvaluationReport, test_cases: List[TestCase], 
                    filename: Optional[str] = None) -> str:
        """保存评测报告为Markdown文件"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"evaluation_report_{timestamp}.md"
        
        report_path = self.output_dir / filename
        md_content = self.generate_markdown_report(report, test_cases)
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        return str(report_path)
    
    def save_json_report(self, report: EvaluationReport, filename: Optional[str] = None) -> str:
        """保存评测报告为JSON文件"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"evaluation_report_{timestamp}.json"
        
        report_path = self.output_dir / filename
        
        report_dict = {
            "timestamp": report.timestamp,
            "summary": report.summary,
            "metrics": {
                "overall_accuracy": report.overall_accuracy,
                "boundary_weather_recall": report.boundary_weather_recall,
                "normal_weather_precision": report.normal_weather_precision,
                "edge_case_handling_rate": report.edge_case_handling_rate
            },
            "results": [
                {
                    "test_id": r.test_id,
                    "passed": r.passed,
                    "accuracy_metrics": r.accuracy_metrics,
                    "error_details": r.error_details,
                    "execution_time": r.execution_time
                }
                for r in report.results
            ]
        }
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report_dict, f, ensure_ascii=False, indent=2)
        
        return str(report_path)
