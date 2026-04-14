#!/usr/bin/env python3
"""
航空气象Agent PE评测脚本
评测指标：准确率、召回率、F1 Score
"""

import json
import time
import requests
from pathlib import Path
from typing import Dict, List, Any
from dataclasses import dataclass
from collections import defaultdict

# API配置
API_BASE_URL = "http://localhost:8000/api/v1"
ANALYZE_ENDPOINT = f"{API_BASE_URL}/analyze"

# 测试角色（dispatcher和controller合并后测试）
TEST_ROLES = ["pilot", "dispatcher", "mechanic"]

@dataclass
class EvaluationResult:
    """单个测试场景的评测结果"""
    scenario_id: str
    role: str
    success: bool
    response_time_ms: float
    expected_keys: List[str]
    extracted_keys: List[str]
    matched_keys: List[str]
    missing_keys: List[str]
    extra_keys: List[str]
    field_matches: Dict[str, bool]
    error_message: str = ""

@dataclass
class MetricSummary:
    """评测指标汇总"""
    total_scenarios: int
    successful_calls: int
    failed_calls: int
    avg_response_time_ms: float
    precision: float  # 提取字段准确率
    recall: float     # 期望字段召回率
    f1_score: float
    category_metrics: Dict[str, Dict[str, float]]
    role_metrics: Dict[str, Dict[str, float]]

def load_test_scenarios() -> List[Dict[str, Any]]:
    """加载测试场景"""
    scenarios_path = Path(__file__).parent / "metar_test_scenarios.json"
    with open(scenarios_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["test_scenarios"]

def call_analyze_api(metar_raw: str, role: str) -> Dict[str, Any]:
    """调用分析API"""
    payload = {
        "metar_raw": metar_raw,
        "role": role
    }
    
    start_time = time.time()
    response = requests.post(ANALYZE_ENDPOINT, json=payload, timeout=30)
    elapsed_ms = (time.time() - start_time) * 1000
    
    if response.status_code == 200:
        return {
            "success": True,
            "data": response.json(),
            "response_time_ms": elapsed_ms
        }
    else:
        return {
            "success": False,
            "error": f"HTTP {response.status_code}: {response.text}",
            "response_time_ms": elapsed_ms
        }

def extract_output_fields(response_data: Dict[str, Any]) -> Dict[str, Any]:
    """从API响应中提取关键字段"""
    # 提取结构化分析结果
    result = {}
    
    if "flight_rules" in response_data:
        result["flight_rules"] = response_data["flight_rules"]
    
    if "visibility_m" in response_data:
        result["visibility_m"] = response_data["visibility_m"]
    
    if "wind_speed_kt" in response_data:
        result["wind_speed_kt"] = response_data["wind_speed_kt"]
    
    if "wind_gust_kt" in response_data:
        result["wind_gust_kt"] = response_data["wind_gust_kt"]
    
    if "temperature_c" in response_data:
        result["temperature_c"] = response_data["temperature_c"]
    
    if "weather" in response_data:
        result["weather"] = response_data["weather"]
    
    if "risk_level" in response_data:
        result["risk_level"] = response_data["risk_level"]
    
    return result

def evaluate_single_scenario(
    scenario: Dict[str, Any],
    role: str
) -> EvaluationResult:
    """评测单个测试场景"""
    scenario_id = scenario["id"]
    metar_raw = scenario["metar_raw"]
    expected = scenario["expected"]
    
    # 调用API
    api_result = call_analyze_api(metar_raw, role)
    
    if not api_result["success"]:
        return EvaluationResult(
            scenario_id=scenario_id,
            role=role,
            success=False,
            response_time_ms=api_result["response_time_ms"],
            expected_keys=list(expected.keys()),
            extracted_keys=[],
            matched_keys=[],
            missing_keys=list(expected.keys()),
            extra_keys=[],
            field_matches={},
            error_message=api_result["error"]
        )
    
    # 提取输出字段
    extracted = extract_output_fields(api_result["data"])
    expected_keys = set(expected.keys())
    extracted_keys = set(extracted.keys())
    
    # 计算匹配
    matched_keys = []
    field_matches = {}
    
    for key in expected_keys:
        if key in extracted:
            expected_val = expected[key]
            extracted_val = extracted[key]
            
            # 处理不同类型的值比较
            if isinstance(expected_val, list):
                # 列表比较：检查是否包含所有期望元素
                match = all(elem in extracted_val for elem in expected_val)
            elif isinstance(expected_val, bool):
                match = extracted_val == expected_val
            elif isinstance(expected_val, (int, float)):
                # 数值允许5%误差
                if isinstance(extracted_val, (int, float)):
                    match = abs(extracted_val - expected_val) / max(expected_val, 1) < 0.05
                else:
                    match = False
            else:
                match = str(extracted_val).upper() == str(expected_val).upper()
            
            matched_keys.append(key)
            field_matches[key] = match
    
    missing_keys = list(expected_keys - set(extracted_keys))
    extra_keys = list(set(extracted_keys) - expected_keys)
    
    return EvaluationResult(
        scenario_id=scenario_id,
        role=role,
        success=True,
        response_time_ms=api_result["response_time_ms"],
        expected_keys=list(expected_keys),
        extracted_keys=list(extracted_keys),
        matched_keys=matched_keys,
        missing_keys=missing_keys,
        extra_keys=extra_keys,
        field_matches=field_matches
    )

def calculate_metrics(results: List[EvaluationResult]) -> MetricSummary:
    """计算评测指标"""
    total = len(results)
    successful = [r for r in results if r.success]
    failed = [r for r in results if not r.success]
    
    # 响应时间
    avg_response_time = sum(r.response_time_ms for r in results) / total if total > 0 else 0
    
    # 计算Precision和Recall
    total_expected_fields = 0
    total_extracted_fields = 0
    total_matched_fields = 0
    
    for r in successful:
        total_expected_fields += len(r.expected_keys)
        total_extracted_fields += len(r.extracted_keys)
        total_matched_fields += sum(1 for matched in r.field_matches.values() if matched)
    
    precision = total_matched_fields / total_extracted_fields if total_extracted_fields > 0 else 0
    recall = total_matched_fields / total_expected_fields if total_expected_fields > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    
    # 按类别统计
    category_metrics = defaultdict(lambda: {"precision": 0, "recall": 0, "f1": 0, "count": 0})
    role_metrics = defaultdict(lambda: {"precision": 0, "recall": 0, "f1": 0, "count": 0})
    
    # 加载场景分类信息
    scenarios = load_test_scenarios()
    scenario_categories = {s["id"]: s["category"] for s in scenarios}
    
    for r in successful:
        category = scenario_categories.get(r.scenario_id, "未知")
        category_metrics[category]["count"] += 1
        role_metrics[r.role]["count"] += 1
    
    return MetricSummary(
        total_scenarios=total,
        successful_calls=len(successful),
        failed_calls=len(failed),
        avg_response_time_ms=avg_response_time,
        precision=precision,
        recall=recall,
        f1_score=f1,
        category_metrics=dict(category_metrics),
        role_metrics=dict(role_metrics)
    )

def generate_report(results: List[EvaluationResult], metrics: MetricSummary) -> str:
    """生成评测报告"""
    report_lines = [
        "=" * 60,
        "航空气象Agent PE评测报告",
        "=" * 60,
        "",
        "## 总体指标",
        f"- 总测试场景: {metrics.total_scenarios}",
        f"- 成功调用: {metrics.successful_calls}",
        f"- 失败调用: {metrics.failed_calls}",
        f"- 平均响应时间: {metrics.avg_response_time_ms:.2f}ms",
        "",
        f"- **准确率 (Precision)**: {metrics.precision:.2%}",
        f"- **召回率 (Recall)**: {metrics.recall:.2%}",
        f"- **F1 Score**: {metrics.f1_score:.2%}",
        "",
        "## Bad Cases",
    ]
    
    # 分析失败案例
    bad_cases = [r for r in results if not r.success or 
                 any(not matched for matched in r.field_matches.values())]
    
    if bad_cases:
        for r in bad_cases[:10]:  # 只显示前10个
            report_lines.append(f"\n### {r.scenario_id} (角色: {r.role})")
            if not r.success:
                report_lines.append(f"- 错误: {r.error_message}")
            else:
                report_lines.append(f"- 缺失字段: {r.missing_keys}")
                report_lines.append(f"- 错误匹配: {[k for k, v in r.field_matches.items() if not v]}")
    else:
        report_lines.append("\n✅ 无Bad Case")
    
    return "\n".join(report_lines)

def main():
    """主评测流程"""
    print("🚀 开始PE评测...")
    print(f"📊 测试角色: {TEST_ROLES}")
    
    # 加载测试场景
    scenarios = load_test_scenarios()
    print(f"✅ 已加载 {len(scenarios)} 个测试场景")
    
    # 执行评测
    all_results = []
    
    for role in TEST_ROLES:
        print(f"\n🔍 评测角色: {role}")
        
        for i, scenario in enumerate(scenarios, 1):
            print(f"  [{i}/{len(scenarios)}] {scenario['id']}...", end=" ")
            
            result = evaluate_single_scenario(scenario, role)
            all_results.append(result)
            
            if result.success:
                print(f"✓ ({result.response_time_ms:.0f}ms)")
            else:
                print(f"✗ {result.error_message}")
    
    # 计算指标
    print("\n📊 计算评测指标...")
    metrics = calculate_metrics(all_results)
    
    # 生成报告
    report = generate_report(all_results, metrics)
    
    # 保存报告
    output_dir = Path(__file__).parent
    report_path = output_dir / "evaluation_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    
    print(f"\n✅ 评测完成!")
    print(f"📄 报告已保存: {report_path}")
    print(f"\n{report}")

if __name__ == "__main__":
    main()
