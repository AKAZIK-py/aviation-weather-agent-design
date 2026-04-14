"""
能见度5级区间 + 对数归一化模块

Zone 1: ≥10km — 无影响
Zone 2: 5-10km — 极低风险
Zone 3: 3-5km — 需关注
Zone 4: 1-3km — 高风险
Zone 5: <1km — 危险/不适航

buffer=500m
"""
import math
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class VisibilityZone:
    """能见度区间诊断结果"""
    zone: int                          # 区间编号 1-5
    label: str                         # 区间标签
    color: str                         # 颜色标识
    risk_level: str                    # 风险等级
    visibility_km: Optional[float]     # 实际能见度 (km)
    in_buffer: bool                    # 是否在缓冲区内
    buffer_zones: List[int] = field(default_factory=list)
    description: str = ""

    @property
    def score(self) -> float:
        """映射到 0-100 分数"""
        return normalize_visibility_score(self.visibility_km)


# 区间定义: (下界km, 上界km, zone编号, 标签, 颜色, 风险等级)
_ZONE_DEFS = [
    (10,          float('inf'), 1, "无影响",     "GREEN",  "LOW"),
    (5,           10,           2, "极低风险",   "GREEN",  "LOW"),
    (3,           5,            3, "需关注",     "YELLOW", "MEDIUM"),
    (1,           3,            4, "高风险",     "ORANGE", "HIGH"),
    (0,           1,            5, "危险/不适航", "RED",    "CRITICAL"),
]

# 缓冲区大小 (km)
_BUFFER_KM = 0.5


def classify_visibility(vis_km: Optional[float]) -> VisibilityZone:
    """
    对能见度进行5级区间诊断，含缓冲区逻辑。

    Args:
        vis_km: 能见度（公里），None 表示无数据。

    Returns:
        VisibilityZone 诊断结果
    """
    if vis_km is None:
        return VisibilityZone(
            zone=1, label="无影响", color="GREEN", risk_level="LOW",
            visibility_km=None, in_buffer=False, buffer_zones=[],
            description="无能见度数据，默认无影响",
        )

    # 确定主 zone
    main_def = None
    for low, high, zone_id, label, color, risk in _ZONE_DEFS:
        if low <= vis_km < high:
            main_def = (zone_id, label, color, risk)
            break

    if main_def is None:
        main_def = (1, "无影响", "GREEN", "LOW")

    zone_id, label, color, risk = main_def

    # 缓冲区检测
    in_buffer = False
    buffer_zones: List[int] = []

    for low, high, adj_zone, _l, _c, _r in _ZONE_DEFS:
        if adj_zone == zone_id:
            continue
        # 检查是否在相邻 zone 边界的缓冲区内
        if adj_zone == zone_id - 1:
            # 上方相邻 zone: vis_km 接近当前 zone 的上界 (即上方 zone 的下界)
            boundary = low  # 当前 zone 的下界也是上方相邻 zone 的边界
            if abs(vis_km - boundary) <= _BUFFER_KM:
                in_buffer = True
                buffer_zones.append(adj_zone)
        elif adj_zone == zone_id + 1:
            # 下方相邻 zone: vis_km 接近当前 zone 的下界 (即下方 zone 的上界)
            boundary = high  # 当前 zone 的上界也是下方相邻 zone 的边界
            if abs(vis_km - boundary) <= _BUFFER_KM and boundary != float('inf'):
                in_buffer = True
                buffer_zones.append(adj_zone)

    desc = f"能见度 {vis_km}km → Zone {zone_id} ({label})"
    if in_buffer:
        desc += f" [缓冲区: 同时触发 Zone {buffer_zones}]"

    return VisibilityZone(
        zone=zone_id, label=label, color=color, risk_level=risk,
        visibility_km=vis_km, in_buffer=in_buffer,
        buffer_zones=sorted(buffer_zones), description=desc,
    )


def _get_zone_upper_bound(zone_id: int) -> Optional[float]:
    """获取 zone 的上界"""
    bounds = {1: 10, 2: 10, 3: 5, 4: 3, 5: 1}
    return bounds.get(zone_id)


def _get_zone_lower_bound(zone_id: int) -> Optional[float]:
    """获取 zone 的下界"""
    bounds = {1: 10, 2: 5, 3: 3, 4: 1, 5: 0}
    return bounds.get(zone_id)


def normalize_visibility_score(vis_km: Optional[float]) -> float:
    """
    将能见度归一化为 0-100 分数（对数映射）。

    公式: 100 * (1 - log(vis + 1) / log(11))

    - vis=10km → ~69 (但实际用 clamp 处理为低分)
    - vis=0km → 100
    - vis>=10km → 0

    使用分段逻辑确保:
    - >=10km → 0
    - <0.05km → 100
    """
    if vis_km is None:
        return 0.0

    if vis_km >= 10:
        return 0.0
    if vis_km <= 0:
        return 100.0

    # 对数映射: vis=10→0, vis=0→100
    score = 100.0 * (1.0 - math.log(vis_km + 1.0) / math.log(11.0))
    return max(0.0, min(100.0, score))
