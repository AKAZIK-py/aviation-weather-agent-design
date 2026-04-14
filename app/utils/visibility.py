"""
能见度区间化工具 - 统一能见度展示格式

民航标准能见度区间：
  <1km    - 极低能见度（LIFR）
  1-2km   - 低能见度（IFR）
  2-4km   - 较低能见度（IFR/MVFR边界）
  4-6km   - 中等能见度（MVFR）
  6-10km  - 良好能见度（VFR）
  >10km   - 优秀能见度（VFR/CAVOK）

核心原则：
- 对外展示只用区间，禁止输出9.999等精确数值
- 内部计算仍使用精确值
"""
from typing import Tuple


# 能见度区间定义（单位：km）
VISIBILITY_RANGES = [
    (0, 1, "<1km"),
    (1, 2, "1-2km"),
    (2, 4, "2-4km"),
    (4, 6, "4-6km"),
    (6, 10, "6-10km"),
    (10, float("inf"), ">10km"),
]


def format_visibility_range(vis_km: float) -> str:
    """
    将精确能见度值转换为区间表示

    Args:
        vis_km: 能见度（公里），如 9.999, 0.8, 5.5

    Returns:
        区间字符串，如 ">10km", "<1km", "4-6km"

    Examples:
        >>> format_visibility_range(9.999)
        '6-10km'
        >>> format_visibility_range(10.0)
        '>10km'
        >>> format_visibility_range(0.8)
        '<1km'
        >>> format_visibility_range(3.2)
        '2-4km'
    """
    if vis_km is None:
        return "未知"

    # CAVOK 或 >=10km
    if vis_km >= 10:
        return ">10km"

    for low, high, label in VISIBILITY_RANGES:
        if low <= vis_km < high:
            return label

    # fallback（不应到达）
    return f"{vis_km:.1f}km"


def get_visibility_range_label(vis_km: float) -> Tuple[str, str]:
    """
    获取能见度区间标签和对应的飞行规则倾向

    Args:
        vis_km: 能见度（公里）

    Returns:
        (区间标签, 飞行规则倾向)
    """
    range_label = format_visibility_range(vis_km)

    rule_hint = {
        "<1km": "LIFR/不适飞",
        "1-2km": "IFR",
        "2-4km": "IFR/MVFR",
        "4-6km": "MVFR",
        "6-10km": "VFR",
        ">10km": "VFR",
    }.get(range_label, "未知")

    return range_label, rule_hint


def is_unflyable(vis_km: float) -> bool:
    """
    判断是否不适飞（能见度 < 1km）
    
    Args:
        vis_km: 能见度（公里）
    
    Returns:
        True 表示不适飞
    """
    return vis_km is not None and vis_km < 1.0
