"""
天气现象动态权重矩阵

每个天气现象对应 W_vis/W_ceil/W_wind/W_temp 四个权重，总和=1.0
多现象叠加: 取各维度权重的最大值（最危险原则）
"""
from typing import Dict, List


# 权重矩阵: {现象代码: {W_vis, W_ceil, W_wind, W_temp}}
WEIGHT_MATRIX: Dict[str, Dict[str, float]] = {
    # === 正常/晴好 ===
    "CAVOK": {"W_vis": 0.10, "W_ceil": 0.10, "W_wind": 0.40, "W_temp": 0.40},
    "NSC":   {"W_vis": 0.10, "W_ceil": 0.10, "W_wind": 0.40, "W_temp": 0.40},
    "CLR":   {"W_vis": 0.10, "W_ceil": 0.10, "W_wind": 0.40, "W_temp": 0.40},

    # === 雾类 ===
    "FG":    {"W_vis": 0.70, "W_ceil": 0.05, "W_wind": 0.05, "W_temp": 0.20},
    "FZFG":  {"W_vis": 0.50, "W_ceil": 0.05, "W_wind": 0.05, "W_temp": 0.40},
    "BR":    {"W_vis": 0.60, "W_ceil": 0.10, "W_wind": 0.10, "W_temp": 0.20},
    "HZ":    {"W_vis": 0.60, "W_ceil": 0.15, "W_wind": 0.15, "W_temp": 0.10},

    # === 降水 ===
    "RA":    {"W_vis": 0.40, "W_ceil": 0.30, "W_wind": 0.15, "W_temp": 0.15},
    "+RA":   {"W_vis": 0.40, "W_ceil": 0.35, "W_wind": 0.15, "W_temp": 0.10},
    "SN":    {"W_vis": 0.45, "W_ceil": 0.25, "W_wind": 0.15, "W_temp": 0.15},
    "+SN":   {"W_vis": 0.50, "W_ceil": 0.25, "W_wind": 0.15, "W_temp": 0.10},

    # === 冻降水 ===
    "FZRA":  {"W_vis": 0.30, "W_ceil": 0.15, "W_wind": 0.15, "W_temp": 0.40},
    "FZDZ":  {"W_vis": 0.35, "W_ceil": 0.15, "W_wind": 0.15, "W_temp": 0.35},

    # === 雷暴 ===
    "TS":    {"W_vis": 0.25, "W_ceil": 0.30, "W_wind": 0.35, "W_temp": 0.10},
    "+TSRA": {"W_vis": 0.35, "W_ceil": 0.35, "W_wind": 0.20, "W_temp": 0.10},
    "TSGR":  {"W_vis": 0.20, "W_ceil": 0.25, "W_wind": 0.35, "W_temp": 0.20},

    # === 风相关 ===
    "WS":         {"W_vis": 0.05, "W_ceil": 0.05, "W_wind": 0.80, "W_temp": 0.10},
    "HIGH_WIND":  {"W_vis": 0.05, "W_ceil": 0.05, "W_wind": 0.70, "W_temp": 0.20},

    # === 沙尘/扬沙 ===
    "SS":    {"W_vis": 0.75, "W_ceil": 0.10, "W_wind": 0.10, "W_temp": 0.05},
    "DS":    {"W_vis": 0.80, "W_ceil": 0.05, "W_wind": 0.10, "W_temp": 0.05},
    "DU":    {"W_vis": 0.65, "W_ceil": 0.10, "W_wind": 0.15, "W_temp": 0.10},
    "SA":    {"W_vis": 0.60, "W_ceil": 0.10, "W_wind": 0.20, "W_temp": 0.10},

    # === 其他 ===
    "VA":    {"W_vis": 0.55, "W_ceil": 0.20, "W_wind": 0.15, "W_temp": 0.10},
    "GR":    {"W_vis": 0.30, "W_ceil": 0.25, "W_wind": 0.30, "W_temp": 0.15},
    "PL":    {"W_vis": 0.35, "W_ceil": 0.25, "W_wind": 0.20, "W_temp": 0.20},
    "IC":    {"W_vis": 0.30, "W_ceil": 0.20, "W_wind": 0.15, "W_temp": 0.35},

    # === 默认复合 ===
    "_COMPOUND_DEFAULT": {"W_vis": 0.30, "W_ceil": 0.25, "W_wind": 0.25, "W_temp": 0.20},
}


def get_weight_for_phenomena(phenomena_list: List[str]) -> Dict[str, float]:
    """
    根据天气现象列表计算动态权重（最危险原则：取各维度最大值）。

    Args:
        phenomena_list: 天气现象代码列表，如 ["FG", "RA"]

    Returns:
        {W_vis, W_ceil, W_wind, W_temp} 权重字典
    """
    if not phenomena_list:
        return {"W_vis": 0.25, "W_ceil": 0.25, "W_wind": 0.25, "W_temp": 0.25}

    result = {"W_vis": 0.0, "W_ceil": 0.0, "W_wind": 0.0, "W_temp": 0.0}

    matched = False
    for phen in phenomena_list:
        # 精确匹配
        if phen in WEIGHT_MATRIX:
            weights = WEIGHT_MATRIX[phen]
            matched = True
        # 尝试前缀匹配 (如 "+TSRA" 匹配 "+TSRA", "TS" 匹配 "TS")
        else:
            weights = _find_best_match(phen)
            if weights is not None:
                matched = True
            else:
                continue

        for key in result:
            result[key] = max(result[key], weights[key])

    # 如果没有任何匹配，使用默认复合权重
    if not matched:
        result = dict(WEIGHT_MATRIX["_COMPOUND_DEFAULT"])

    # 归一化确保总和=1.0
    total = sum(result.values())
    if total > 0:
        for key in result:
            result[key] = round(result[key] / total, 4)

    return result


def _find_best_match(phenomenon: str) -> Dict[str, float]:
    """
    尝试模糊匹配天气现象。

    例如: "TSRA" 可能匹配 "TS" 或 "+TSRA"
    """
    # 尝试包含匹配（优先级: 完全包含 > 前缀包含）
    best_match = None
    best_len = 0

    for code, weights in WEIGHT_MATRIX.items():
        if code.startswith("_"):
            continue
        if code in phenomenon or phenomenon in code:
            if len(code) > best_len:
                best_match = weights
                best_len = len(code)

    return best_match
