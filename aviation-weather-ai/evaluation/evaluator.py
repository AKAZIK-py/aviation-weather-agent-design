"""
航空天气AI系统 - 评测器核心模块
执行边界天气识别能力的评测
"""

import json
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
import statistics

from .golden_set_generator import TestCase, TestType, WeatherCategory


@dataclass
class EvaluationResult:
    """单个测试案例的评测结果"""
    test_id: str
    passed: bool
    expected: Dict[str, Any]
    actual: Dict[str, Any]
    accuracy_metrics: Dict[str, float]
    error_details: Optional[str] = None
    execution_time: float = 0.0


@dataclass
class EvaluationReport:
    """完整评测报告"""
    timestamp: str
    total_cases: int
    passed_cases: int
    failed_cases: int
    overall_accuracy: float
    boundary_weather_recall: float  # 关键指标：边界天气召回率
    normal_weather_precision: float
    edge_case_handling_rate: float
    results: List[EvaluationResult] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)


class WeatherAIEvaluator:
    """航空天气AI评测器"""
    
    def __init__(self, api_endpoint: Optional[str] = None):
        """
        初始化评测器
        
        Args:
            api_endpoint: AI系统API端点（可选，用于真实API调用）
        """
        self.api_endpoint = api_endpoint
        self.evaluation_results: List[EvaluationResult] = []
    
    def evaluate_test_case(self, test_case: TestCase, actual_output: Dict[str, Any]) -> EvaluationResult:
        """
        评测单个测试案例
        
        Args:
            test_case: 测试案例
            actual_output: AI系统的实际输出
        
        Returns:
            EvaluationResult: 评测结果
        """
        start_time = time.time()
        
        expected = test_case.expected_results
        passed = False
        accuracy_metrics = {}
        error_details = None
        
        try:
            # 核心评测逻辑
            if test_case.test_type == TestType.BOUNDARY_WEATHER:
                # 边界天气识别评测
                passed, accuracy_metrics = self._evaluate_boundary_weather(expected, actual_output)
            
            elif test_case.test_type == TestType.NORMAL_WEATHER:
                # 正常天气识别评测
                passed, accuracy_metrics = self._evaluate_normal_weather(expected, actual_output)
            
            elif test_case.test_type == TestType.EDGE_CASE:
                # 边缘案例评测
                passed, accuracy_metrics = self._evaluate_edge_case(expected, actual_output)
        
        except Exception as e:
            error_details = f"评测异常: {str(e)}"
            passed = False
        
        execution_time = time.time() - start_time
        
        result = EvaluationResult(
            test_id=test_case.test_id,
            passed=passed,
            expected=expected,
            actual=actual_output,
            accuracy_metrics=accuracy_metrics,
            error_details=error_details,
            execution_time=execution_time
        )
        
        return result
    
    def _evaluate_boundary_weather(self, expected: Dict[str, Any], actual: Dict[str, Any]) -> tuple:
        """
        评测边界天气识别能力
        
        Returns:
            (是否通过, 准确度指标字典)
        """
        metrics = {}
        all_passed = True
        
        # 1. 边界天气标识准确度
        expected_boundary = expected.get("is_boundary_weather", False)
        actual_boundary = actual.get("is_boundary_weather", False)
        boundary_accuracy = 1.0 if expected_boundary == actual_boundary else 0.0
        metrics["boundary_flag_accuracy"] = boundary_accuracy
        
        if boundary_accuracy == 0.0:
            all_passed = False
        
        # 2. 能见度评测
        if "visibility" in expected:
            vis_expected = expected["visibility"]
            vis_actual = actual.get("visibility", {})
            
            # 能见度值误差
            expected_value = vis_expected.get("value")
            actual_value = vis_actual.get("value")
            
            if expected_value is not None and actual_value is not None:
                vis_error = abs(expected_value - actual_value) / expected_value
                metrics["visibility_error"] = vis_error
                
                # 边界标识准确度
                expected_flag = vis_expected.get("boundary_flag", False)
                actual_flag = vis_actual.get("boundary_flag", False)
                metrics["visibility_boundary_flag_accuracy"] = 1.0 if expected_flag == actual_flag else 0.0
                
                if metrics["visibility_boundary_flag_accuracy"] == 0.0:
                    all_passed = False
        
        # 3. 云底高评测
        if "ceiling" in expected:
            ceil_expected = expected["ceiling"]
            ceil_actual = actual.get("ceiling", {})
            
            expected_height = ceil_expected.get("height")
            actual_height = ceil_actual.get("height")
            
            if expected_height is not None and actual_height is not None:
                ceil_error = abs(expected_height - actual_height) / expected_height
                metrics["ceiling_error"] = ceil_error
                
                expected_flag = ceil_expected.get("boundary_flag", False)
                actual_flag = ceil_actual.get("boundary_flag", False)
                metrics["ceiling_boundary_flag_accuracy"] = 1.0 if expected_flag == actual_flag else 0.0
                
                if metrics["ceiling_boundary_flag_accuracy"] == 0.0:
                    all_passed = False
        
        # 4. 风速评测
        if "wind" in expected:
            wind_expected = expected["wind"]
            wind_actual = actual.get("wind", {})
            
            expected_speed = wind_expected.get("speed")
            actual_speed = wind_actual.get("speed")
            
            if expected_speed is not None and actual_speed is not None:
                wind_error = abs(expected_speed - actual_speed) / expected_speed
                metrics["wind_error"] = wind_error
                
                expected_flag = wind_expected.get("boundary_flag", False)
                actual_flag = wind_actual.get("boundary_flag", False)
                metrics["wind_boundary_flag_accuracy"] = 1.0 if expected_flag == actual_flag else 0.0
                
                if metrics["wind_boundary_flag_accuracy"] == 0.0:
                    all_passed = False
        
        # 5. 天气现象评测
        if "weather_phenomena" in expected:
            expected_phenomena = set(expected["weather_phenomena"])
            actual_phenomena = set(actual.get("weather_phenomena", []))
            
            if expected_phenomena:
                # Jaccard相似度
                intersection = len(expected_phenomena & actual_phenomena)
                union = len(expected_phenomena | actual_phenomena)
                phenomena_similarity = intersection / union if union > 0 else 0.0
                metrics["weather_phenomena_similarity"] = phenomena_similarity
                
                # 至少识别出关键天气现象
                critical_phenomena = {"FG", "TS", "TSRA", "+TSRA", "+SHRA"}
                critical_detected = len(expected_phenomena & critical_phenomena & actual_phenomena)
                critical_expected = len(expected_phenomena & critical_phenomena)
                
                if critical_expected > 0:
                    metrics["critical_phenomena_recall"] = critical_detected / critical_expected
                    if metrics["critical_phenomena_recall"] < 0.8:
                        all_passed = False
        
        # 6. 风险等级评测
        if "risk_level" in expected:
            expected_risk = expected["risk_level"]
            actual_risk = actual.get("risk_level", "unknown")
            metrics["risk_level_accuracy"] = 1.0 if expected_risk == actual_risk else 0.0
        
        return (all_passed, metrics)
    
    def _evaluate_normal_weather(self, expected: Dict[str, Any], actual: Dict[str, Any]) -> tuple:
        """评测正常天气识别能力"""
        metrics = {}
        all_passed = True
        
        # 确保正确识别为非边界天气
        expected_boundary = expected.get("is_boundary_weather", False)
        actual_boundary = actual.get("is_boundary_weather", False)
        
        if expected_boundary != actual_boundary:
            all_passed = False
            metrics["false_positive"] = 1.0  # 误报边界天气
        
        metrics["normal_weather_accuracy"] = 1.0 if expected_boundary == actual_boundary else 0.0
        
        return (all_passed, metrics)
    
    def _evaluate_edge_case(self, expected: Dict[str, Any], actual: Dict[str, Any]) -> tuple:
        """评测边缘案例处理能力"""
        metrics = {}
        all_passed = True
        
        # 检查数据完整性处理
        if "data_completeness" in expected:
            # 系统应能优雅处理缺失数据
            if "error" in actual:
                all_passed = False
                metrics["data_completeness_handling"] = 0.0
            else:
                metrics["data_completeness_handling"] = 1.0
        
        # 检查特殊格式处理
        if "trend" in expected:
            expected_trend = expected["trend"]
            actual_trend = actual.get("trend", "")
            metrics["trend_handling"] = 1.0 if expected_trend == actual_trend else 0.5
        
        return (all_passed, metrics)
    
    def evaluate_golden_set(self, test_cases: List[TestCase], actual_outputs: List[Dict[str, Any]]) -> EvaluationReport:
        """
        评测完整的Golden Set
        
        Args:
            test_cases: 测试案例列表
            actual_outputs: AI系统的实际输出列表
        
        Returns:
            EvaluationReport: 完整评测报告
        """
        if len(test_cases) != len(actual_outputs):
            raise ValueError(f"测试案例数量({len(test_cases)})与实际输出数量({len(actual_outputs)})不匹配")
        
        results = []
        
        for test_case, actual_output in zip(test_cases, actual_outputs):
            result = self.evaluate_test_case(test_case, actual_output)
            results.append(result)
        
        # 计算整体指标
        total_cases = len(results)
        passed_cases = sum(1 for r in results if r.passed)
        failed_cases = total_cases - passed_cases
        overall_accuracy = passed_cases / total_cases if total_cases > 0 else 0.0
        
        # 计算边界天气召回率（关键指标）
        boundary_results = [r for r, tc in zip(results, test_cases) if tc.test_type == TestType.BOUNDARY_WEATHER]
        boundary_passed = sum(1 for r in boundary_results if r.passed)
        boundary_weather_recall = boundary_passed / len(boundary_results) if boundary_results else 0.0
        
        # 计算正常天气精确度
        normal_results = [r for r, tc in zip(results, test_cases) if tc.test_type == TestType.NORMAL_WEATHER]
        normal_passed = sum(1 for r in normal_results if r.passed)
        normal_weather_precision = normal_passed / len(normal_results) if normal_results else 0.0
        
        # 计算边缘案例处理率
        edge_results = [r for r, tc in zip(results, test_cases) if tc.test_type == TestType.EDGE_CASE]
        edge_passed = sum(1 for r in edge_results if r.passed)
        edge_case_handling_rate = edge_passed / len(edge_results) if edge_results else 0.0
        
        # 生成摘要
        summary = {
            "total_cases": total_cases,
            "passed": passed_cases,
            "failed": failed_cases,
            "pass_rate": f"{overall_accuracy * 100:.2f}%",
            "boundary_weather": {
                "total": len(boundary_results),
                "passed": boundary_passed,
                "recall": f"{boundary_weather_recall * 100:.2f}%"
            },
            "normal_weather": {
                "total": len(normal_results),
                "passed": normal_passed,
                "precision": f"{normal_weather_precision * 100:.2f}%"
            },
            "edge_cases": {
                "total": len(edge_results),
                "passed": edge_passed,
                "handling_rate": f"{edge_case_handling_rate * 100:.2f}%"
            }
        }
        
        report = EvaluationReport(
            timestamp=datetime.now().isoformat(),
            total_cases=total_cases,
            passed_cases=passed_cases,
            failed_cases=failed_cases,
            overall_accuracy=overall_accuracy,
            boundary_weather_recall=boundary_weather_recall,
            normal_weather_precision=normal_weather_precision,
            edge_case_handling_rate=edge_case_handling_rate,
            results=results,
            summary=summary
        )
        
        return report
    
    def calculate_performance_metrics(self, results: List[EvaluationResult]) -> Dict[str, float]:
        """计算性能指标"""
        execution_times = [r.execution_time for r in results]
        
        return {
            "avg_execution_time": statistics.mean(execution_times) if execution_times else 0.0,
            "max_execution_time": max(execution_times) if execution_times else 0.0,
            "min_execution_time": min(execution_times) if execution_times else 0.0,
            "median_execution_time": statistics.median(execution_times) if execution_times else 0.0
        }
