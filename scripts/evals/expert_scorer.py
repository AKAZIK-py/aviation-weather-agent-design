#!/usr/bin/env python3
"""
专家评分子代理 — 调用 Claude Code CLI 对 Agent 输出进行专家级评分。

负责 3 个专家指标:
  flight_rules_accurate, risk_accurate, safety_covered

基于 ICAO Annex 3 飞行规则标准，与 normal_scorer 完全隔离（独立 prompt）。

输出: results/expert_scores.jsonl
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------------

_EXPERT_PROMPT_TEMPLATE = """你是一位资深航空安全专家和持照飞行员，精通 ICAO Annex 3 飞行规则标准。

## 你的任务
对以下航空气象 Agent 的输出进行专家级评分。你只关注三个维度:

### 1. flight_rules_accurate (飞行规则准确率, 0/1)
Agent 对飞行规则的判定是否与 METAR 数据一致。

ICAO Annex 3 标准:
| 规则 | 能见度 (VIS) | 云底高 (Ceiling) |
|------|-------------|-----------------|
| VFR  | > 5 km      | > 3000 ft (900m)  |
| MVFR | 3-5 km      | 1000-3000 ft (300-900m) |
| IFR  | 1-3 km      | 500-1000 ft (150-300m)  |
| LIFR | < 1 km      | < 500 ft (150m)  |

云底高以最低的 BKN/OVC 层为准，FEW/SCT 不计为 ceiling。

### 2. risk_accurate (风险评估准确率, 0/1)
Agent 的风险等级判定是否与 METAR 条件匹配。

标准:
- CRITICAL: 雷暴(TS/CB)、能见度<1km、风切变(LLWS)、严重颠簸、火山灰
- HIGH: 能见度<3km、云底高<500ft、阵风>40kt、冻雨(FZFG)
- MEDIUM: MVFR条件、能见度3-5km、风速20-30kt
- LOW: VFR条件、能见度>5km、风速<20kt、无危险天气

### 3. safety_covered (安全边界覆盖率, 0/1)
对于 CRITICAL 条件的 case，Agent 是否正确标记了不适飞/NO-GO/备降等安全警告。
对于非 CRITICAL case，此项默认为 1。
"""

_EXPERT_BATCH_TEMPLATE = """你是ICAO Annex 3航空气象专家评测员。请对以下每条 Case 进行专家级评分。

## 待评测 Cases
{cases_text}

## 评分标准
- flight_rules_accurate: Agent输出的飞行规则是否与ICAO Annex 3标准一致(0/1)
- risk_accurate: 风险评估是否准确覆盖了主要风险维度(0/1)
- safety_covered: 安全警告是否充分，CRITICAL情况必须有明确警告(0/1)

## 输出格式
输出一个 JSON 数组，每个元素对应一条 case:
```json
[
  {{
    "case_id": "STD_001",
    "flight_rules_accurate": 0或1,
    "risk_accurate": 0或1,
    "safety_covered": 0或1,
    "reasoning": {{
      "flight_rules_accurate": "理由",
      "risk_accurate": "理由",
      "safety_covered": "理由"
    }}
  }}
]
```
只输出 JSON 数组，不要输出任何其他内容。"""


def _build_expert_batch_prompt(cases: List[Dict[str, Any]]) -> str:
    """构建专家批量评分 prompt。"""
    cases_text = ""
    for case in cases:
        case_id = case.get("case_id", "unknown")
        query = case.get("query", "")
        role = case.get("role", "pilot")
        metar = case.get("metar_text", case.get("metar", ""))
        agent_output = case.get("agent_output", case.get("output", ""))
        expected_fr = case.get("expected_flight_rules", "unknown")
        expected_rl = case.get("expected_risk_level", "unknown")
        cases_text += f"""
### Case: {case_id}
- 用户问题: {query}
- 角色: {role}
- METAR: {metar}
- 期望飞行规则: {expected_fr}
- 期望风险等级: {expected_rl}
- Agent 输出: {agent_output[:800]}

"""
    return _EXPERT_BATCH_TEMPLATE.format(cases_text=cases_text)


def _build_expert_prompt(case_data: Dict[str, Any]) -> str:
    """构建单条专家评分 prompt（保留兼容）。"""
    return _build_expert_batch_prompt([case_data])


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
    """解析专家评分批量响应。"""
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
                required = ["flight_rules_accurate", "risk_accurate", "safety_covered"]
                for field in required:
                    if field not in item:
                        item[field] = 0
                if "reasoning" not in item:
                    item["reasoning"] = {}
                results.append(item)
            return results
    except json.JSONDecodeError:
        pass

    return [{
        "case_id": cid,
        "flight_rules_accurate": 0, "risk_accurate": 0, "safety_covered": 0,
        "reasoning": {"error": f"JSON parse failed: {raw[:200]}"},
        "parse_error": True,
    } for cid in case_ids]


def _parse_llm_response(raw: str, case_id: str) -> Dict[str, Any]:
    """从 Claude CLI 输出中解析单条 JSON（保留兼容）。"""
    results = _parse_batch_response(raw, [case_id])
    return results[0] if results else {"case_id": case_id, "error": "empty"}


def score_case_expert(case_data: Dict[str, Any]) -> Dict[str, Any]:
    """单条评分（保留兼容）。"""
    return score_batch_expert([case_data])[0]


def score_batch_expert(cases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """批量专家评分：一次 Claude Code 调用处理多条 case。"""
    case_ids = [c.get("case_id", f"case_{i}") for i, c in enumerate(cases)]
    prompt = _build_expert_batch_prompt(cases)
    raw_response = _call_claude_cli(prompt)
    results = _parse_batch_response(raw_response, case_ids)

    while len(results) < len(cases):
        results.append({
            "case_id": case_ids[len(results)],
            "flight_rules_accurate": 0, "risk_accurate": 0, "safety_covered": 0,
            "reasoning": {"error": "missing from batch response"},
        })
    return results[:len(cases)]


def score_all_expert(
    cases: List[Dict[str, Any]],
    output_path: Optional[Path] = None,
    batch_size: int = 10,
) -> List[Dict[str, Any]]:
    """批量专家评分，每 batch_size 条 case 调用一次 Claude Code。"""
    results = []
    total = len(cases)

    for batch_start in range(0, total, batch_size):
        batch_end = min(batch_start + batch_size, total)
        batch = cases[batch_start:batch_end]
        batch_num = batch_start // batch_size + 1
        total_batches = (total + batch_size - 1) // batch_size

        print(f"[expert_scorer] Batch {batch_num}/{total_batches} ({len(batch)} cases) ...", flush=True)

        try:
            batch_results = score_batch_expert(batch)
        except Exception as exc:
            batch_results = [{
                "case_id": c.get("case_id", f"case_{i}"),
                "flight_rules_accurate": 0, "risk_accurate": 0, "safety_covered": 0,
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
    if len(sys.argv) < 2:
        print("Usage: python expert_scorer.py <input_cases.jsonl>")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    output_path = input_path.with_suffix(".expert_scores.jsonl")

    cases = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))

    results = score_all_expert(cases, output_path)
    print(f"\nScored {len(results)} cases. Output: {output_path}")
