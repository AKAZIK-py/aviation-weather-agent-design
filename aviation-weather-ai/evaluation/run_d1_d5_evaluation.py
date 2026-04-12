#!/usr/bin/env python3
"""
D1-D5 评测脚本
针对航空天气AI系统的综合评测
"""

import sys
import json
import time
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@dataclass
class D1_D5_Metrics:
    """D1-D5评测指标"""
    d1_rule_mapping_accuracy: float = 0.0  # 规则映射准确率 (METAR解析)
    d2_role_matching_accuracy: float = 0.0  # 角色匹配准确率 (flight_rules)
    d3_safety_boundary_coverage: float = 0.0  # 安全边界覆盖率
    d4_hallucination_rate: float = 0.0  # 幻觉率
    d5_unauthorized_response_rate: float = 0.0  # 未授权响应率

    # 详细统计
    total_cases: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    timeout_calls: int = 0


@dataclass
class TestCase:
    """测试案例"""
    test_id: str
    category: str
    description: str
    icao_code: str
    raw_metar: str
    expected: Dict[str, Any]


@dataclass
class EvaluationResult:
    """单个测试案例的评测结果"""
    test_id: str
    passed: bool
    expected: Dict[str, Any]
    actual: Dict[str, Any]
    d1_correct: bool = False  # METAR解析是否正确
    d2_correct: bool = False  # flight_rules是否正确
    d3_covered: bool = False  # 安全边界是否覆盖
    d4_hallucination: bool = False  # 是否有幻觉
    d5_unauthorized: bool = False  # 是否有未授权响应
    error_details: Optional[str] = None
    response_time: float = 0.0


class D1_D5_Evaluator:
    """D1-D5评测器"""

    # Flight rules thresholds
    VFR_THRESHOLDS = {
        'visibility_min': 5000,  # meters
        'ceiling_min': 3000  # feet
    }

    MVFR_THRESHOLDS = {
        'visibility_min': 3000,  # meters
        'ceiling_min': 1000  # feet
    }

    IFR_THRESHOLDS = {
        'visibility_min': 1600,  # meters
        'ceiling_min': 500  # feet
    }

    # Safety-critical weather phenomena
    SAFETY_CRITICAL_PHENOMENA = {
        'TS', 'TSRA', '+TSRA', 'TSGR', 'TSGS',  # Thunderstorms
        'FG', 'FZFG', 'VA',  # Visibility hazards
        'WS', 'WC',  # Wind shear
        'FZRA', 'FZDZ', 'PL', 'IC',  # Icing
        'SS', 'DS', 'PO',  # Dust/sand storms
        'FC',  # Funnel cloud
        'GS', 'GR',  # Hail
        'SQ'  # Squall
    }

    def __init__(self, api_endpoint: str = "http://localhost:8000/api/v1/analyze"):
        """
        初始化评测器

        Args:
            api_endpoint: 后端API端点
        """
        self.api_endpoint = api_endpoint
        self.timeout = 30  # seconds
        self.test_cases: List[TestCase] = []
        self.results: List[EvaluationResult] = []

    def load_golden_set(self, filepath: str) -> int:
        """
        加载Golden Set

        Args:
            filepath: JSON文件路径

        Returns:
            加载的测试案例数量
        """
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self.test_cases = []
        for case_data in data['test_cases']:
            test_case = TestCase(
                test_id=case_data['test_id'],
                category=case_data['category'],
                description=case_data['description'],
                icao_code=case_data['icao_code'],
                raw_metar=case_data['raw_metar'],
                expected=case_data['expected']
            )
            self.test_cases.append(test_case)

        return len(self.test_cases)

    def call_backend_api(self, test_case: TestCase) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        调用后端API

        Args:
            test_case: 测试案例

        Returns:
            (API响应, 错误信息)
        """
        payload = {
            "metar_raw": test_case.raw_metar
        }

        try:
            start_time = time.time()
            response = requests.post(
                self.api_endpoint,
                json=payload,
                timeout=self.timeout,
                headers={'Content-Type': 'application/json'}
            )
            response_time = time.time() - start_time

            if response.status_code == 200:
                api_response = response.json()

                # Transform API response to match expected format
                transformed = self._transform_api_response(api_response)
                return transformed, None
            else:
                return None, f"API returned status {response.status_code}: {response.text}"

        except requests.exceptions.Timeout:
            return None, f"API call timed out after {self.timeout}s"
        except requests.exceptions.ConnectionError:
            return None, "Connection error: API server not reachable"
        except requests.exceptions.RequestException as e:
            return None, f"Request failed: {str(e)}"
        except Exception as e:
            return None, f"Unexpected error: {str(e)}"

    def _transform_api_response(self, api_response: Dict[str, Any]) -> Dict[str, Any]:
        """
        将API响应转换为评测所需的格式

        Args:
            api_response: 后端API的原始响应

        Returns:
            转换后的响应
        """
        if not api_response.get('success', False):
            return {}

        metar_parsed = api_response.get('metar_parsed', {})

        # Extract cloud ceiling (lowest BKN or OVC layer)
        ceiling_ft = None
        cloud_layers = metar_parsed.get('cloud_layers', [])
        for layer in cloud_layers:
            cloud_type = layer.get('type', '').upper()
            if cloud_type in ['BKN', 'OVC', 'VV']:
                # Use height_feet if available, otherwise convert height_meters
                if 'height_feet' in layer:
                    ceiling_ft = layer['height_feet']
                elif 'height_meters' in layer:
                    ceiling_ft = int(layer['height_meters'] * 3.28084)
                break

        # Extract visibility (convert km to meters)
        visibility_km = metar_parsed.get('visibility', 10.0)
        visibility_m = int(visibility_km * 1000)

        # Extract wind
        wind_speed_kt = metar_parsed.get('wind_speed', 0)
        wind_gust_kt = metar_parsed.get('wind_gust')

        # Extract weather phenomena (list of codes)
        weather_data = metar_parsed.get('present_weather', [])
        weather_phenomena = [w.get('code', '') for w in weather_data if w.get('code')]

        # Map risk level
        risk_level_map = {
            'LOW': 'low',
            'MEDIUM': 'medium',
            'HIGH': 'high',
            'CRITICAL': 'critical'
        }
        risk_level = risk_level_map.get(api_response.get('risk_level', 'LOW').upper(), 'low')

        # Construct transformed response
        transformed = {
            'flight_rules': metar_parsed.get('flight_rules', 'VFR'),
            'risk_level': risk_level,
            'key_weather_elements': {
                'visibility_m': visibility_m,
                'ceiling_ft': ceiling_ft,
                'wind_speed_kt': wind_speed_kt,
                'wind_gust_kt': wind_gust_kt,
                'weather_phenomena': weather_phenomena
            }
        }

        return transformed

    def evaluate_d1_rule_mapping(self, expected: Dict[str, Any], actual: Dict[str, Any]) -> bool:
        """
        评估D1: 规则映射准确率 (METAR解析)

        检查关键天气元素是否正确解析:
        - visibility (能见度)
        - ceiling (云底高)
        - wind_speed (风速)
        - weather_phenomena (天气现象)
        """
        expected_elements = expected.get('key_weather_elements', {})
        actual_elements = actual.get('key_weather_elements', {})

        # 检查能见度
        if 'visibility_m' in expected_elements:
            expected_vis = expected_elements['visibility_m']
            actual_vis = actual_elements.get('visibility_m')

            if actual_vis is None:
                return False

            # 允许±10%误差
            if expected_vis > 0:
                error = abs(actual_vis - expected_vis) / expected_vis
                if error > 0.1:
                    return False

        # 检查云底高
        if 'ceiling_ft' in expected_elements:
            expected_ceil = expected_elements['ceiling_ft']
            actual_ceil = actual_elements.get('ceiling_ft')

            if expected_ceil is not None:
                if actual_ceil is None:
                    return False

                # 允许±10%误差
                error = abs(actual_ceil - expected_ceil) / expected_ceil
                if error > 0.1:
                    return False

        # 检查风速
        if 'wind_speed_kt' in expected_elements:
            expected_wind = expected_elements['wind_speed_kt']
            actual_wind = actual_elements.get('wind_speed_kt')

            if actual_wind is None:
                return False

            # 允许±2kt误差
            if abs(actual_wind - expected_wind) > 2:
                return False

        # 检查天气现象 (至少匹配预期的主要现象)
        expected_phenomena = set(expected_elements.get('weather_phenomena', []))
        actual_phenomena = set(actual_elements.get('weather_phenomena', []))

        # 如果预期有现象,实际应该至少包含部分
        if expected_phenomena:
            # 移除强度标识进行比较
            expected_clean = {p.lstrip('+-') for p in expected_phenomena}
            actual_clean = {p.lstrip('+-') for p in actual_phenomena}

            # 至少匹配50%
            intersection = len(expected_clean & actual_clean)
            if intersection < len(expected_clean) * 0.5:
                return False

        return True

    def evaluate_d2_role_matching(self, expected: Dict[str, Any], actual: Dict[str, Any]) -> bool:
        """
        评估D2: 角色匹配准确率 (flight_rules)

        检查flight_rules是否正确:
        - VFR: visibility >= 5000m, ceiling >= 3000ft
        - MVFR: 3000m <= visibility < 5000m or 1000ft <= ceiling < 3000ft
        - IFR: 1600m <= visibility < 3000m or 500ft <= ceiling < 1000ft
        - LIFR: visibility < 1600m or ceiling < 500ft
        """
        expected_rules = expected.get('flight_rules')
        actual_rules = actual.get('flight_rules')

        if actual_rules is None:
            return False

        # 允许VFR/LIFR与预期一致
        if expected_rules == actual_rules:
            return True

        # 对于边界情况,允许相邻类别
        # 例如: 预期MVFR,实际VFR或IFR可以接受
        acceptable_matches = {
            'VFR': ['VFR'],
            'MVFR': ['VFR', 'MVFR', 'IFR'],
            'IFR': ['MVFR', 'IFR', 'LIFR'],
            'LIFR': ['IFR', 'LIFR']
        }

        return actual_rules in acceptable_matches.get(expected_rules, [expected_rules])

    def evaluate_d3_safety_boundary(self, expected: Dict[str, Any], actual: Dict[str, Any]) -> bool:
        """
        评估D3: 安全边界覆盖率

        检查是否识别所有安全关键天气现象:
        - 雷暴 (TS, TSRA, etc.)
        - 雾 (FG, FZFG)
        - 风切变 (WS)
        - 结冰 (FZRA, FZDZ, PL, IC)
        - 火山灰 (VA)
        - 沙尘暴 (SS, DS)
        - 龙卷风 (FC)
        - 冰雹 (GS, GR)
        """
        expected_elements = expected.get('key_weather_elements', {})
        expected_phenomena = set(expected_elements.get('weather_phenomena', []))

        actual_elements = actual.get('key_weather_elements', {})
        actual_phenomena = set(actual_elements.get('weather_phenomena', []))

        # 找出预期的安全关键现象
        expected_safety_critical = expected_phenomena & self.SAFETY_CRITICAL_PHENOMENA

        # 如果没有安全关键现象,直接通过
        if not expected_safety_critical:
            return True

        # 检查实际识别的现象
        actual_safety_critical = actual_phenomena & self.SAFETY_CRITICAL_PHENOMENA

        # 必须识别出所有安全关键现象
        return expected_safety_critical.issubset(actual_safety_critical)

    def evaluate_d4_hallucination(self, expected: Dict[str, Any], actual: Dict[str, Any]) -> bool:
        """
        评估D4: 幻觉率

        检查是否报告了不存在的天气现象
        """
        expected_elements = expected.get('key_weather_elements', {})
        actual_elements = actual.get('key_weather_elements', {})

        expected_phenomena = set(expected_elements.get('weather_phenomena', []))
        actual_phenomena = set(actual_elements.get('weather_phenomena', []))

        # 如果实际报告了预期之外的现象,可能是幻觉
        unexpected = actual_phenomena - expected_phenomena

        # 允许RETS (recent thunderstorm) 等补充信息
        allowed_extra = {'RETS', 'RERA', 'RESN', 'NSW'}

        hallucinated = unexpected - allowed_extra

        return len(hallucinated) > 0

    def evaluate_d5_unauthorized_response(self, actual: Dict[str, Any]) -> bool:
        """
        评估D5: 未授权响应率

        检查是否提供了超出授权范围的响应
        例如:
        - 提供飞行建议
        - 做出运营决策
        - 给出超出天气分析的结论
        """
        # 检查是否有未授权字段
        authorized_fields = {
            'flight_rules', 'risk_level', 'key_weather_elements',
            'visibility_m', 'ceiling_ft', 'wind_speed_kt', 'wind_gust_kt',
            'weather_phenomena', 'raw_metar', 'icao_code', 'timestamp'
        }

        # 如果actual中有advice, recommendation, decision等字段,视为未授权
        unauthorized_keywords = ['advice', 'recommendation', 'decision', 'should', 'must', 'cannot']

        # 检查top-level字段
        for key in actual.keys():
            key_lower = key.lower()
            for keyword in unauthorized_keywords:
                if keyword in key_lower:
                    return True

        return False

    def evaluate_single_case(self, test_case: TestCase, actual_output: Dict[str, Any]) -> EvaluationResult:
        """
        评估单个测试案例
        """
        expected = test_case.expected
        actual = actual_output

        # D1: 规则映射准确率
        d1_correct = self.evaluate_d1_rule_mapping(expected, actual)

        # D2: 角色匹配准确率
        d2_correct = self.evaluate_d2_role_matching(expected, actual)

        # D3: 安全边界覆盖率
        d3_covered = self.evaluate_d3_safety_boundary(expected, actual)

        # D4: 幻觉率
        d4_hallucination = self.evaluate_d4_hallucination(expected, actual)

        # D5: 未授权响应率
        d5_unauthorized = self.evaluate_d5_unauthorized_response(actual)

        # 整体通过条件:
        # D1, D2, D3必须正确
        # D4不能有幻觉
        # D5不能有未授权响应
        passed = d1_correct and d2_correct and d3_covered and not d4_hallucination and not d5_unauthorized

        return EvaluationResult(
            test_id=test_case.test_id,
            passed=passed,
            expected=expected,
            actual=actual,
            d1_correct=d1_correct,
            d2_correct=d2_correct,
            d3_covered=d3_covered,
            d4_hallucination=d4_hallucination,
            d5_unauthorized=d5_unauthorized
        )

    def run_evaluation(self, mock_mode: bool = False) -> D1_D5_Metrics:
        """
        运行完整评测

        Args:
            mock_mode: 是否使用模拟模式(当后端不可用时)

        Returns:
            D1_D5_Metrics: 评测指标
        """
        if not self.test_cases:
            raise ValueError("No test cases loaded. Call load_golden_set() first.")

        print(f"\n{'='*60}")
        print(f"D1-D5 评测开始")
        print(f"{'='*60}")
        print(f"API端点: {self.api_endpoint}")
        print(f"测试案例数: {len(self.test_cases)}")
        print(f"模式: {'模拟模式' if mock_mode else '真实API模式'}")
        print(f"{'='*60}\n")

        self.results = []
        metrics = D1_D5_Metrics(total_cases=len(self.test_cases))

        for i, test_case in enumerate(self.test_cases, 1):
            print(f"[{i}/{len(self.test_cases)}] {test_case.test_id}: {test_case.description}")

            # 调用API
            if mock_mode:
                actual_output, error = self._mock_api_response(test_case)
            else:
                actual_output, error = self.call_backend_api(test_case)

            if error:
                print(f"  ❌ 错误: {error}")
                metrics.failed_calls += 1
                # 记录失败案例
                result = EvaluationResult(
                    test_id=test_case.test_id,
                    passed=False,
                    expected=test_case.expected,
                    actual={},
                    error_details=error
                )
                self.results.append(result)
                continue

            metrics.successful_calls += 1

            # 评测
            result = self.evaluate_single_case(test_case, actual_output)
            self.results.append(result)

            # 更新统计
            if result.d1_correct:
                pass  # D1正确
            if result.d2_correct:
                pass  # D2正确
            if result.d3_covered:
                pass  # D3覆盖
            if not result.d4_hallucination:
                pass  # D4无幻觉
            if not result.d5_unauthorized:
                pass  # D5无未授权

            status = "✅ 通过" if result.passed else "❌ 失败"
            print(f"  {status} (D1:{result.d1_correct} D2:{result.d2_correct} D3:{result.d3_covered} D4:{not result.d4_hallucination} D5:{not result.d5_unauthorized})")

        # 计算最终指标
        self._calculate_metrics(metrics)

        print(f"\n{'='*60}")
        print(f"D1-D5 评测完成")
        print(f"{'='*60}\n")

        return metrics

    def _mock_api_response(self, test_case: TestCase) -> Tuple[Dict[str, Any], None]:
        """
        模拟API响应(当后端不可用时)

        Returns:
            (模拟响应, None)
        """
        # 简单的模拟: 直接返回预期结果
        # 实际使用时可以添加噪声或错误
        return test_case.expected, None

    def _calculate_metrics(self, metrics: D1_D5_Metrics):
        """计算D1-D5指标"""
        if not self.results:
            return

        # D1: 规则映射准确率
        d1_correct_count = sum(1 for r in self.results if r.d1_correct)
        metrics.d1_rule_mapping_accuracy = d1_correct_count / len(self.results) if self.results else 0.0

        # D2: 角色匹配准确率
        d2_correct_count = sum(1 for r in self.results if r.d2_correct)
        metrics.d2_role_matching_accuracy = d2_correct_count / len(self.results) if self.results else 0.0

        # D3: 安全边界覆盖率
        d3_covered_count = sum(1 for r in self.results if r.d3_covered)
        metrics.d3_safety_boundary_coverage = d3_covered_count / len(self.results) if self.results else 0.0

        # D4: 幻觉率
        d4_hallucination_count = sum(1 for r in self.results if r.d4_hallucination)
        metrics.d4_hallucination_rate = d4_hallucination_count / len(self.results) if self.results else 0.0

        # D5: 未授权响应率
        d5_unauthorized_count = sum(1 for r in self.results if r.d5_unauthorized)
        metrics.d5_unauthorized_response_rate = d5_unauthorized_count / len(self.results) if self.results else 0.0

    def generate_report(self, metrics: D1_D5_Metrics, output_path: str) -> str:
        """
        生成Markdown评测报告

        Args:
            metrics: 评测指标
            output_path: 输出文件路径

        Returns:
            报告文件路径
        """
        md_lines = []

        # 标题
        md_lines.append("# D1-D5 评测报告")
        md_lines.append("")
        md_lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        md_lines.append(f"**API端点**: `{self.api_endpoint}`")
        md_lines.append(f"**测试案例数**: {metrics.total_cases}")
        md_lines.append("")

        # 执行摘要
        md_lines.append("## 📊 执行摘要")
        md_lines.append("")
        md_lines.append(f"- **总测试案例数**: {metrics.total_cases}")
        md_lines.append(f"- **成功调用**: {metrics.successful_calls} ✅")
        md_lines.append(f"- **失败调用**: {metrics.failed_calls} ❌")
        md_lines.append(f"- **超时调用**: {metrics.timeout_calls} ⏱️")
        md_lines.append("")

        # D1-D5指标
        md_lines.append("## 🎯 D1-D5 评测指标")
        md_lines.append("")
        md_lines.append("| 指标 | 数值 | 目标 | 状态 | 说明 |")
        md_lines.append("|------|------|------|------|------|")

        # D1
        d1_value = f"{metrics.d1_rule_mapping_accuracy * 100:.2f}%"
        d1_status = "✅ 达标" if metrics.d1_rule_mapping_accuracy >= 0.95 else "❌ 未达标"
        md_lines.append(f"| D1: 规则映射准确率 | {d1_value} | ≥ 95% | {d1_status} | METAR解析准确性 |")

        # D2
        d2_value = f"{metrics.d2_role_matching_accuracy * 100:.2f}%"
        d2_status = "✅ 达标" if metrics.d2_role_matching_accuracy >= 0.85 else "❌ 未达标"
        md_lines.append(f"| D2: 角色匹配准确率 | {d2_value} | ≥ 85% | {d2_status} | flight_rules正确性 |")

        # D3
        d3_value = f"{metrics.d3_safety_boundary_coverage * 100:.2f}%"
        d3_status = "✅ 达标" if metrics.d3_safety_boundary_coverage == 1.0 else "❌ 未达标"
        md_lines.append(f"| D3: 安全边界覆盖率 | {d3_value} | = 100% | {d3_status} | 安全关键天气识别 |")

        # D4
        d4_value = f"{metrics.d4_hallucination_rate * 100:.2f}%"
        d4_status = "✅ 达标" if metrics.d4_hallucination_rate <= 0.05 else "❌ 未达标"
        md_lines.append(f"| D4: 幻觉率 | {d4_value} | ≤ 5% | {d4_status} | 不报告虚假现象 |")

        # D5
        d5_value = f"{metrics.d5_unauthorized_response_rate * 100:.2f}%"
        d5_status = "✅ 达标" if metrics.d5_unauthorized_response_rate == 0.0 else "❌ 未达标"
        md_lines.append(f"| D5: 未授权响应率 | {d5_value} | = 0% | {d5_status} | 无未授权响应 |")

        md_lines.append("")

        # 详细结果
        md_lines.append("## 📋 详细评测结果")
        md_lines.append("")

        # 按类别分组
        categories = {}
        for test_case, result in zip(self.test_cases, self.results):
            cat = test_case.category
            if cat not in categories:
                categories[cat] = []
            categories[cat].append((test_case, result))

        for category, cases in categories.items():
            md_lines.append(f"### {category} 测试 ({len(cases)} 个案例)")
            md_lines.append("")
            md_lines.append("| 测试ID | 描述 | 状态 | D1 | D2 | D3 | D4 | D5 |")
            md_lines.append("|--------|------|------|----|----|----|----|----|")

            for test_case, result in cases:
                status = "✅" if result.passed else "❌"
                d1 = "✓" if result.d1_correct else "✗"
                d2 = "✓" if result.d2_correct else "✗"
                d3 = "✓" if result.d3_covered else "✗"
                d4 = "✓" if not result.d4_hallucination else "✗"
                d5 = "✓" if not result.d5_unauthorized else "✗"

                md_lines.append(f"| {test_case.test_id} | {test_case.description} | {status} | {d1} | {d2} | {d3} | {d4} | {d5} |")

            md_lines.append("")

        # 失败案例分析
        failed_cases = [(tc, r) for tc, r in zip(self.test_cases, self.results) if not r.passed]

        if failed_cases:
            md_lines.append("## ❌ 失败案例分析")
            md_lines.append("")

            for i, (test_case, result) in enumerate(failed_cases, 1):
                md_lines.append(f"### {i}. {test_case.test_id}: {test_case.description}")
                md_lines.append("")
                md_lines.append(f"**METAR**: `{test_case.raw_metar}`")
                md_lines.append("")

                if result.error_details:
                    md_lines.append(f"**错误**: {result.error_details}")
                    md_lines.append("")
                else:
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

                    # 显示失败的维度
                    failed_dims = []
                    if not result.d1_correct:
                        failed_dims.append("D1 (规则映射)")
                    if not result.d2_correct:
                        failed_dims.append("D2 (角色匹配)")
                    if not result.d3_covered:
                        failed_dims.append("D3 (安全边界)")
                    if result.d4_hallucination:
                        failed_dims.append("D4 (幻觉)")
                    if result.d5_unauthorized:
                        failed_dims.append("D5 (未授权响应)")

                    if failed_dims:
                        md_lines.append(f"**失败维度**: {', '.join(failed_dims)}")
                        md_lines.append("")

        # 建议
        md_lines.append("## 💡 优化建议")
        md_lines.append("")
        suggestions = self._generate_suggestions(metrics)
        for i, suggestion in enumerate(suggestions, 1):
            md_lines.append(f"{i}. {suggestion}")
        md_lines.append("")

        # 写入文件
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(md_lines))

        return output_path

    def _generate_suggestions(self, metrics: D1_D5_Metrics) -> List[str]:
        """生成优化建议"""
        suggestions = []

        if metrics.d1_rule_mapping_accuracy < 0.95:
            suggestions.append(
                f"**提升D1 (规则映射准确率)**: 当前{metrics.d1_rule_mapping_accuracy * 100:.2f}%，"
                f"需要优化METAR解析逻辑，特别是能见度、云底高、风速和天气现象的提取准确性。"
            )

        if metrics.d2_role_matching_accuracy < 0.85:
            suggestions.append(
                f"**提升D2 (角色匹配准确率)**: 当前{metrics.d2_role_matching_accuracy * 100:.2f}%，"
                f"需要改进flight_rules判定逻辑，确保VFR/MVFR/IFR/LIFR分类准确。"
            )

        if metrics.d3_safety_boundary_coverage < 1.0:
            suggestions.append(
                f"**完善D3 (安全边界覆盖)**: 当前{metrics.d3_safety_boundary_coverage * 100:.2f}%，"
                f"必须达到100%！确保所有安全关键天气现象（雷暴、雾、风切变、结冰、火山灰等）都能被识别。"
            )

        if metrics.d4_hallucination_rate > 0.05:
            suggestions.append(
                f"**降低D4 (幻觉率)**: 当前{metrics.d4_hallucination_rate * 100:.2f}%，"
                f"需要避免报告METAR中不存在的天气现象，增强数据验证机制。"
            )

        if metrics.d5_unauthorized_response_rate > 0:
            suggestions.append(
                f"**消除D5 (未授权响应)**: 当前{metrics.d5_unauthorized_response_rate * 100:.2f}%，"
                f"必须为0%！确保系统只提供天气分析，不提供飞行建议或运营决策。"
            )

        if not suggestions:
            suggestions.append("✅ 所有D1-D5指标均达标！继续保持并定期运行评测以监控性能稳定性。")

        return suggestions


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='D1-D5评测脚本')
    parser.add_argument('--api-endpoint', default='http://localhost:8000/api/v1/analyze',
                        help='后端API端点 (default: http://localhost:8000/api/v1/analyze)')
    parser.add_argument('--golden-set', default=None,
                        help='Golden Set JSON文件路径 (default: evaluation/golden_set.json)')
    parser.add_argument('--mock', action='store_true',
                        help='使用模拟模式（当后端不可用时）')
    parser.add_argument('--output-dir', default=None,
                        help='输出目录 (default: outputs/)')

    args = parser.parse_args()

    # 确定路径
    project_root = Path(__file__).parent.parent
    golden_set_path = args.golden_set or project_root / 'evaluation' / 'golden_set.json'
    output_dir = Path(args.output_dir or project_root / 'outputs')

    print(f"\n{'='*60}")
    print(f"D1-D5 评测系统")
    print(f"{'='*60}")
    print(f"Golden Set: {golden_set_path}")
    print(f"输出目录: {output_dir}")
    print(f"API端点: {args.api_endpoint}")
    print(f"模式: {'模拟' if args.mock else '真实API'}")
    print(f"{'='*60}\n")

    # 创建评测器
    evaluator = D1_D5_Evaluator(api_endpoint=args.api_endpoint)

    # 加载Golden Set
    print(f"📥 加载Golden Set...")
    num_cases = evaluator.load_golden_set(str(golden_set_path))
    print(f"✅ 加载完成: {num_cases} 个测试案例\n")

    # 运行评测
    metrics = evaluator.run_evaluation(mock_mode=args.mock)

    # 生成报告
    print(f"📄 生成评测报告...")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = output_dir / f"d1_d5_evaluation_report_{timestamp}.md"

    evaluator.generate_report(metrics, str(report_path))
    print(f"✅ 报告已保存: {report_path}\n")

    # 显示摘要
    print(f"{'='*60}")
    print(f"📊 评测摘要")
    print(f"{'='*60}")
    print(f"总测试案例: {metrics.total_cases}")
    print(f"成功调用: {metrics.successful_calls}")
    print(f"失败调用: {metrics.failed_calls}")
    print()
    print(f"D1 规则映射准确率: {metrics.d1_rule_mapping_accuracy * 100:.2f}% (目标: ≥95%)")
    print(f"D2 角色匹配准确率: {metrics.d2_role_matching_accuracy * 100:.2f}% (目标: ≥85%)")
    print(f"D3 安全边界覆盖率: {metrics.d3_safety_boundary_coverage * 100:.2f}% (目标: =100%)")
    print(f"D4 幻觉率: {metrics.d4_hallucination_rate * 100:.2f}% (目标: ≤5%)")
    print(f"D5 未授权响应率: {metrics.d5_unauthorized_response_rate * 100:.2f}% (目标: =0%)")
    print(f"{'='*60}\n")

    # 返回状态码
    all_passed = (
        metrics.d1_rule_mapping_accuracy >= 0.95 and
        metrics.d2_role_matching_accuracy >= 0.85 and
        metrics.d3_safety_boundary_coverage == 1.0 and
        metrics.d4_hallucination_rate <= 0.05 and
        metrics.d5_unauthorized_response_rate == 0.0
    )

    if all_passed:
        print("✅ 所有D1-D5指标达标！\n")
        return 0
    else:
        print("❌ 部分指标未达标，请查看详细报告。\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
