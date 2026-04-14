"""
综合动态风险评分引擎

流程:
1. normalize_visibility_score(vis_km) → vis_score (0-100)
2. normalize_ceiling_score(ceiling_ft) → ceiling_score (0-100)
3. normalize_wind_score(speed_kt, gust_kt) → wind_score (0-100)
4. normalize_temp_score(temp_c) → temp_score (0-100)
5. get_weight_for_phenomena(phenomena) → weights
6. base_score = Σ(dimension_score × weight)
7. apply_critical_overrides() → 检查 W-01/W-02/FZRA 强制覆盖
8. map_to_flight_rules(score, vis_score, ceiling_score, vis_km, ceiling_ft) → flight_rules
9. 返回 DynamicRiskReport
"""
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from app.utils.ceiling_zones import classify as classify_ceiling, normalize_ceiling_score
from app.utils.visibility_zones import classify_visibility, normalize_visibility_score
from app.utils.dynamic_weights import get_weight_for_phenomena
from app.utils.wind_assessment import (
    assess_wind,
    normalize_wind_score,
    INSTANTANEOUS_WIND_THRESHOLDS,
)


@dataclass
class DynamicRiskReport:
    """综合动态风险评估报告"""
    # 总体结论
    overall_risk: str                    # LOW / MEDIUM / HIGH / CRITICAL
    flight_rules: str                    # VFR / MVFR / IFR / LIFR
    base_score: float                    # 加权综合分数 (0-100)

    # 各维度分数
    vis_score: float                     # 能见度分数 (0-100)
    ceiling_score: float                 # 云底高分数 (0-100)
    wind_score: float                    # 风况分数 (0-100)
    temp_score: float                    # 温度分数 (0-100)

    # 权重
    weights: Dict[str, float] = field(default_factory=dict)

    # 区间诊断
    vis_zone: Optional[Any] = None       # VisibilityZone
    ceiling_zone: Optional[Any] = None   # CeilingZone

    # 风况详情
    wind_assessment: Optional[Any] = None  # WindAssessment

    # 覆盖原因
    override_reasons: List[str] = field(default_factory=list)

    # 风险因素摘要
    risk_factors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """转为字典（用于序列化）"""
        d = {
            "overall_risk": self.overall_risk,
            "flight_rules": self.flight_rules,
            "base_score": round(self.base_score, 1),
            "vis_score": round(self.vis_score, 1),
            "ceiling_score": round(self.ceiling_score, 1),
            "wind_score": round(self.wind_score, 1),
            "temp_score": round(self.temp_score, 1),
            "weights": self.weights,
            "override_reasons": self.override_reasons,
            "risk_factors": self.risk_factors,
        }
        if self.vis_zone:
            d["vis_zone"] = {
                "zone": self.vis_zone.zone,
                "label": self.vis_zone.label,
                "color": self.vis_zone.color,
            }
        if self.ceiling_zone:
            d["ceiling_zone"] = {
                "zone": self.ceiling_zone.zone,
                "label": self.ceiling_zone.label,
                "color": self.ceiling_zone.color,
            }
        if self.wind_assessment:
            d["wind_detail"] = {
                "overall_risk": self.wind_assessment.overall_risk,
                "instantaneous_ms": self.wind_assessment.instantaneous_ms,
                "gust_difference_kt": self.wind_assessment.gust_difference_kt,
                "crosswind_kt": self.wind_assessment.crosswind_kt,
                "unsafe_for_flight": self.wind_assessment.unsafe_for_flight,
            }
        return d


class DynamicRiskEngine:
    """综合动态风险评分引擎"""

    def calculate(
        self,
        metar_data: Dict[str, Any],
        phenomena: Optional[List[str]] = None,
        wind_speed_kt: Optional[int] = None,
        wind_dir_deg: Optional[int] = None,
        gust_speed_kt: Optional[int] = None,
        runway_heading_deg: Optional[int] = None,
        aircraft_type: str = "default",
    ) -> DynamicRiskReport:
        """
        执行综合动态风险评估。

        Args:
            metar_data: 解析后的 METAR 数据字典
            phenomena: 天气现象代码列表
            wind_speed_kt: 平均风速 (kt)
            wind_dir_deg: 风向 (度)
            gust_speed_kt: 阵风 (kt)
            runway_heading_deg: 跑道航向 (度)
            aircraft_type: 机型类别

        Returns:
            DynamicRiskReport 综合评估报告
        """
        risk_factors: List[str] = []
        override_reasons: List[str] = []

        # 提取 METAR 数据
        visibility = metar_data.get("visibility")
        temperature = metar_data.get("temperature")
        cloud_layers = metar_data.get("cloud_layers", [])

        # 获取云底高
        ceiling_types = {"BKN", "OVC", "VV"}
        ceiling_heights = [
            layer["height_feet"] for layer in cloud_layers
            if layer.get("type") in ceiling_types and layer.get("height_feet")
        ]
        lowest_ceiling = min(ceiling_heights) if ceiling_heights else None

        # 天气现象
        if phenomena is None:
            wx_list = metar_data.get("present_weather", [])
            if wx_list and isinstance(wx_list[0], dict):
                phenomena = [w.get("code", "") for w in wx_list]
            else:
                phenomena = wx_list if wx_list else []

        # 风速
        if wind_speed_kt is None:
            wind_speed_kt = metar_data.get("wind_speed")
        if wind_dir_deg is None:
            wind_dir_deg = metar_data.get("wind_direction")
        if gust_speed_kt is None:
            gust_speed_kt = metar_data.get("wind_gust")

        # ===== Step 1-4: 各维度分数 =====
        vis_score = normalize_visibility_score(visibility)
        ceiling_score = normalize_ceiling_score(lowest_ceiling)
        wind_score = normalize_wind_score(wind_speed_kt, gust_speed_kt)
        temp_score = normalize_temp_score(temperature)

        # ===== 区间诊断 =====
        vis_zone = classify_visibility(visibility)
        ceiling_zone = classify_ceiling(lowest_ceiling)

        if vis_zone.zone >= 4:
            risk_factors.append(f"能见度区间: Zone {vis_zone.zone} ({vis_zone.label})")
        if ceiling_zone.zone >= 4:
            risk_factors.append(f"云底高区间: Zone {ceiling_zone.zone} ({ceiling_zone.label})")
        # 缓冲区告警
        if vis_zone.in_buffer:
            risk_factors.append(f"能见度缓冲区告警: {vis_zone.description}")
        if ceiling_zone.in_buffer:
            risk_factors.append(f"云底高缓冲区告警: {ceiling_zone.description}")

        # ===== Step 5: 动态权重 =====
        weights = get_weight_for_phenomena(phenomena)

        # ===== Step 6: 加权综合分数 =====
        base_score = (
            vis_score * weights["W_vis"]
            + ceiling_score * weights["W_ceil"]
            + wind_score * weights["W_wind"]
            + temp_score * weights["W_temp"]
        )

        # ===== 风况详细评估 =====
        wind_assessment = assess_wind(
            wind_speed_kt=wind_speed_kt,
            wind_dir_deg=wind_dir_deg,
            gust_speed_kt=gust_speed_kt,
            runway_heading_deg=runway_heading_deg,
            aircraft_type=aircraft_type,
            phenomena=phenomena,
        )
        risk_factors.extend(wind_assessment.risk_factors)

        # ===== Step 7: 关键覆盖规则 =====
        overall_risk = _score_to_risk(base_score)

        # W-01/W-02 覆盖
        if wind_assessment.override_reasons:
            overall_risk = "CRITICAL"
            override_reasons.extend(wind_assessment.override_reasons)

        # FZRA/FZDZ 三重交叉验证 (温度+能见度+露点差)
        if any(ph.upper() in ("FZRA", "FZDZ") for ph in phenomena):
            dew = metar_data.get("dewpoint")
            temp = metar_data.get("temperature")
            vis = metar_data.get("visibility")
            dpd = (temp - dew) if (temp is not None and dew is not None) else 99.0

            cond1 = temp is not None and temp <= 0
            cond2 = vis is not None and vis < 5
            cond3 = dpd < 3

            if cond1 and cond2 and cond3:
                override_score = max(base_score, 95.0)
                overall_risk = _score_to_risk(override_score)
                if _risk_priority(overall_risk) < _risk_priority("CRITICAL"):
                    overall_risk = "CRITICAL"
                reason = f"FZRA-01: 三重验证通过(T={temp}<=0, VIS={vis}<5km, DPD={dpd:.1f}<3) -> 95分"
                override_reasons.append(reason)
                risk_factors.append(reason)
            else:
                reason = f"FZRA-WARN: 条件不典型(T={temp}, VIS={vis}, DPD={dpd:.1f})，不触发强制覆盖"
                override_reasons.append(reason)
                risk_factors.append(reason)

        # FZFG + 低云 强制覆盖
        if any("FZFG" in p.upper() for p in phenomena):
            if lowest_ceiling is not None and lowest_ceiling < 500:
                if _risk_priority(overall_risk) < _risk_priority("CRITICAL"):
                    overall_risk = "CRITICAL"
                    reason = f"FZFG + 低云 {lowest_ceiling}ft → CRITICAL"
                    override_reasons.append(reason)
                    risk_factors.append(reason)

        # TS/TSGR/FC 强制覆盖 (雷暴、冰雹、龙卷风)
        critical_wx = {"TS", "TSGR", "FC", "TORNADO"}
        for p in phenomena:
            p_upper = p.upper()
            if p_upper in critical_wx or any(p_upper.startswith(c) for c in critical_wx):
                if _risk_priority(overall_risk) < _risk_priority("CRITICAL"):
                    overall_risk = "CRITICAL"
                    reason = f"{p}: 危险天气现象强制 CRITICAL 覆盖"
                    override_reasons.append(reason)
                    risk_factors.append(reason)
                break

        # +TSRA 强制覆盖 (强雷暴伴雨)
        for p in phenomena:
            if "+TS" in p.upper():
                if _risk_priority(overall_risk) < _risk_priority("CRITICAL"):
                    overall_risk = "CRITICAL"
                    reason = f"{p}: 强雷暴强制 CRITICAL 覆盖"
                    override_reasons.append(reason)
                    risk_factors.append(reason)
                break

        # ===== Step 8: 飞行规则映射 =====
        flight_rules = _map_to_flight_rules(
            base_score, vis_score, ceiling_score, visibility, lowest_ceiling
        )

        # 去重 risk_factors
        seen = set()
        unique_factors = []
        for f in risk_factors:
            if f not in seen:
                seen.add(f)
                unique_factors.append(f)

        return DynamicRiskReport(
            overall_risk=overall_risk,
            flight_rules=flight_rules,
            base_score=base_score,
            vis_score=vis_score,
            ceiling_score=ceiling_score,
            wind_score=wind_score,
            temp_score=temp_score,
            weights=weights,
            vis_zone=vis_zone,
            ceiling_zone=ceiling_zone,
            wind_assessment=wind_assessment,
            override_reasons=override_reasons,
            risk_factors=unique_factors,
        )


def normalize_temp_score(temp_c: Optional[int]) -> float:
    """
    温度风险分数 (0-100) - 6档连续映射。

    积冰关注区间: -25°C ~ 5°C
    - >5°C 或 <-25°C → 0 (无积冰风险)
    - 2~5°C → 20~40 (轻微关注)
    - 0~2°C → 40~60 (积冰临界)
    - -5~0°C → 60~85 (积冰高风险)
    - -15~-5°C → 85~100 (积冰最高风险)
    - -25~-15°C → 60~85 (极低温，风险回落)
    """
    if temp_c is None:
        return 0.0

    if temp_c > 5 or temp_c < -25:
        return 0.0
    elif temp_c >= 2:
        return 20.0 + 20.0 * (5 - temp_c) / 3
    elif temp_c >= 0:
        return 40.0 + 20.0 * (2 - temp_c) / 2
    elif temp_c >= -5:
        return 60.0 + 25.0 * (0 - temp_c) / 5
    elif temp_c > -15:
        return 85.0 + 15.0 * (-5 - temp_c) / 10
    else:  # -25 <= temp_c <= -15
        return 60.0 + 25.0 * (-15 - temp_c) / 10


def _score_to_risk(score: float) -> str:
    """综合分数 → 风险等级"""
    if score >= 80:
        return "CRITICAL"
    elif score >= 55:
        return "HIGH"
    elif score >= 30:
        return "MEDIUM"
    else:
        return "LOW"


def _map_to_flight_rules(
    base_score: float,
    vis_score: float,
    ceiling_score: float,
    vis_km: Optional[float],
    ceiling_ft: Optional[int],
) -> str:
    """
    双轨飞行规则映射:
    1. 综合分数映射
    2. 分维度映射 (vis_km 和 ceiling_ft 各自独立)
    3. 取最严格的那个
    """
    # 轨道1: 综合分数映射
    if base_score >= 85:
        score_rules = "LIFR"
    elif base_score >= 65:
        score_rules = "IFR"
    elif base_score >= 40:
        score_rules = "MVFR"
    else:
        score_rules = "VFR"

    # 轨道2: 分维度映射
    # 能见度维度
    if vis_km is not None:
        if vis_km < 1:
            vis_rules = "LIFR"
        elif vis_km < 3:
            vis_rules = "IFR"
        elif vis_km < 5:
            vis_rules = "MVFR"
        else:
            vis_rules = "VFR"
    else:
        vis_rules = "VFR"

    # 云底高维度 (与6级Zone对齐)
    if ceiling_ft is not None:
        if ceiling_ft < 500:
            ceil_rules = "LIFR"
        elif ceiling_ft < 1000:
            ceil_rules = "IFR"
        elif ceiling_ft < 2500:
            ceil_rules = "MVFR"
        else:
            ceil_rules = "VFR"
    else:
        ceil_rules = "VFR"

    # 取最严格
    priority = {"VFR": 0, "MVFR": 1, "IFR": 2, "LIFR": 3}
    rules = [score_rules, vis_rules, ceil_rules]
    worst = max(rules, key=lambda r: priority.get(r, 0))
    return worst


def _risk_priority(risk: str) -> int:
    """风险等级优先级"""
    priority = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
    return priority.get(risk, 0)
