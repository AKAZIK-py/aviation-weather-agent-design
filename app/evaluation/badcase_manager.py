"""
Badcase 管理器 — 自动沉淀失败案例 + 回归验证

功能:
- add_badcase(): 从评测结果自动生成 badcase 记录
- load_badcases() / save_badcases(): JSONL 持久化
- get_regression_cases(): 获取所有未修复 badcase，用于回归测试
- mark_fixed(): 标记已修复 + 记录根因

存储格式: eval/badcases/badcases.jsonl (每行一个 JSON，符合 schema.json)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# 项目根目录下的 badcase 存储路径
_BADCASE_DIR = Path(__file__).resolve().parent.parent.parent / "eval" / "badcases"
_BADCASE_FILE = _BADCASE_DIR / "badcases.jsonl"

# 合法的 badcase 分类（来自 schema.json）
VALID_CATEGORIES = (
    "task_not_finished",
    "critical_info_missed",
    "output_too_template",
    "hallucination",
    "other",
)


class BadcaseManager:
    """Badcase 管理器：负责失败案例的增删改查和回归集生成。"""

    def __init__(self, badcase_path: Path | str | None = None):
        """
        Args:
            badcase_path: badcase JSONL 文件路径，默认 eval/badcases/badcases.jsonl
        """
        self._path = Path(badcase_path) if badcase_path else _BADCASE_FILE
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._cases: List[Dict[str, Any]] | None = None

    # ==================== 持久化 ====================

    def load_badcases(self) -> List[Dict[str, Any]]:
        """从 JSONL 文件加载所有 badcase。"""
        if self._cases is not None:
            return self._cases

        self._cases = []
        if not self._path.exists():
            logger.info("badcase 文件不存在，返回空列表: %s", self._path)
            return self._cases

        with open(self._path, "r", encoding="utf-8") as f:
            for lineno, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    self._cases.append(record)
                except json.JSONDecodeError as exc:
                    logger.warning("badcase JSONL 第 %d 行解析失败: %s", lineno, exc)

        logger.info("已加载 %d 条 badcase 记录", len(self._cases))
        return self._cases

    def save_badcases(self, cases: List[Dict[str, Any]] | None = None) -> None:
        """将 badcase 列表写回 JSONL 文件。"""
        if cases is not None:
            self._cases = cases

        if self._cases is None:
            self._cases = []

        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            for record in self._cases:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

        logger.info("已保存 %d 条 badcase 到 %s", len(self._cases), self._path)

    # ==================== 增删改 ====================

    def _generate_case_id(self) -> str:
        """生成 case_id: BC_YYYYMMDD_NNN (当日序号自增)。"""
        tz = timezone(timedelta(hours=8))
        today = datetime.now(tz).strftime("%Y%m%d")
        prefix = f"BC_{today}_"

        cases = self.load_badcases()
        max_seq = 0
        for c in cases:
            cid = c.get("case_id", "")
            if cid.startswith(prefix):
                try:
                    seq = int(cid[len(prefix) :])
                    max_seq = max(max_seq, seq)
                except ValueError:
                    pass

        return f"{prefix}{max_seq + 1:03d}"

    def add_badcase(
        self,
        category: str,
        input_data: Dict[str, Any],
        expected: Dict[str, Any],
        actual: Dict[str, Any],
        *,
        case_id: str | None = None,
        source: str = "auto_eval",
        notes: str | None = None,
        source_case_id: str | None = None,
        dataset_version: str | None = None,
        model: str | None = None,
    ) -> Dict[str, Any]:
        """
        添加一条 badcase 记录。

        Args:
            category: 失败分类 (task_not_finished / critical_info_missed /
                      output_too_template / hallucination / other)
            input_data: 输入数据 {metar, role, query}
            expected: 期望结果 {key_info, behavior, must_not_contain}
            actual: 实际结果 {output, latency_ms, token_count}
            case_id: 可选自定义 ID，不传则自动生成
            source: 来源标识
            notes: 备注
            source_case_id: 评测集中的原始 case ID（用于去重）
            dataset_version: 数据集版本（用于去重）
            model: 模型名称（用于去重）

        Returns:
            新增的 badcase 记录，若已存在相同去重键的未修复记录则返回 None
        """
        if category not in VALID_CATEGORIES:
            raise ValueError(
                f"无效的 category '{category}'，合法值: {VALID_CATEGORIES}"
            )

        # 去重键: source_case_id + dataset_version + model + category
        dedup_key_source = source_case_id or ""
        dedup_key_version = dataset_version or ""
        dedup_key_model = model or ""

        cases = self.load_badcases()

        for existing in cases:
            if existing.get("fixed", False):
                continue
            if (
                existing.get("source_case_id", "") == dedup_key_source
                and existing.get("dataset_version", "") == dedup_key_version
                and existing.get("model", "") == dedup_key_model
                and existing.get("category") == category
            ):
                logger.info(
                    "跳过重复 badcase: source_case_id=%s dataset_version=%s "
                    "model=%s category=%s 已存在于 %s",
                    dedup_key_source,
                    dedup_key_version,
                    dedup_key_model,
                    category,
                    existing.get("case_id"),
                )
                return existing

        tz = timezone(timedelta(hours=8))
        record = {
            "case_id": case_id or self._generate_case_id(),
            "category": category,
            "timestamp": datetime.now(tz).isoformat(),
            "source": source,
            "source_case_id": source_case_id,
            "dataset_version": dataset_version,
            "model": model,
            "input": input_data,
            "expected": expected,
            "actual": actual,
            "fixed": False,
            "fixed_at": None,
            "fixed_by": None,
            "root_cause": None,
            "regression_pass_count": 0,
            "notes": notes,
        }

        cases.append(record)
        self._cases = cases
        self.save_badcases()

        logger.info("新增 badcase: %s (category=%s)", record["case_id"], category)
        return record

    _REGRESSION_THRESHOLD = 3  # 需要连续通过次数才标 fixed

    def record_regression_pass(self, case_id: str) -> Dict[str, Any] | None:
        """
        记录一次回归通过。当连续通过次数达到阈值（3次）时自动标记为已修复。

        Args:
            case_id: badcase ID

        Returns:
            更新后的记录，未找到返回 None
        """
        cases = self.load_badcases()
        tz = timezone(timedelta(hours=8))

        for case in cases:
            if case["case_id"] == case_id:
                count = case.get("regression_pass_count", 0) + 1
                case["regression_pass_count"] = count
                if count >= self._REGRESSION_THRESHOLD:
                    case["fixed"] = True
                    case["fixed_at"] = datetime.now(tz).isoformat()
                    logger.info(
                        "badcase %s 连续通过 %d 次，自动标记为已修复",
                        case_id,
                        count,
                    )
                else:
                    logger.info(
                        "badcase %s 回归通过 (%d/%d)",
                        case_id,
                        count,
                        self._REGRESSION_THRESHOLD,
                    )
                self._cases = cases
                self.save_badcases()
                return case

        logger.warning("未找到 badcase: %s", case_id)
        return None

    def reset_regression_count(self, case_id: str) -> Dict[str, Any] | None:
        """
        重置回归通过计数（回归失败时调用）。

        Args:
            case_id: badcase ID

        Returns:
            更新后的记录，未找到返回 None
        """
        cases = self.load_badcases()

        for case in cases:
            if case["case_id"] == case_id:
                case["regression_pass_count"] = 0
                self._cases = cases
                self.save_badcases()
                logger.info("已重置 badcase %s 回归计数", case_id)
                return case

        logger.warning("未找到 badcase: %s", case_id)
        return None

    def mark_fixed(
        self,
        case_id: str,
        root_cause: str,
        fixed_by: str | None = None,
    ) -> Dict[str, Any] | None:
        """
        手动标记一条 badcase 为已修复（跳过回归计数检查）。

        正常流程应使用 record_regression_pass()，连续3次通过后自动标记。

        Args:
            case_id: 要标记的 badcase ID
            root_cause: 根因分析
            fixed_by: 修复者 / 修复 commit

        Returns:
            更新后的记录，未找到则返回 None
        """
        cases = self.load_badcases()
        tz = timezone(timedelta(hours=8))

        for case in cases:
            if case["case_id"] == case_id:
                case["fixed"] = True
                case["fixed_at"] = datetime.now(tz).isoformat()
                case["fixed_by"] = fixed_by
                case["root_cause"] = root_cause
                case["regression_pass_count"] = self._REGRESSION_THRESHOLD
                self._cases = cases
                self.save_badcases()
                logger.info("已手动标记 badcase %s 为已修复", case_id)
                return case

        logger.warning("未找到 badcase: %s", case_id)
        return None

    def delete_badcase(self, case_id: str) -> bool:
        """删除指定 badcase。返回是否删除成功。"""
        cases = self.load_badcases()
        original_len = len(cases)
        cases = [c for c in cases if c.get("case_id") != case_id]

        if len(cases) < original_len:
            self._cases = cases
            self.save_badcases()
            logger.info("已删除 badcase: %s", case_id)
            return True

        logger.warning("删除失败，未找到 badcase: %s", case_id)
        return False

    # ==================== 查询 ====================

    def get_regression_cases(self) -> List[Dict[str, Any]]:
        """
        返回所有未修复的 badcase，用于回归测试。

        Returns:
            fixed == False 的所有记录
        """
        cases = self.load_badcases()
        unfixed = [c for c in cases if not c.get("fixed", False)]
        logger.info("回归集: %d 条未修复 badcase / 共 %d 条", len(unfixed), len(cases))
        return unfixed

    def get_case_by_id(self, case_id: str) -> Dict[str, Any] | None:
        """按 ID 查询单条 badcase。"""
        for case in self.load_badcases():
            if case.get("case_id") == case_id:
                return case
        return None

    def get_cases_by_category(self, category: str) -> List[Dict[str, Any]]:
        """按分类筛选 badcase。"""
        return [c for c in self.load_badcases() if c.get("category") == category]

    def get_stats(self) -> Dict[str, Any]:
        """返回 badcase 统计摘要。"""
        cases = self.load_badcases()
        total = len(cases)
        fixed = sum(1 for c in cases if c.get("fixed", False))
        unfixed = total - fixed

        by_category: Dict[str, int] = {}
        for c in cases:
            cat = c.get("category", "other")
            by_category[cat] = by_category.get(cat, 0) + 1

        by_category_fixed: Dict[str, int] = {}
        for c in cases:
            if c.get("fixed", False):
                cat = c.get("category", "other")
                by_category_fixed[cat] = by_category_fixed.get(cat, 0) + 1

        return {
            "total": total,
            "fixed": fixed,
            "unfixed": unfixed,
            "regression_pass_rate": (
                round(fixed / total * 100, 1) if total > 0 else 100.0
            ),
            "by_category": by_category,
            "fixed_by_category": by_category_fixed,
        }
