"""
云底高6级区间诊断模块

Zone 1: >4000ft (1219m) — 无影响, GREEN
Zone 2: 2500-4000ft (762-1219m) — 极低风险, GREEN, buffer=200ft
Zone 3: 1000-2500ft (305-762m) — 低中云(需关注), YELLOW, buffer=200ft
Zone 4: 500-1000ft (152-305m) — 低云(高风险), ORANGE, buffer=150ft
Zone 5: 300-500ft (91-152m) — 极低云底(危险), RED, buffer=100ft
Zone 6: <300ft (<91m) — 危险/不适航, RED, buffer=100ft

缓冲区内同时触发相邻两个 zone 的告警
None (无BKN/OVC) → Zone 1
"""
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class CeilingZone:
    """云底高区间诊断结果"""
    zone: int                          # 区间编号 1-5
    label: str                         # 区间标签
    color: str                         # 颜色标识
    risk_level: str                    # 风险等级 (LOW/MEDIUM/HIGH/CRITICAL)
    ceiling_ft: Optional[int]          # 实际云底高 (ft), None 表示无 BKN/OVC
    in_buffer: bool                    # 是否在缓冲区内
    buffer_zones: List[int] = field(default_factory=list)  # 缓冲区触发的相邻 zone
    description: str = ""              # 描述信息

    @property
    def all_zones(self) -> List[int]:
        """返回所有触发的 zone（含自身 + 缓冲区触发的）"""
        zones = [self.zone]
        for z in self.buffer_zones:
            if z not in zones:
                zones.append(z)
        return sorted(zones)

    @property
    def score(self) -> float:
        """映射到 0-100 分数 (zone 1=0, zone 6=100)"""
        score_map = {1: 0, 2: 10, 3: 30, 4: 55, 5: 80, 6: 95}
        return score_map.get(self.zone, 0)


# 区间定义: (下界ft, 上界ft, zone编号, 标签, 颜色, 风险等级, 缓冲区ft)
_ZONE_DEFS = [
    (4000,   float('inf'), 1, "无影响",         "GREEN",  "LOW",      200),
    (2500,   4000,         2, "极低风险",       "GREEN",  "LOW",      200),
    (1000,   2500,         3, "低中云(需关注)",  "YELLOW", "MEDIUM",   200),
    (500,    1000,         4, "低云(高风险)",    "ORANGE", "HIGH",     150),
    (300,    500,          5, "极低云底(危险)",  "RED",    "CRITICAL", 100),
    (0,      300,          6, "危险/不适航",     "RED",    "CRITICAL", 100),
]


def classify(ceiling_ft: Optional[int]) -> CeilingZone:
    """
    对云底高进行5级区间诊断，含缓冲区逻辑。

    Args:
        ceiling_ft: 最低 BKN/OVC/VV 云底高（英尺），None 表示无遮蔽。

    Returns:
        CeilingZone 诊断结果
    """
    # 无 BKN/OVC → Zone 1
    if ceiling_ft is None:
        return CeilingZone(
            zone=1,
            label="无影响",
            color="GREEN",
            risk_level="LOW",
            ceiling_ft=None,
            in_buffer=False,
            buffer_zones=[],
            description="无 BKN/OVC 云层，云底高无限制",
        )

    # 确定主 zone
    main_def = None
    for low, high, zone_id, label, color, risk, _buf in _ZONE_DEFS:
        if low <= ceiling_ft < high:
            main_def = (zone_id, label, color, risk)
            break

    if main_def is None:
        # fallback (should not reach here)
        main_def = (1, "无影响", "GREEN", "LOW")

    zone_id, label, color, risk = main_def

    # 缓冲区检测
    in_buffer = False
    buffer_zones: List[int] = []

    for low, high, adj_zone, _l, _c, _r, buf in _ZONE_DEFS:
        if adj_zone == zone_id:
            continue
        # 检查是否在相邻 zone 的缓冲区内
        if adj_zone == zone_id - 1:
            # 上方相邻 zone: ceiling_ft 接近当前 zone 的上界
            boundary = low  # 当前 zone 的下界 = 上方 zone 的边界
            if abs(ceiling_ft - boundary) <= buf:
                in_buffer = True
                buffer_zones.append(adj_zone)
        elif adj_zone == zone_id + 1:
            # 下方相邻 zone: ceiling_ft 接近当前 zone 的下界
            boundary = high  # 当前 zone 的上界 = 下方 zone 的边界
            if boundary != float('inf') and abs(ceiling_ft - boundary) <= buf:
                in_buffer = True
                buffer_zones.append(adj_zone)

    desc = f"云底高 {ceiling_ft}ft → Zone {zone_id} ({label})"
    if in_buffer:
        desc += f" [缓冲区: 同时触发 Zone {buffer_zones}]"

    return CeilingZone(
        zone=zone_id,
        label=label,
        color=color,
        risk_level=risk,
        ceiling_ft=ceiling_ft,
        in_buffer=in_buffer,
        buffer_zones=sorted(buffer_zones),
        description=desc,
    )


def _get_upper_bound(zone_id: int) -> Optional[int]:
    """获取 zone 的上界"""
    bounds = {1: 4000, 2: 4000, 3: 2500, 4: 1000, 5: 500, 6: 300}
    return bounds.get(zone_id)


def _get_lower_bound(zone_id: int) -> Optional[int]:
    """获取 zone 的下界"""
    bounds = {1: 4000, 2: 2500, 3: 1000, 4: 500, 5: 300, 6: 0}
    return bounds.get(zone_id)


def normalize_ceiling_score(ceiling_ft: Optional[int]) -> float:
    """
    将云底高归一化为 0-100 分数（分段线性插值，6档）。

    - >=4000ft → 0
    - 2500-4000ft → 0-15
    - 1000-2500ft → 15-35
    - 500-1000ft → 35-60
    - 300-500ft → 60-80
    - <300ft → 80-100
    """
    if ceiling_ft is None:
        return 0.0

    if ceiling_ft >= 4000:
        return 0.0
    elif ceiling_ft >= 2500:
        # 2500-4000 → 0-15
        return 15.0 * (4000 - ceiling_ft) / (4000 - 2500)
    elif ceiling_ft >= 1000:
        # 1000-2500 → 15-35
        return 15.0 + 20.0 * (2500 - ceiling_ft) / (2500 - 1000)
    elif ceiling_ft >= 500:
        # 500-1000 → 35-60
        return 35.0 + 25.0 * (1000 - ceiling_ft) / (1000 - 500)
    elif ceiling_ft >= 300:
        # 300-500 → 60-80
        return 60.0 + 20.0 * (500 - ceiling_ft) / (500 - 300)
    else:
        # <300 → 80-100
        return min(100.0, 80.0 + 20.0 * (300 - ceiling_ft) / 300)
