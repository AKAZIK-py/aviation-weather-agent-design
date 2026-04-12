"""
航空天气AI系统 - LLM-as-Judge评测模块
使用大语言模型作为评判者进行评测
"""

import aiohttp
import json
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from enum import Enum


class JudgeDimension(Enum):
    """评测维度"""
    ACCURACY = "accuracy"              # 准确性
    COMPLETENESS = "completeness"      # 完整性
    SAFETY = "safety"                  # 安全性
    ROLE_APPROPRIATENESS = "role_appropriateness"  # 角色适配性


@dataclass
class JudgeScore:
    """单个维度的评分"""
    dimension: JudgeDimension
    score: float  # 1-5分
    reasoning: str  # 评分理由


@dataclass
class JudgeResult:
    """LLM Judge评测结果"""
    overall_score: float  # 综合得分 1-5
    dimension_scores: List[JudgeScore]
    summary: str  # 总体评价
    suggestions: List[str]  # 改进建议


class LLMJudge:
    """
    LLM-as-Judge评测器
    使用百度千帆大模型作为评判者
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        初始化LLM Judge

        Args:
            api_key: 百度千帆API密钥（可选，默认使用内置密钥）
        """
        self.api_url = "https://qianfan.baidubce.com/v2/coding"
        self.api_key = api_key or "bce-v3/ALTAXXX-REDACTED-XXXXXXXXX/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
        self.model = "qianfan-code-latest"

        # 评测提示词模板（中文，航空专业）
        self.judge_prompt_template = """你是一名资深的航空天气分析专家，负责评测AI系统对航空天气报告（METAR）的分析质量。

请从以下四个维度对AI系统的输出进行评分（1-5分，5分为最高）：

## 评测维度说明：
1. **准确性（Accuracy）**：天气要素提取是否准确，飞行规则判断是否正确
2. **完整性（Completeness）**：是否完整分析了所有关键天气信息
3. **安全性（Safety）**：是否正确识别危险天气，风险评估是否合理
4. **角色适配性（Role Appropriateness）**：输出是否适合目标用户角色（{role}）

## 标准答案：
{golden_answer}

## AI系统输出：
{system_output}

## 评分要求：
- 1分：严重错误，存在危险幻觉或重大遗漏
- 2分：存在明显错误或不完整
- 3分：基本正确但有待改进
- 4分：良好，仅有轻微瑕疵
- 5分：优秀，完全符合要求

## 输出格式（请严格遵守JSON格式）：
{{
    "accuracy": {{
        "score": <1-5>,
        "reasoning": "<评分理由>"
    }},
    "completeness": {{
        "score": <1-5>,
        "reasoning": "<评分理由>"
    }},
    "safety": {{
        "score": <1-5>,
        "reasoning": "<评分理由>"
    }},
    "role_appropriateness": {{
        "score": <1-5>,
        "reasoning": "<评分理由>"
    }},
    "overall_score": <1-5>,
    "summary": "<总体评价>",
    "suggestions": ["<改进建议1>", "<改进建议2>", ...]
}}
"""

    async def judge(
        self,
        system_output: Dict[str, Any],
        golden_answer: Dict[str, Any],
        role: str = "atc"
    ) -> JudgeResult:
        """
        执行LLM-as-Judge评测

        Args:
            system_output: AI系统的输出
            golden_answer: 标准答案
            role: 目标用户角色（atc/ground/operations/maintenance）

        Returns:
            JudgeResult: 评测结果
        """
        # 角色映射
        role_names = {
            "atc": "空管人员",
            "ground": "地勤人员",
            "operations": "运控人员",
            "maintenance": "机务人员"
        }
        role_name = role_names.get(role, "空管人员")

        # 构建提示词
        prompt = self.judge_prompt_template.format(
            role=role_name,
            golden_answer=json.dumps(golden_answer, ensure_ascii=False, indent=2),
            system_output=json.dumps(system_output, ensure_ascii=False, indent=2)
        )

        # 调用API
        try:
            response_text = await self._call_api(prompt)
            result = self._parse_response(response_text)
            return result
        except Exception as e:
            # API调用失败，返回默认评分
            return self._get_default_result(str(e))

    async def _call_api(self, prompt: str) -> str:
        """
        调用百度千帆API

        Args:
            prompt: 提示词

        Returns:
            str: API响应文本
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.1,  # 低温度以保证稳定输出
            "max_tokens": 2000
        }

        timeout = aiohttp.ClientTimeout(total=30)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                self.api_url,
                headers=headers,
                json=payload
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    # 解析响应
                    if "result" in data:
                        return data["result"]
                    elif "choices" in data:
                        return data["choices"][0]["message"]["content"]
                    else:
                        raise ValueError(f"未知的API响应格式: {data}")
                else:
                    error_text = await response.text()
                    raise Exception(f"API调用失败: {response.status} - {error_text}")

    def _parse_response(self, response_text: str) -> JudgeResult:
        """
        解析API响应

        Args:
            response_text: API响应文本

        Returns:
            JudgeResult: 解析后的评测结果
        """
        try:
            # 尝试提取JSON
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1

            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                data = json.loads(json_str)
            else:
                raise ValueError("响应中未找到有效的JSON")

            # 解析各维度评分
            dimension_scores = []

            for dim in JudgeDimension:
                dim_data = data.get(dim.value, {})
                score = dim_data.get("score", 3)
                reasoning = dim_data.get("reasoning", "")

                # 确保分数在1-5范围内
                score = max(1, min(5, float(score)))

                dimension_scores.append(JudgeScore(
                    dimension=dim,
                    score=score,
                    reasoning=reasoning
                ))

            overall_score = data.get("overall_score", 3.0)
            overall_score = max(1.0, min(5.0, float(overall_score)))

            summary = data.get("summary", "")
            suggestions = data.get("suggestions", [])

            return JudgeResult(
                overall_score=overall_score,
                dimension_scores=dimension_scores,
                summary=summary,
                suggestions=suggestions
            )

        except json.JSONDecodeError as e:
            raise ValueError(f"JSON解析失败: {e}\n响应内容: {response_text}")

    def _get_default_result(self, error_message: str) -> JudgeResult:
        """
        获取默认评测结果（API调用失败时使用）

        Args:
            error_message: 错误信息

        Returns:
            JudgeResult: 默认评测结果
        """
        return JudgeResult(
            overall_score=3.0,
            dimension_scores=[
                JudgeScore(
                    dimension=JudgeDimension.ACCURACY,
                    score=3.0,
                    reasoning=f"API调用失败，使用默认评分: {error_message}"
                ),
                JudgeScore(
                    dimension=JudgeDimension.COMPLETENESS,
                    score=3.0,
                    reasoning="API调用失败，使用默认评分"
                ),
                JudgeScore(
                    dimension=JudgeDimension.SAFETY,
                    score=3.0,
                    reasoning="API调用失败，使用默认评分"
                ),
                JudgeScore(
                    dimension=JudgeDimension.ROLE_APPROPRIATENESS,
                    score=3.0,
                    reasoning="API调用失败，使用默认评分"
                )
            ],
            summary=f"评测失败: {error_message}，使用默认评分",
            suggestions=["请检查API连接状态"]
        )

    async def batch_judge(
        self,
        test_cases: List[Dict[str, Any]],
        role: str = "atc"
    ) -> List[JudgeResult]:
        """
        批量评测

        Args:
            test_cases: 测试案例列表，每个元素包含 predicted 和 expected
            role: 目标用户角色

        Returns:
            List[JudgeResult]: 评测结果列表
        """
        results = []

        for case in test_cases:
            result = await self.judge(
                case.get("predicted", {}),
                case.get("expected", {}),
                role
            )
            results.append(result)

        return results

    def calculate_judge_score(self, result: JudgeResult) -> float:
        """
        将LLM Judge评分转换为百分制

        Args:
            result: Judge结果

        Returns:
            float: 百分制得分
        """
        # 1-5分映射到0-100分
        # 1分 -> 0分
        # 5分 -> 100分
        return (result.overall_score - 1) / 4 * 100
