"""
进近标准计算工具 - 决断高(DH)和最低下降高(MDA)

民航标准进近最低值：
  ILS CAT I:   DH 200ft (决断高)
  ILS CAT II:  DH 100ft (决断高)
  ILS CAT III:  无DH（自动着陆）
  VOR进近:      MDA 约400-600ft
  NDB进近:      MDA 约500-700ft
  目视进近:      MDA 约300-500ft

注意：
- 实际DH/MDA因机场、跑道、进近程序而异
- 这里提供标准参考值，真实运行需查阅航图(AIP)
- 云底高 vs DH/MDA 的对比是飞行安全的关键判断
"""
from typing import Dict, Any, Optional, Tuple


# 标准进近最低值参考（英尺）
STANDARD_APPROACH_MINIMA = {
    "ILS_CAT_I": {
        "type": "DH",
        "value_ft": 200,
        "description": "ILS I类决断高",
        "min_visibility_m": 550,
        "min_visibility_ft": 1800,
    },
    "ILS_CAT_II": {
        "type": "DH",
        "value_ft": 100,
        "description": "ILS II类决断高",
        "min_visibility_m": 300,
        "min_visibility_ft": 1000,
    },
    "ILS_CAT_III": {
        "type": "DH",
        "value_ft": 0,
        "description": "ILS III类（自动着陆）",
        "min_visibility_m": 0,
        "min_visibility_ft": 0,
    },
    "VOR": {
        "type": "MDA",
        "value_ft": 500,
        "description": "VOR非精密进近最低下降高",
        "min_visibility_m": 1600,
        "min_visibility_ft": 5250,
    },
    "NDB": {
        "type": "MDA",
        "value_ft": 600,
        "description": "NDB非精密进近最低下降高",
        "min_visibility_m": 2000,
        "min_visibility_ft": 6560,
    },
    "VISUAL": {
        "type": "MDA",
        "value_ft": 400,
        "description": "目视进近最低下降高",
        "min_visibility_m": 5000,
        "min_visibility_ft": 16400,
    },
}


def get_decision_heights(cloud_ceiling_ft: Optional[int] = None) -> Dict[str, Any]:
    """
    获取各进近方式的决断高/MDA，并与当前云底高对比

    Args:
        cloud_ceiling_ft: 当前最低云底高度（英尺），可选

    Returns:
        包含各进近方式DH/MDA和可行性的字典
    """
    result = {
        "approaches": {},
        "recommended_approach": None,
        "ceiling_ft": cloud_ceiling_ft,
    }

    best_approach = None
    for approach_type, minima in STANDARD_APPROACH_MINIMA.items():
        dh_mda_ft = minima["value_ft"]
        can_approach = True

        if cloud_ceiling_ft is not None:
            # 云底高必须高于DH/MDA至少200ft才安全（简化规则）
            can_approach = cloud_ceiling_ft > dh_mda_ft

        entry = {
            "type": minima["type"],
            "value_ft": dh_mda_ft,
            "description": minima["description"],
            "feasible": can_approach,
            "min_visibility_m": minima["min_visibility_m"],
        }

        if can_approach and (best_approach is None or dh_mda_ft < STANDARD_APPROACH_MINIMA[best_approach]["value_ft"]):
            best_approach = approach_type

        result["approaches"][approach_type] = entry

    result["recommended_approach"] = best_approach
    return result


def format_decision_info(cloud_ceiling_ft: Optional[int] = None, visibility_km: Optional[float] = None) -> str:
    """
    格式化决断高/MDA信息为可读文本

    Args:
        cloud_ceiling_ft: 云底高（英尺）
        visibility_km: 能见度（公里）

    Returns:
        格式化的决断高信息文本
    """
    info = get_decision_heights(cloud_ceiling_ft)

    lines = []
    lines.append("【进近标准与决断高】")

    if cloud_ceiling_ft is not None:
        lines.append(f"当前云底高: {cloud_ceiling_ft} ft")
    else:
        lines.append("当前云底高: 无云层数据")

    lines.append("")
    lines.append("标准进近最低值参考：")

    for approach_type, entry in info["approaches"].items():
        status = "✅ 可行" if entry["feasible"] else "❌ 不可行"
        dh_label = "DH" if entry["type"] == "DH" else "MDA"
        lines.append(f"  - {entry['description']}: {dh_label} {entry['value_ft']}ft [{status}]")

    if info["recommended_approach"]:
        rec = STANDARD_APPROACH_MINIMA[info["recommended_approach"]]
        lines.append(f"\n推荐进近方式: {rec['description']}")

    return "\n".join(lines)


def check_ceiling_vs_dh(cloud_ceiling_ft: int, approach_type: str = "ILS_CAT_I") -> Tuple[bool, str]:
    """
    检查云底高是否满足进近最低标准

    Args:
        cloud_ceiling_ft: 云底高（英尺）
        approach_type: 进近方式

    Returns:
        (是否满足, 说明文字)
    """
    minima = STANDARD_APPROACH_MINIMA.get(approach_type)
    if not minima:
        return False, f"未知进近方式: {approach_type}"

    dh = minima["value_ft"]
    if cloud_ceiling_ft > dh:
        margin = cloud_ceiling_ft - dh
        return True, f"云底高 {cloud_ceiling_ft}ft 高于 {minima['description']} {dh}ft，余度 {margin}ft"
    else:
        shortfall = dh - cloud_ceiling_ft
        return False, f"云底高 {cloud_ceiling_ft}ft 低于 {minima['description']} {dh}ft，差 {shortfall}ft，不满足进近标准"
