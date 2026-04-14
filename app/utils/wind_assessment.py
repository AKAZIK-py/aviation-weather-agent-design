"""
大风动态评估器

评估维度:
- 瞬时风速 (m/s)
- 阵风差值 (kt)
- 侧风分量 (kt)

关键规则:
- W-01: 瞬时风速 ≥20m/s → CRITICAL (override=True)
- W-02: WS 风切变 → CRITICAL (override=True)
- W-03: 阵风差值 ≥15kt + 平均>25kt → HIGH
- W-04: 侧风 > 机型限制 → HIGH
"""
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# kt to m/s conversion factor
KT_TO_MS = 0.514444


@dataclass
class WindAssessment:
    """大风评估结果"""
    overall_risk: str                    # LOW / MEDIUM / HIGH / CRITICAL
    instantaneous_ms: float              # 瞬时风速 (m/s)
    gust_difference_kt: float            # 阵风差值 (kt)
    crosswind_kt: float                  # 侧风分量 (kt)
    headwind_kt: float                   # 顶风分量 (kt)
    risk_factors: List[str] = field(default_factory=list)
    unsafe_for_flight: bool = False
    override_reasons: List[str] = field(default_factory=list)

    @property
    def score(self) -> float:
        """映射到 0-100 风险分数"""
        score_map = {"LOW": 10, "MEDIUM": 40, "HIGH": 70, "CRITICAL": 95}
        return score_map.get(self.overall_risk, 10)


# 阈值定义
INSTANTANEOUS_WIND_THRESHOLDS = {
    "safe": 8,       # m/s
    "caution": 13,   # m/s
    "high": 17,      # m/s
    "critical": 20,  # m/s
}

GUST_DIFFERENCE_THRESHOLDS = {
    "safe": 8,        # kt
    "caution": 12,    # kt
    "high": 15,       # kt
    "critical": 20,   # kt
}

CROSSWIND_THRESHOLDS = {
    "light": 10,      # kt
    "medium": 15,     # kt
    "heavy": 20,      # kt
    "max": 25,        # kt
}

# 机型侧风限制 (kt)
AIRCRAFT_CROSSWIND_LIMITS = {
    "heavy": 30,       # 重型机 (B747, A330等)
    "medium": 25,      # 中型机 (B737, A320等)
    "light": 15,       # 轻型机 (Cessna等)
    "default": 25,     # 默认
}

# 风切变现象代码
WIND_SHEAR_CODES = {"WS"}


def assess_wind(
    wind_speed_kt: Optional[int] = None,
    wind_dir_deg: Optional[int] = None,
    gust_speed_kt: Optional[int] = None,
    runway_heading_deg: Optional[int] = None,
    aircraft_type: str = "default",
    phenomena: Optional[List[str]] = None,
) -> WindAssessment:
    """
    综合大风评估。

    Args:
        wind_speed_kt: 平均风速 (kt)
        wind_dir_deg: 风向 (度)
        gust_speed_kt: 阵风风速 (kt)
        runway_heading_deg: 跑道磁航向 (度)
        aircraft_type: 机型类别 (heavy/medium/light/default)
        phenomena: 天气现象列表 (检测风切变等)

    Returns:
        WindAssessment 评估结果
    """
    risk_factors: List[str] = []
    override_reasons: List[str] = []
    overall_risk = "LOW"
    unsafe = False

    # 默认值
    speed_kt = wind_speed_kt or 0
    gust_kt = gust_speed_kt or 0
    instantaneous_ms = speed_kt * KT_TO_MS
    gust_diff = max(0, gust_kt - speed_kt)

    # 计算侧风/顶风分量
    crosswind_kt = 0.0
    headwind_kt = 0.0
    if wind_dir_deg is not None and runway_heading_deg is not None:
        crosswind_kt, headwind_kt = _calc_crosswind_headwind(
            wind_dir_deg, speed_kt, runway_heading_deg
        )

    # ===== 规则评估 =====

    # W-01: 瞬时风速 ≥20m/s → CRITICAL
    if instantaneous_ms >= INSTANTANEOUS_WIND_THRESHOLDS["critical"]:
        overall_risk = "CRITICAL"
        unsafe = True
        reason = f"W-01: 瞬时风速 {instantaneous_ms:.1f}m/s ≥ 20m/s"
        risk_factors.append(reason)
        override_reasons.append(reason)

    elif instantaneous_ms >= INSTANTANEOUS_WIND_THRESHOLDS["high"]:
        if _risk_priority(overall_risk) < _risk_priority("HIGH"):
            overall_risk = "HIGH"
        risk_factors.append(f"强风: {instantaneous_ms:.1f}m/s (≥17m/s)")

    elif instantaneous_ms >= INSTANTANEOUS_WIND_THRESHOLDS["caution"]:
        if _risk_priority(overall_risk) < _risk_priority("MEDIUM"):
            overall_risk = "MEDIUM"
        risk_factors.append(f"风速较大: {instantaneous_ms:.1f}m/s (≥13m/s)")

    # W-02: WS 风切变 → CRITICAL
    if phenomena:
        for p in phenomena:
            if p in WIND_SHEAR_CODES or "WS" in p:
                overall_risk = "CRITICAL"
                unsafe = True
                reason = f"W-02: 检测到风切变 ({p})"
                risk_factors.append(reason)
                override_reasons.append(reason)
                break

    # W-03: 阵风差值 ≥15kt + 平均>25kt → HIGH
    if gust_diff >= GUST_DIFFERENCE_THRESHOLDS["high"] and speed_kt > 25:
        if _risk_priority(overall_risk) < _risk_priority("HIGH"):
            overall_risk = "HIGH"
        reason = f"W-03: 阵风差 {gust_diff}kt + 平均 {speed_kt}kt"
        risk_factors.append(reason)

    elif gust_diff >= GUST_DIFFERENCE_THRESHOLDS["caution"]:
        if _risk_priority(overall_risk) < _risk_priority("MEDIUM"):
            overall_risk = "MEDIUM"
        risk_factors.append(f"阵风差值较大: {gust_diff}kt")

    # W-04: 侧风 > 机型限制 → HIGH
    ac_limit = AIRCRAFT_CROSSWIND_LIMITS.get(
        aircraft_type, AIRCRAFT_CROSSWIND_LIMITS["default"]
    )
    if crosswind_kt > ac_limit:
        if _risk_priority(overall_risk) < _risk_priority("HIGH"):
            overall_risk = "HIGH"
        reason = f"W-04: 侧风 {crosswind_kt:.1f}kt > {aircraft_type}限制 {ac_limit}kt"
        risk_factors.append(reason)

    elif crosswind_kt > CROSSWIND_THRESHOLDS["heavy"]:
        if _risk_priority(overall_risk) < _risk_priority("HIGH"):
            overall_risk = "HIGH"
        risk_factors.append(f"强侧风: {crosswind_kt:.1f}kt")

    elif crosswind_kt > CROSSWIND_THRESHOLDS["medium"]:
        if _risk_priority(overall_risk) < _risk_priority("MEDIUM"):
            overall_risk = "MEDIUM"
        risk_factors.append(f"中等侧风: {crosswind_kt:.1f}kt")

    elif crosswind_kt > CROSSWIND_THRESHOLDS["light"]:
        if _risk_priority(overall_risk) < _risk_priority("MEDIUM"):
            overall_risk = "MEDIUM"
        risk_factors.append(f"轻度侧风: {crosswind_kt:.1f}kt")

    return WindAssessment(
        overall_risk=overall_risk,
        instantaneous_ms=round(instantaneous_ms, 2),
        gust_difference_kt=gust_diff,
        crosswind_kt=round(crosswind_kt, 1),
        headwind_kt=round(headwind_kt, 1),
        risk_factors=risk_factors,
        unsafe_for_flight=unsafe,
        override_reasons=override_reasons,
    )


def normalize_wind_score(speed_kt: Optional[int], gust_kt: Optional[int] = None) -> float:
    """
    将风速归一化为 0-100 分数（绝对不超过100）。

    使用阵风值（如有）或平均风速。
    分段线性: 0-10kt→0, 10-20kt→0-20, 20-30kt→20-40, 30-50kt→40-85, 50+→85-100
    阵风差值惩罚: +5/+10/+15，最终 cap 100
    """
    speed = max(speed_kt or 0, gust_kt or 0)

    if speed <= 10:
        base = 0.0
    elif speed <= 20:
        base = 20.0 * (speed - 10) / 10
    elif speed <= 30:
        base = 20.0 + 20.0 * (speed - 20) / 10
    elif speed <= 50:
        base = 40.0 + 45.0 * (speed - 30) / 20
    else:
        base = min(85.0 + 15.0 * (speed - 50) / 30, 100.0)

    # 阵风差值惩罚
    penalty = 0.0
    if gust_kt is not None and speed_kt is not None:
        diff = gust_kt - speed_kt
        if diff >= 15:
            penalty = 15.0
        elif diff >= 10:
            penalty = 10.0
        elif diff >= 5:
            penalty = 5.0

    return min(base + penalty, 100.0)


def _calc_crosswind_headwind(
    wind_dir: int, wind_speed: int, runway_heading: int
) -> Tuple[float, float]:
    """
    计算侧风和顶风分量。

    Args:
        wind_dir: 风向 (度, 0-360)
        wind_speed: 风速 (kt)
        runway_heading: 跑道磁航向 (度)

    Returns:
        (crosswind_kt, headwind_kt)
    """
    # 风向与跑道的夹角
    angle = math.radians(wind_dir - runway_heading)

    # 侧风分量 (绝对值)
    crosswind = abs(wind_speed * math.sin(angle))

    # 顶风分量 (正值=顶风, 负值=顺风)
    headwind = wind_speed * math.cos(angle)

    return crosswind, headwind


def _risk_priority(risk: str) -> int:
    """风险等级优先级 (越高越危险)"""
    priority = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
    return priority.get(risk, 0)
