#!/usr/bin/env python3
"""
IAA (Inter-Annotator Agreement) 抽检模块。

随机抽取 20% case，对比 normal_scorer 和 expert_scorer 的二分类结果，
计算 Cohen's Kappa，支持熔断机制。
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _extract_overlap_binary(
    normal: Dict[str, Any],
    expert: Dict[str, Any],
) -> List[Tuple[int, int]]:
    """
    从 normal 和 expert 评分中提取重叠的二分类指标对。

    重叠指标:
      - normal["task_complete"] ↔ expert 无直接对应（跳过）
      - normal["hallucination"] ↔ expert 无直接对应（跳过）
      - normal["template"] ↔ expert 无直接对应（跳过）

    实际重叠: 通过映射间接比较
      - normal["key_info_hit"] ↔ expert["flight_rules_accurate"] (信息准确性)
      - normal["usable"] ↔ expert["risk_accurate"] + expert["safety_covered"] (整体可用性)

    简化方案: 直接比较 normal 和 expert 中名称相同或语义等价的指标。
    如果没有直接等价指标，则构造综合二分类:
      - normal_pass = task_complete AND key_info_hit AND NOT hallucination
      - expert_pass = flight_rules_accurate AND risk_accurate AND safety_covered
    """
    # 方案 A: 直接综合二分类
    normal_pass = int(
        normal.get("task_complete", 0) == 1
        and normal.get("key_info_hit", 0) == 1
        and normal.get("hallucination", 0) == 0
    )
    expert_pass = int(
        expert.get("flight_rules_accurate", 0) == 1
        and expert.get("risk_accurate", 0) == 1
        and expert.get("safety_covered", 0) == 1
    )
    pairs = [(normal_pass, expert_pass)]

    # 方案 B: 如果 normal 有 expert 同名字段，也提取
    for field in ["flight_rules_accurate", "risk_accurate", "safety_covered"]:
        if field in normal and field in expert:
            pairs.append((int(normal[field]), int(expert[field])))

    return pairs


def _cohens_kappa(rater1: List[int], rater2: List[int]) -> float:
    """
    计算 Cohen's Kappa 系数。

    Args:
        rater1: 评分者1的二分类结果列表
        rater2: 评分者2的二分类结果列表

    Returns:
        Kappa 值 (float)
    """
    n = len(rater1)
    if n == 0:
        return 1.0

    # 观察一致率
    po = sum(1 for a, b in zip(rater1, rater2) if a == b) / n

    # 每个类别的边际概率
    p1_yes = sum(rater1) / n
    p1_no = 1 - p1_yes
    p2_yes = sum(rater2) / n
    p2_no = 1 - p2_yes

    # 期望一致率
    pe = p1_yes * p2_yes + p1_no * p2_no

    if pe == 1.0:
        return 1.0

    kappa = (po - pe) / (1 - pe)
    return round(kappa, 4)


def compute_iaa(
    normal_scores: List[Dict[str, Any]],
    expert_scores: List[Dict[str, Any]],
    sample_ratio: float = 0.2,
    seed: int = 42,
) -> Dict[str, Any]:
    """
    计算 IAA (Inter-Annotator Agreement)。

    Args:
        normal_scores: normal_scorer 的评分结果列表，每条需含 case_id
        expert_scores: expert_scorer 的评分结果列表，每条需含 case_id
        sample_ratio: 抽样比例，默认 0.2 (20%)
        seed: 随机种子

    Returns:
        {
            "status": "OK" | "WARNING" | "CIRCUIT_BREAKER",
            "message": str,
            "kappa": float,
            "sample_size": int,
            "total_cases": int,
            "agreement_rate": float,
            "divergent_cases": [...]
        }
    """
    # 按 case_id 建立索引
    normal_by_id = {s["case_id"]: s for s in normal_scores if "case_id" in s}
    expert_by_id = {s["case_id"]: s for s in expert_scores if "case_id" in s}

    # 找到共同 case
    common_ids = sorted(set(normal_by_id.keys()) & set(expert_by_id.keys()))
    total = len(common_ids)

    if total == 0:
        return {
            "status": "WARNING",
            "message": "⚠️ 无共同 case 可比较",
            "kappa": 0.0,
            "sample_size": 0,
            "total_cases": 0,
            "agreement_rate": 0.0,
            "divergent_cases": [],
        }

    # 随机抽样
    rng = random.Random(seed)
    sample_size = max(1, int(total * sample_ratio))
    sample_ids = rng.sample(common_ids, min(sample_size, total))

    # 提取二分类对
    all_rater1: List[int] = []
    all_rater2: List[int] = []
    divergent_cases = []

    for cid in sample_ids:
        normal = normal_by_id[cid]
        expert = expert_by_id[cid]
        pairs = _extract_overlap_binary(normal, expert)

        for r1, r2 in pairs:
            all_rater1.append(r1)
            all_rater2.append(r2)
            if r1 != r2:
                divergent_cases.append({
                    "case_id": cid,
                    "normal_score": r1,
                    "expert_score": r2,
                    "normal_detail": {
                        k: normal.get(k) for k in
                        ["task_complete", "key_info_hit", "usable", "template", "hallucination"]
                        if k in normal
                    },
                    "expert_detail": {
                        k: expert.get(k) for k in
                        ["flight_rules_accurate", "risk_accurate", "safety_covered"]
                        if k in expert
                    },
                })

    kappa = _cohens_kappa(all_rater1, all_rater2)
    agreement_rate = sum(1 for a, b in zip(all_rater1, all_rater2) if a == b) / len(all_rater1) if all_rater1 else 1.0

    # 判断状态
    if kappa == 1.0:
        status = "CIRCUIT_BREAKER"
        message = "🔴 IAA=1.0 主动熔断 — 评分一致性异常完美，请人工复核评分 prompt 是否过拟合"
    elif kappa < 0.6:
        status = "WARNING"
        message = f"⚠️ 低一致性 Kappa={kappa} — normal 和 expert 评分分歧较大，请检查评分标准"
    else:
        status = "OK"
        message = f"✅ 一致性正常 Kappa={kappa}"

    return {
        "status": status,
        "message": message,
        "kappa": kappa,
        "sample_size": sample_size,
        "total_cases": total,
        "agreement_rate": round(agreement_rate, 4),
        "divergent_cases": divergent_cases,
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python iaa_checker.py <normal_scores.jsonl> <expert_scores.jsonl>")
        sys.exit(1)

    def load_jsonl(path: Path) -> List[Dict[str, Any]]:
        results = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    results.append(json.loads(line))
        return results

    normal_scores = load_jsonl(Path(sys.argv[1]))
    expert_scores = load_jsonl(Path(sys.argv[2]))

    result = compute_iaa(normal_scores, expert_scores)
    print(json.dumps(result, ensure_ascii=False, indent=2))
