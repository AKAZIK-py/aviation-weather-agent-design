"""
多维度个性化策略引擎
5维个性化：角色 + 飞行阶段 + 机型 + 机场 + 紧迫性
在已有角色system_prompts基础上增强，不替换
"""
from typing import Dict, Any, Optional


# ==================== 个性化维度定义 ====================

PERSONALIZATION_DIMENSIONS = {
    "role": {
        "pilot": "飞行员",
        "dispatcher": "签派管制",
        "forecaster": "预报员",
        "ground_crew": "地勤机务",
    },
    "flight_phase": {
        "pre_departure": "起飞前",
        "en_route": "航路中",
        "approach": "进近阶段",
        "diversion": "备降阶段",
    },
    "aircraft_type": {
        "heavy": "重型机(B777/A330等)",
        "regional": "支线机(CRJ/ERJ等)",
        "helicopter": "直升机",
    },
    "urgency": {
        "normal": "常规",
        "urgent": "紧急",
        "critical": "特急",
    },
}

# 有效枚举值集合（用于校验）
VALID_VALUES = {
    "role": set(PERSONALIZATION_DIMENSIONS["role"].keys()),
    "flight_phase": set(PERSONALIZATION_DIMENSIONS["flight_phase"].keys()),
    "aircraft_type": set(PERSONALIZATION_DIMENSIONS["aircraft_type"].keys()),
    "urgency": set(PERSONALIZATION_DIMENSIONS["urgency"].keys()),
}


# ==================== 飞行阶段附加提示 ====================

_FLIGHT_PHASE_PROMPTS: Dict[str, str] = {
    "pre_departure": """【飞行阶段：起飞前】
重点关注：
- 本场METAR/TAF趋势是否满足起飞标准
- 备降场天气是否达标
- 侧风限制是否在机型限制内
- 积冰条件评估（温度0~-15°C区间）""",

    "en_route": """【飞行阶段：航路中】
重点关注：
- 目的地/备降场天气趋势
- 航路危险天气（雷暴/积冰/颠簸）
- 风对燃油消耗的影响
- 是否需要提前决策备降""",

    "approach": """【飞行阶段：进近阶段】
重点关注：
- 跑道视程(RVR)与决断高对比
- 侧风分量与着陆限制
- 风切变报告
- 复飞程序适用性""",

    "diversion": """【飞行阶段：备降阶段】
重点关注：
- 备降场天气是否满足着陆标准
- 剩余油量与距离评估
- 备降场进近方式可选性
- 是否需要二次备降""",
}


# ==================== 机型附加提示 ====================

_AIRCRAFT_TYPE_PROMPTS: Dict[str, str] = {
    "heavy": """【机型：重型机】
- 侧风限制通常38KT（干跑道）/25KT（湿跑道）
- 大翼面积对积冰更敏感
- 起降滑跑距离较长，需关注RVR
- 高空颠簸感知较弱""",

    "regional": """【机型：支线机】
- 侧风限制通常25-30KT
- 对低能见度和低云更敏感
- 受阵风影响更大
- 巡航高度较低，受低层天气影响更大""",

    "helicopter": """【机型：直升机】
- 能见度限制通常为G类空域标准
- 可在较低能见度下运行（目视飞行）
- 侧风限制通常25KT
- 对风切变和下降气流极其敏感
- 需关注自由涡轮温度限制""",
}


# ==================== 紧迫性附加提示 ====================

_URGENCY_PROMPTS: Dict[str, str] = {
    "normal": "",  # 常规不添加额外提示

    "urgent": """【紧迫性：紧急】
- 请精简分析，突出最关键信息
- 直接给出GO/NO-GO建议
- 备降场推荐优先级排前列""",

    "critical": """【紧迫性：特急】
- 仅输出关键安全信息
- 首行即标明：是否适飞
- 给出最短路径决策
- 若有CRITICAL风险因素立即标红""",
}


class PersonalizationEngine:
    """多维度个性化引擎"""

    def __init__(self):
        self.dimensions = PERSONALIZATION_DIMENSIONS

    @staticmethod
    def validate_params(
        role: Optional[str] = None,
        flight_phase: Optional[str] = None,
        aircraft_type: Optional[str] = None,
        urgency: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        校验个性化参数，返回错误字典（空字典表示全部通过）

        Returns:
            错误字段名 → 错误描述 的字典
        """
        errors: Dict[str, str] = {}

        if role is not None and role not in VALID_VALUES["role"]:
            errors["role"] = (
                f"无效role='{role}'，可选: {sorted(VALID_VALUES['role'])}"
            )
        if flight_phase is not None and flight_phase not in VALID_VALUES["flight_phase"]:
            errors["flight_phase"] = (
                f"无效flight_phase='{flight_phase}'，可选: {sorted(VALID_VALUES['flight_phase'])}"
            )
        if aircraft_type is not None and aircraft_type not in VALID_VALUES["aircraft_type"]:
            errors["aircraft_type"] = (
                f"无效aircraft_type='{aircraft_type}'，可选: {sorted(VALID_VALUES['aircraft_type'])}"
            )
        if urgency is not None and urgency not in VALID_VALUES["urgency"]:
            errors["urgency"] = (
                f"无效urgency='{urgency}'，可选: {sorted(VALID_VALUES['urgency'])}"
            )

        return errors

    @staticmethod
    def build_personalized_prompt(
        metar: str,
        role: str = "dispatcher",
        flight_phase: Optional[str] = None,
        aircraft_type: Optional[str] = None,
        urgency: Optional[str] = None,
    ) -> str:
        """
        构建多维度增强的提示词

        Args:
            metar: 原始METAR报文
            role: 用户角色
            flight_phase: 飞行阶段（可选）
            aircraft_type: 机型（可选）
            urgency: 紧迫性（可选）

        Returns:
            增强后的提示词（在角色system_prompt基础上附加维度信息）
        """
        parts: list[str] = []

        # 维度上下文摘要
        dim_labels: list[str] = []
        role_cn = PERSONALIZATION_DIMENSIONS["role"].get(role, role)
        dim_labels.append(f"角色={role_cn}")

        if flight_phase:
            fp_cn = PERSONALIZATION_DIMENSIONS["flight_phase"].get(flight_phase, flight_phase)
            dim_labels.append(f"阶段={fp_cn}")
        if aircraft_type:
            at_cn = PERSONALIZATION_DIMENSIONS["aircraft_type"].get(aircraft_type, aircraft_type)
            dim_labels.append(f"机型={at_cn}")
        if urgency:
            u_cn = PERSONALIZATION_DIMENSIONS["urgency"].get(urgency, urgency)
            dim_labels.append(f"紧迫性={u_cn}")

        parts.append(f"【上下文维度】{' | '.join(dim_labels)}")
        parts.append(f"METAR报文：{metar}")

        # 附加各维度提示
        if flight_phase and flight_phase in _FLIGHT_PHASE_PROMPTS:
            parts.append(_FLIGHT_PHASE_PROMPTS[flight_phase])

        if aircraft_type and aircraft_type in _AIRCRAFT_TYPE_PROMPTS:
            parts.append(_AIRCRAFT_TYPE_PROMPTS[aircraft_type])

        if urgency and urgency in _URGENCY_PROMPTS and _URGENCY_PROMPTS[urgency]:
            parts.append(_URGENCY_PROMPTS[urgency])

        return "\n\n".join(parts)

    @staticmethod
    def get_dimension_info() -> Dict[str, Any]:
        """返回所有维度的定义信息"""
        return PERSONALIZATION_DIMENSIONS


# 模块级便捷函数
def build_personalized_prompt(
    metar: str,
    role: str = "dispatcher",
    flight_phase: Optional[str] = None,
    aircraft_type: Optional[str] = None,
    urgency: Optional[str] = None,
) -> str:
    """模块级便捷函数"""
    return PersonalizationEngine.build_personalized_prompt(
        metar, role, flight_phase, aircraft_type, urgency
    )


__all__ = [
    "PersonalizationEngine",
    "PERSONALIZATION_DIMENSIONS",
    "VALID_VALUES",
    "build_personalized_prompt",
]
