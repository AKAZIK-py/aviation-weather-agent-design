#!/usr/bin/env python3
"""
航空气象Agent Claude Code Judge 裁判模块

用 Claude Code CLI (claude -p) 做裁判，评估Agent输出质量。

核心接口:
  - judge_case(case, agent_output, timeout=30) -> dict
  - run_judge_on_cases(cases_with_outputs, timeout=30) -> list[dict]
"""

from __future__ import annotations

import json
import re
import subprocess
from typing import List, Tuple


def _build_judge_prompt(case: dict, agent_output: str) -> str:
    """构建发给 Claude Code 的裁判 prompt"""
    metar = case.get("metar", "")
    parsed = case.get("parsed", {})
    role = case.get("role", "")
    query = case.get("query", "")

    return f"""你是航空气象Agent的评测裁判。

METAR原文: {metar}
解析数据: {json.dumps(parsed, ensure_ascii=False)}
角色: {role}
用户问题: {query}
Agent输出:
{agent_output}

请评估Agent输出，返回JSON:
{{
  "usable": true/false,
  "verbose_without_advice": true/false,
  "is_template": true/false,
  "hallucination": false,
  "hallucination_details": "",
  "reason": "一句话说明"
}}

只返回JSON，不要其他内容。"""


def _parse_judge_result(raw_stdout: str, raw_stderr: str = "") -> dict:
    """解析 claude -p --output-format json 的返回结果"""
    default_fail = {
        "usable": False,
        "verbose_without_advice": True,
        "is_template": True,
        "hallucination": True,
        "hallucination_details": "judge解析失败",
        "reason": "裁判解析失败",
    }

    if not raw_stdout.strip():
        return default_fail

    try:
        claude_result = json.loads(raw_stdout)
        # claude -p --output-format json 返回 {"result": "...", ...}
        judge_text = claude_result.get("result", "")
        if not judge_text:
            # 有些版本直接返回文本字段
            judge_text = claude_result.get("content", raw_stdout)
    except json.JSONDecodeError:
        # 如果不是外层JSON，直接把整个stdout当作文本处理
        judge_text = raw_stdout

    # 从文本中提取 JSON 块
    # 优先匹配 ```json ... ``` 代码块
    code_block_match = re.search(r"```json\s*(\{.*?\})\s*```", judge_text, re.DOTALL)
    if code_block_match:
        try:
            return json.loads(code_block_match.group(1))
        except json.JSONDecodeError:
            pass

    # 回退: 匹配任意 {...} 块
    json_match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", judge_text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    return default_fail


def judge_case(case: dict, agent_output: str, timeout: int = 30) -> dict:
    """
    对单条 case 的 agent_output 进行裁判评估。

    Args:
        case: 包含 metar, parsed, role, query 的测试用例
        agent_output: Agent 生成的输出文本
        timeout: claude CLI 超时秒数

    Returns:
        裁判结果 dict，包含:
          - usable: bool - 能否直接给角色使用
          - verbose_without_advice: bool - 是否说了很多但没给建议
          - is_template: bool - 是否在套模板
          - hallucination: bool - 是否有幻觉
          - hallucination_details: str - 幻觉详情
          - reason: str - 一句话说明
    """
    prompt = _build_judge_prompt(case, agent_output)

    try:
        result = subprocess.run(
            [
                "claude",
                "-p",
                prompt,
                "--max-turns",
                "1",
                "--output-format",
                "json",
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return _parse_judge_result(result.stdout, result.stderr)
    except subprocess.TimeoutExpired:
        return {
            "usable": False,
            "verbose_without_advice": True,
            "is_template": True,
            "hallucination": True,
            "hallucination_details": f"judge超时({timeout}s)",
            "reason": f"裁判调用超时({timeout}s)",
        }
    except FileNotFoundError:
        return {
            "usable": False,
            "verbose_without_advice": True,
            "is_template": True,
            "hallucination": True,
            "hallucination_details": "claude CLI 未安装",
            "reason": "claude CLI 未找到，请确认已安装 Claude Code",
        }
    except Exception as e:
        return {
            "usable": False,
            "verbose_without_advice": True,
            "is_template": True,
            "hallucination": True,
            "hallucination_details": f"judge异常: {e}",
            "reason": f"裁判异常: {e}",
        }


def run_judge_on_cases(
    cases_with_outputs: List[Tuple[dict, str]], timeout: int = 30
) -> List[dict]:
    """
    批量评测函数。

    Args:
        cases_with_outputs: [(case, agent_output), ...] 列表
        timeout: 每条 case 的 claude CLI 超时秒数

    Returns:
        每条 case 的 judge 结果列表，与输入顺序一致
    """
    results = []
    for i, (case, agent_output) in enumerate(cases_with_outputs):
        judge_result = judge_case(case, agent_output, timeout=timeout)
        judge_result["_case_index"] = i
        results.append(judge_result)
    return results
