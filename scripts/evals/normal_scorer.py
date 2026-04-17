#!/usr/bin/env python3
"""
普通评分子代理 — 调用 Claude Code CLI 对 Agent 输出进行 LLM 评分。

负责 4 个主指标 + 2 个辅助指标:
  task_complete, key_info_hit, usable, template, hallucination

输出: results/normal_scores.jsonl
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parents[2]
SCORING_DOC = ROOT_DIR / "scoring" / "CLAUDE.md"

# ---------------------------------------------------------------------------

def _build_batch_prompt(cases: List[Dict[str, Any]]) -> str:
    """构建批量评分 prompt，一次处理多条 case。"""
    scoring_rules = ""
    if SCORING_DOC.exists():
        scoring_rules = SCORING_DOC.read_text(encoding="utf-8")

    cases_text = ""
    for case in cases:
        case_id = case.get("case_id", "unknown")
        query = case.get("query", "")
        metar = case.get("metar_text", case.get("metar", ""))
        agent_output = case.get("agent_output", case.get("output", ""))
        expected_key_info = case.get("expected_key_info", [])
        cases_text += f"""
### Case: {case_id}
- 用户问题: {query}
- METAR: {metar}
- 预期关键信息: {json.dumps(expected_key_info, ensure_ascii=False)}
- Agent 输出: {agent_output[:800]}

"""

    return f"""你是一个航空领域评测员。请根据以下评分规则对每条 Case 的 Agent 输出进行评分。

## 评分规则
{scoring_rules}

## 待评测 Cases
{cases_text}
## 评分要求
对每条 case 输出一个 JSON 对象，最终输出一个 JSON 数组。格式:
```json
[
  {{
    "case_id": "STD_001",
    "task_complete": 0或1,
    "key_info_hit": 0或1,
    "usable": 0或1,
    "template": 0或1,
    "hallucination": 0或1,
    "reasoning": {{
      "task_complete": "理由",
      "key_info_hit": "理由",
      "usable": "理由",
      "template": "理由",
      "hallucination": "理由"
    }}
  }}
]
```
只输出 JSON 数组，不要输出任何其他内容。"""


def _build_prompt(case_data: Dict[str, Any]) -> str:
    """构建单条 case 评分 prompt（保留兼容）。"""
    return _build_batch_prompt([case_data])


def _call_claude_cli(prompt: str, timeout: int = 300) -> str:
    """调用 claude -p 获取评分结果。"""
    try:
        result = subprocess.run(
            ["claude", "-p", "--model", "claude-sonnet-4-20250514"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            return json.dumps({"error": f"claude CLI exited with code {result.returncode}: {result.stderr[:200]}"})
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        return json.dumps({"error": "claude CLI timeout"})
    except FileNotFoundError:
        return json.dumps({"error": "claude CLI not found"})
    except Exception as exc:
        return json.dumps({"error": f"claude CLI error: {exc}"})


def _parse_batch_response(raw: str, case_ids: List[str]) -> List[Dict[str, Any]]:
    """从 Claude CLI 输出中解析 JSON 数组。"""
    if "```json" in raw:
        start = raw.index("```json") + 7
        end = raw.index("```", start)
        raw = raw[start:end].strip()
    elif "```" in raw:
        start = raw.index("```") + 3
        end = raw.index("```", start)
        raw = raw[start:end].strip()

    try:
        data = json.loads(raw)
        if isinstance(data, list):
            results = []
            for item in data:
                required = ["task_complete", "key_info_hit", "usable", "template", "hallucination"]
                for field in required:
                    if field not in item:
                        item[field] = 0
                if "reasoning" not in item:
                    item["reasoning"] = {}
                results.append(item)
            return results
    except json.JSONDecodeError:
        pass

    # 解析失败，返回空结果
    return [{
        "case_id": cid,
        "task_complete": 0, "key_info_hit": 0, "usable": 0,
        "template": 0, "hallucination": 0,
        "reasoning": {"error": f"JSON parse failed: {raw[:200]}"},
        "parse_error": True,
    } for cid in case_ids]


def _parse_llm_response(raw: str, case_id: str) -> Dict[str, Any]:
    """从 Claude CLI 输出中解析单条 JSON（保留兼容）。"""
    results = _parse_batch_response(raw, [case_id])
    return results[0] if results else {"case_id": case_id, "error": "empty"}


def score_case_normal(case_data: Dict[str, Any]) -> Dict[str, Any]:
    """单条评分（保留兼容）。"""
    return score_batch_normal([case_data])[0]


def score_batch_normal(cases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """批量评分：一次 Claude Code 调用处理多条 case。"""
    case_ids = [c.get("case_id", f"case_{i}") for i, c in enumerate(cases)]
    prompt = _build_batch_prompt(cases)
    raw_response = _call_claude_cli(prompt)
    results = _parse_batch_response(raw_response, case_ids)

    # 确保结果数量匹配
    while len(results) < len(cases):
        results.append({
            "case_id": case_ids[len(results)],
            "task_complete": 0, "key_info_hit": 0, "usable": 0,
            "template": 0, "hallucination": 0,
            "reasoning": {"error": "missing from batch response"},
        })
    return results[:len(cases)]


def score_all_normal(
    cases: List[Dict[str, Any]],
    output_path: Optional[Path] = None,
    batch_size: int = 10,
) -> List[Dict[str, Any]]:
    """
    批量普通评分，每 batch_size 条 case 调用一次 Claude Code。
    """
    results = []
    total = len(cases)

    for batch_start in range(0, total, batch_size):
        batch_end = min(batch_start + batch_size, total)
        batch = cases[batch_start:batch_end]
        batch_num = batch_start // batch_size + 1
        total_batches = (total + batch_size - 1) // batch_size

        print(f"[normal_scorer] Batch {batch_num}/{total_batches} ({len(batch)} cases) ...", flush=True)

        try:
            batch_results = score_batch_normal(batch)
        except Exception as exc:
            batch_results = [{
                "case_id": c.get("case_id", f"case_{i}"),
                "task_complete": 0, "key_info_hit": 0, "usable": 0,
                "template": 0, "hallucination": 0,
                "reasoning": {"error": str(exc)},
                "scorer_exception": True,
            } for i, c in enumerate(batch)]

        results.extend(batch_results)

        if output_path:
            with open(output_path, "a", encoding="utf-8") as f:
                for r in batch_results:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")

    return results


if __name__ == "__main__":
    # 简单 CLI 测试: 读取 jsonl 输入，输出评分结果
    if len(sys.argv) < 2:
        print("Usage: python normal_scorer.py <input_cases.jsonl>")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    output_path = input_path.with_suffix(".normal_scores.jsonl")

    cases = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))

    results = score_all_normal(cases, output_path)
    print(f"\nScored {len(results)} cases. Output: {output_path}")
