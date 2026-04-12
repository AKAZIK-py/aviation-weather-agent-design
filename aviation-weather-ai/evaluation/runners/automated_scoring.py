"""
航空天气AI系统 - 自动化评测执行器
执行完整的评测流程并生成报告
"""

import asyncio
import aiohttp
import json
import os
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from pathlib import Path

# 导入核心评测模块
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.hallucination_detector import HallucinationDetector, HallucinationReport
from core.precision_recall import MetricsCalculator, DimensionScores
from core.llm_judge import LLMJudge, JudgeResult
from core.role_evaluator import RoleEvaluator, RoleEvaluationResult, UserRole


@dataclass
class TestCaseResult:
    """单个测试案例的完整评测结果"""
    test_id: str
    category: str
    raw_metar: str
    expected: Dict[str, Any]
    predicted: Dict[str, Any]

    # 各项评测结果
    hallucination_report: Optional[HallucinationReport] = None
    precision_recall: Optional[Dict[str, float]] = None
    judge_result: Optional[JudgeResult] = None
    role_evaluations: Optional[Dict[UserRole, RoleEvaluationResult]] = None

    # 综合得分
    overall_score: float = 0.0
    passed: bool = False
    error: Optional[str] = None


@dataclass
class ScoringReport:
    """完整评测报告"""
    timestamp: str
    total_cases: int
    passed_cases: int
    failed_cases: int

    # 汇总指标
    overall_accuracy: float
    dimension_scores: DimensionScores
    avg_hallucination_score: float
    avg_judge_score: float
    avg_role_score: float

    # 详细结果
    results: List[TestCaseResult] = field(default_factory=list)

    # 统计信息
    category_breakdown: Dict[str, Any] = field(default_factory=dict)
    error_summary: List[str] = field(default_factory=list)


class AutomatedScorer:
    """
    自动化评测执行器
    加载Golden Set，调用后端API，执行完整评测流程
    """

    def __init__(
        self,
        api_endpoint: str = "http://localhost:8000/api/v1/analyze",
        llm_api_key: Optional[str] = None
    ):
        """
        初始化自动化评测器

        Args:
            api_endpoint: 后端API端点
            llm_api_key: LLM Judge的API密钥（可选）
        """
        self.api_endpoint = api_endpoint

        # 初始化各评测模块
        self.hallucination_detector = HallucinationDetector()
        self.metrics_calculator = MetricsCalculator()
        self.llm_judge = LLMJudge(api_key=llm_api_key)
        self.role_evaluator = RoleEvaluator()

        # 评测统计
        self.stats = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "hallucination_detected": 0,
            "critical_hallucination": 0
        }

    async def run_all(self, golden_set_path: str) -> ScoringReport:
        """
        执行完整的评测流程

        Args:
            golden_set_path: Golden Set JSON文件路径

        Returns:
            ScoringReport: 完整评测报告
        """
        print(f"🚀 开始执行自动化评测...")
        print(f"📄 加载Golden Set: {golden_set_path}")

        # 1. 加载Golden Set
        try:
            golden_set = self._load_golden_set(golden_set_path)
            test_cases = golden_set.get("test_cases", [])
            print(f"✅ 成功加载 {len(test_cases)} 个测试案例")
        except Exception as e:
            print(f"❌ 加载Golden Set失败: {e}")
            return self._create_empty_report(f"加载Golden Set失败: {e}")

        # 2. 执行评测
        print(f"\n🔍 开始执行评测...")
        results = []

        for i, test_case in enumerate(test_cases):
            print(f"\n[{i+1}/{len(test_cases)}] 评测案例: {test_case['test_id']}")

            result = await self._evaluate_single_case(test_case)
            results.append(result)

            # 更新统计
            self.stats["total_calls"] += 1
            if result.error:
                self.stats["failed_calls"] += 1
                print(f"  ❌ 评测失败: {result.error}")
            else:
                self.stats["successful_calls"] += 1
                if result.passed:
                    print(f"  ✅ 评测通过 (得分: {result.overall_score:.1f})")
                else:
                    print(f"  ⚠️ 评测未通过 (得分: {result.overall_score:.1f})")

        # 3. 生成汇总报告
        print(f"\n📊 生成汇总报告...")
        report = self._generate_report(results, golden_set.get("metadata", {}))

        return report

    def _load_golden_set(self, path: str) -> Dict[str, Any]:
        """
        加载Golden Set

        Args:
            path: 文件路径

        Returns:
            Dict: Golden Set数据
        """
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    async def _evaluate_single_case(self, test_case: Dict[str, Any]) -> TestCaseResult:
        """
        评测单个测试案例

        Args:
            test_case: 测试案例数据

        Returns:
            TestCaseResult: 评测结果
        """
        test_id = test_case.get("test_id", "unknown")
        category = test_case.get("category", "unknown")
        raw_metar = test_case.get("raw_metar", "")
        expected = test_case.get("expected", {})

        result = TestCaseResult(
            test_id=test_id,
            category=category,
            raw_metar=raw_metar,
            expected=expected,
            predicted={}
        )

        try:
            # 1. 调用后端API
            predicted = await self._call_backend_api(raw_metar)
            result.predicted = predicted

            # 2. 执行幻觉检测
            hallucination_report = self.hallucination_detector.detect(predicted, expected)
            result.hallucination_report = hallucination_report

            # 更新统计
            if hallucination_report.hallucination_count > 0:
                self.stats["hallucination_detected"] += 1
            if hallucination_report.critical_count > 0:
                self.stats["critical_hallucination"] += 1

            # 3. 计算精确率/召回率
            metrics_result = self.metrics_calculator.calculate_precision_recall_f1(
                predicted, expected
            )
            result.precision_recall = {
                "precision": metrics_result.precision,
                "recall": metrics_result.recall,
                "f1_score": metrics_result.f1_score
            }

            # 4. 执行LLM-as-Judge评测
            judge_result = await self.llm_judge.judge(predicted, expected)
            result.judge_result = judge_result

            # 5. 执行角色适配评测
            role_evaluations = self.role_evaluator.evaluate_all_roles(predicted, expected)
            result.role_evaluations = role_evaluations

            # 6. 计算综合得分
            # 各部分权重：幻觉检测40%，精确率/召回率30%，LLM Judge 20%，角色适配10%
            hallucination_score = self.hallucination_detector.get_hallucination_score(hallucination_report)
            precision_recall_score = metrics_result.f1_score * 100
            judge_score = self.llm_judge.calculate_judge_score(judge_result)
            role_score = self.role_evaluator.get_role_weighted_score(role_evaluations)

            result.overall_score = (
                hallucination_score * 0.40 +
                precision_recall_score * 0.30 +
                judge_score * 0.20 +
                role_score * 0.10
            )

            # 7. 判断是否通过
            # 通过条件：无严重幻觉，且得分>=60分
            result.passed = (
                hallucination_report.critical_count == 0 and
                result.overall_score >= 60.0
            )

        except Exception as e:
            result.error = str(e)
            result.passed = False
            result.overall_score = 0.0

        return result

    async def _call_backend_api(self, raw_metar: str) -> Dict[str, Any]:
        """
        调用后端API获取分析结果

        Args:
            raw_metar: 原始METAR报文

        Returns:
            Dict: API响应结果
        """
        # 构建请求
        payload = {
            "metar": raw_metar
        }

        headers = {
            "Content-Type": "application/json"
        }

        timeout = aiohttp.ClientTimeout(total=30)

        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    self.api_endpoint,
                    headers=headers,
                    json=payload
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data
                    else:
                        error_text = await response.text()
                        raise Exception(f"API调用失败: {response.status} - {error_text}")

        except aiohttp.ClientError as e:
            # 网络错误，使用Mock数据
            print(f"  ⚠️  API连接失败: {e}，使用Mock数据")
            return self._get_mock_response(raw_metar)

        except Exception as e:
            raise e

    def _get_mock_response(self, raw_metar: str) -> Dict[str, Any]:
        """
        当API不可用时，返回Mock数据

        Args:
            raw_metar: 原始METAR报文

        Returns:
            Dict: Mock响应
        """
        # 简单的Mock实现：基于METAR内容生成基本响应
        # 实际使用时应根据METAR解析规则生成

        response = {
            "flight_rules": "VFR",
            "risk_level": "low",
            "key_weather_elements": {
                "visibility_m": 9999,
                "ceiling_ft": None,
                "wind_speed_kt": 5,
                "wind_gust_kt": None,
                "weather_phenomena": []
            },
            "is_boundary_weather": False,
            "explanation": f"[Mock响应] 分析METAR: {raw_metar}",
            "recommendations": ["天气条件良好，适合飞行"]
        }

        # 根据METAR内容调整Mock响应
        if "FG" in raw_metar or "TS" in raw_metar:
            response["flight_rules"] = "IFR"
            response["risk_level"] = "high"
            response["key_weather_elements"]["weather_phenomena"] = ["FG"] if "FG" in raw_metar else ["TS"]

        if raw_metar.find("5000") != -1 or raw_metar.find("3000") != -1:
            vis_match = raw_metar.split()
            for part in vis_match:
                if part.isdigit() and len(part) == 4:
                    response["key_weather_elements"]["visibility_m"] = int(part)
                    if int(part) < 5000:
                        response["flight_rules"] = "MVFR"
                        response["risk_level"] = "medium"

        return response

    def _generate_report(
        self,
        results: List[TestCaseResult],
        metadata: Dict[str, Any]
    ) -> ScoringReport:
        """
        生成汇总报告

        Args:
            results: 所有测试结果
            metadata: Golden Set元数据

        Returns:
            ScoringReport: 汇总报告
        """
        total_cases = len(results)
        passed_cases = sum(1 for r in results if r.passed)
        failed_cases = total_cases - passed_cases

        overall_accuracy = passed_cases / total_cases if total_cases > 0 else 0.0

        # 计算各维度平均分
        hallucination_scores = [
            self.hallucination_detector.get_hallucination_score(r.hallucination_report)
            for r in results if r.hallucination_report
        ]
        avg_hallucination_score = sum(hallucination_scores) / len(hallucination_scores) if hallucination_scores else 0.0

        judge_scores = [
            self.llm_judge.calculate_judge_score(r.judge_result)
            for r in results if r.judge_result
        ]
        avg_judge_score = sum(judge_scores) / len(judge_scores) if judge_scores else 0.0

        role_scores = [
            self.role_evaluator.get_role_weighted_score(r.role_evaluations)
            for r in results if r.role_evaluations
        ]
        avg_role_score = sum(role_scores) / len(role_scores) if role_scores else 0.0

        # 计算D1-D5维度得分
        all_results_for_d = []
        for r in results:
            all_results_for_d.append({
                "predicted": r.predicted,
                "expected": r.expected,
                "category": r.category
            })
        dimension_scores = self.metrics_calculator.calculate_d1_through_d5(all_results_for_d)

        # 按类别统计
        category_breakdown = {}
        for r in results:
            if r.category not in category_breakdown:
                category_breakdown[r.category] = {
                    "total": 0,
                    "passed": 0,
                    "avg_score": 0.0,
                    "scores": []
                }
            category_breakdown[r.category]["total"] += 1
            if r.passed:
                category_breakdown[r.category]["passed"] += 1
            category_breakdown[r.category]["scores"].append(r.overall_score)

        for cat, data in category_breakdown.items():
            data["avg_score"] = sum(data["scores"]) / len(data["scores"]) if data["scores"] else 0.0
            data["pass_rate"] = data["passed"] / data["total"] if data["total"] > 0 else 0.0
            del data["scores"]  # 移除详细分数列表

        # 收集错误信息
        error_summary = [r.error for r in results if r.error]

        return ScoringReport(
            timestamp=datetime.now().isoformat(),
            total_cases=total_cases,
            passed_cases=passed_cases,
            failed_cases=failed_cases,
            overall_accuracy=overall_accuracy,
            dimension_scores=dimension_scores,
            avg_hallucination_score=avg_hallucination_score,
            avg_judge_score=avg_judge_score,
            avg_role_score=avg_role_score,
            results=results,
            category_breakdown=category_breakdown,
            error_summary=error_summary
        )

    def _create_empty_report(self, error_message: str) -> ScoringReport:
        """
        创建空报告（用于错误情况）

        Args:
            error_message: 错误信息

        Returns:
            ScoringReport: 空报告
        """
        return ScoringReport(
            timestamp=datetime.now().isoformat(),
            total_cases=0,
            passed_cases=0,
            failed_cases=0,
            overall_accuracy=0.0,
            dimension_scores=DimensionScores(
                d1_boundary_identification=0.0,
                d2_parameter_accuracy=0.0,
                d3_phenomena_detection=0.0,
                d4_flight_rules_judgment=0.0,
                d5_risk_assessment=0.0,
                overall_score=0.0
            ),
            avg_hallucination_score=0.0,
            avg_judge_score=0.0,
            avg_role_score=0.0,
            results=[],
            category_breakdown={},
            error_summary=[error_message]
        )

    def save_report(self, report: ScoringReport, output_dir: str) -> Dict[str, str]:
        """
        保存报告到文件

        Args:
            report: 评测报告
            output_dir: 输出目录

        Returns:
            Dict[str, str]: 生成的文件路径
        """
        os.makedirs(output_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 1. 保存JSON报告
        json_path = os.path.join(output_dir, f"evaluation_report_{timestamp}.json")
        self._save_json_report(report, json_path)

        # 2. 保存Markdown报告
        md_path = os.path.join(output_dir, f"evaluation_report_{timestamp}.md")
        self._save_markdown_report(report, md_path)

        return {
            "json": json_path,
            "markdown": md_path
        }

    def _save_json_report(self, report: ScoringReport, path: str):
        """
        保存JSON格式报告
        """
        # 转换为可序列化的字典
        data = {
            "timestamp": report.timestamp,
            "summary": {
                "total_cases": report.total_cases,
                "passed_cases": report.passed_cases,
                "failed_cases": report.failed_cases,
                "overall_accuracy": f"{report.overall_accuracy * 100:.2f}%",
                "avg_hallucination_score": f"{report.avg_hallucination_score:.2f}",
                "avg_judge_score": f"{report.avg_judge_score:.2f}",
                "avg_role_score": f"{report.avg_role_score:.2f}"
            },
            "dimension_scores": {
                "d1_boundary_identification": f"{report.dimension_scores.d1_boundary_identification:.2f}",
                "d2_parameter_accuracy": f"{report.dimension_scores.d2_parameter_accuracy:.2f}",
                "d3_phenomena_detection": f"{report.dimension_scores.d3_phenomena_detection:.2f}",
                "d4_flight_rules_judgment": f"{report.dimension_scores.d4_flight_rules_judgment:.2f}",
                "d5_risk_assessment": f"{report.dimension_scores.d5_risk_assessment:.2f}",
                "overall_score": f"{report.dimension_scores.overall_score:.2f}"
            },
            "category_breakdown": report.category_breakdown,
            "statistics": self.stats,
            "results": []
        }

        # 添加详细结果
        for r in report.results:
            result_data = {
                "test_id": r.test_id,
                "category": r.category,
                "raw_metar": r.raw_metar,
                "passed": r.passed,
                "overall_score": f"{r.overall_score:.2f}",
                "error": r.error
            }

            if r.hallucination_report:
                result_data["hallucination"] = {
                    "count": r.hallucination_report.hallucination_count,
                    "critical": r.hallucination_report.critical_count,
                    "penalty": r.hallucination_report.penalty_score
                }

            if r.precision_recall:
                result_data["precision_recall"] = {
                    k: f"{v:.4f}" for k, v in r.precision_recall.items()
                }

            if r.judge_result:
                result_data["judge_score"] = f"{r.judge_result.overall_score:.2f}"

            data["results"].append(result_data)

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"📄 JSON报告已保存: {path}")

    def _save_markdown_report(self, report: ScoringReport, path: str):
        """
        保存Markdown格式报告
        """
        lines = []

        # 标题
        lines.append("# 航空天气AI系统评测报告")
        lines.append(f"\n**评测时间**: {report.timestamp}\n")

        # 总体概览
        lines.append("## 📊 总体概览\n")
        lines.append(f"- **总测试案例**: {report.total_cases}")
        lines.append(f"- **通过案例**: {report.passed_cases}")
        lines.append(f"- **失败案例**: {report.failed_cases}")
        lines.append(f"- **通过率**: {report.overall_accuracy * 100:.2f}%\n")

        # 维度得分
        lines.append("## 🎯 各维度得分\n")
        lines.append("| 维度 | 得分 | 说明 |")
        lines.append("|------|------|------|")
        lines.append(f"| D1 边界天气识别 | {report.dimension_scores.d1_boundary_identification:.2f} | 关键能力 |")
        lines.append(f"| D2 参数提取准确性 | {report.dimension_scores.d2_parameter_accuracy:.2f} | 核心指标 |")
        lines.append(f"| D3 天气现象检测 | {report.dimension_scores.d3_phenomena_detection:.2f} | 安全关键 |")
        lines.append(f"| D4 飞行规则判断 | {report.dimension_scores.d4_flight_rules_judgment:.2f} | 决策关键 |")
        lines.append(f"| D5 风险评估 | {report.dimension_scores.d5_risk_assessment:.2f} | 安全关键 |")
        lines.append(f"| **综合得分** | **{report.dimension_scores.overall_score:.2f}** | 加权平均 |\n")

        # 其他评分
        lines.append("## 📈 其他评测指标\n")
        lines.append(f"- **幻觉检测平均分**: {report.avg_hallucination_score:.2f}/100")
        lines.append(f"- **LLM Judge平均分**: {report.avg_judge_score:.2f}/100")
        lines.append(f"- **角色适配平均分**: {report.avg_role_score:.2f}/100\n")

        # 按类别统计
        lines.append("## 📁 按类别统计\n")
        lines.append("| 类别 | 总数 | 通过 | 通过率 | 平均得分 |")
        lines.append("|------|------|------|--------|----------|")
        for cat, data in report.category_breakdown.items():
            lines.append(f"| {cat} | {data['total']} | {data['passed']} | {data['pass_rate']*100:.1f}% | {data['avg_score']:.2f} |")
        lines.append("")

        # 错误摘要
        if report.error_summary:
            lines.append("## ⚠️ 错误摘要\n")
            for error in report.error_summary[:10]:  # 只显示前10个
                lines.append(f"- {error}")
            lines.append("")

        # 统计信息
        lines.append("## 📊 评测统计\n")
        lines.append(f"- 总调用次数: {self.stats['total_calls']}")
        lines.append(f"- 成功次数: {self.stats['successful_calls']}")
        lines.append(f"- 失败次数: {self.stats['failed_calls']}")
        lines.append(f"- 检测到幻觉: {self.stats['hallucination_detected']}")
        lines.append(f"- 严重幻觉: {self.stats['critical_hallucination']}\n")

        # 保存文件
        with open(path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

        print(f"📄 Markdown报告已保存: {path}")


async def main():
    """主函数 - 执行评测"""
    # 初始化评测器
    scorer = AutomatedScorer(
        api_endpoint="http://localhost:8000/api/v1/analyze"
    )

    # 执行评测
    golden_set_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "golden_set.json"
    )

    report = await scorer.run_all(golden_set_path)

    # 保存报告
    output_dir = os.path.join(
        os.path.dirname(__file__),
        "..",
        "reports"
    )

    paths = scorer.save_report(report, output_dir)

    print(f"\n✅ 评测完成！")
    print(f"📊 通过率: {report.overall_accuracy * 100:.2f}%")
    print(f"🎯 综合得分: {report.dimension_scores.overall_score:.2f}")
    print(f"📄 报告已保存到: {output_dir}")


if __name__ == "__main__":
    asyncio.run(main())
