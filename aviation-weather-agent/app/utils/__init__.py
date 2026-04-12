"""工具函数模块"""
from app.utils.visibility import (
    format_visibility_range,
    get_visibility_range_label,
    is_unflyable,
    VISIBILITY_RANGES,
)
from app.utils.approach import (
    get_decision_heights,
    format_decision_info,
    check_ceiling_vs_dh,
    STANDARD_APPROACH_MINIMA,
)

# 动态风险评估系统
from app.utils.ceiling_zones import (
    classify as classify_ceiling,
    normalize_ceiling_score,
    CeilingZone,
)
from app.utils.visibility_zones import (
    classify_visibility,
    normalize_visibility_score,
    VisibilityZone,
)
from app.utils.dynamic_weights import (
    get_weight_for_phenomena,
    WEIGHT_MATRIX,
)
from app.utils.wind_assessment import (
    assess_wind,
    normalize_wind_score,
    WindAssessment,
)
from app.utils.dynamic_risk_engine import (
    DynamicRiskEngine,
    DynamicRiskReport,
)

__all__ = [
    # 能见度工具
    "format_visibility_range",
    "get_visibility_range_label",
    "is_unflyable",
    "VISIBILITY_RANGES",
    # 进近标准工具
    "get_decision_heights",
    "format_decision_info",
    "check_ceiling_vs_dh",
    "STANDARD_APPROACH_MINIMA",
    # 云底高区间
    "classify_ceiling",
    "normalize_ceiling_score",
    "CeilingZone",
    # 能见度区间
    "classify_visibility",
    "normalize_visibility_score",
    "VisibilityZone",
    # 动态权重
    "get_weight_for_phenomena",
    "WEIGHT_MATRIX",
    # 大风评估
    "assess_wind",
    "normalize_wind_score",
    "WindAssessment",
    # 综合风险引擎
    "DynamicRiskEngine",
    "DynamicRiskReport",
]
