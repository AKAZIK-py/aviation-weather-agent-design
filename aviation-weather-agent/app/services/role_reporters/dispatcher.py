"""
DispatcherReporter - 签派员视角的报告生成器

关注点：航班运行效率与决策支持
- 允许：飞行规则、能见度、云底高、天气现象、延误相关
- 过滤：DH/MDA、进近方式细节、积冰细节
"""
from typing import Dict, Any, List

from app.services.role_reporters.base import BaseReporter
from app.utils.visibility import format_visibility_range


class DispatcherReporter(BaseReporter):
    """签派员角色报告生成器"""

    ROLE = "dispatcher"
    ROLE_CN = "签派员"

    # 允许的风险因素关键词
    ALLOWED_RISK_KEYWORDS = {
        "飞行规则", "VFR", "IFR", "MVFR", "LIFR",
        "能见度", "低能见", "雾", "FG",
        "云底高", "低云", "云层",
        "天气现象", "雷暴", "TS", "降水", "雨", "雪", "SN",
        "延误", "取消", "备降", "放行",
        "风", "阵风", "风切变",
        "跑道",
    }

    # 过滤掉的关键词
    FILTERED_RISK_KEYWORDS = {
        "DH", "MDA", "决断高", "ILS CAT", "进近方式",
        "积冰细节", "化油器", "机体积冰",
        "户外作业", "设备", "维护", "机务",
        "航材", "存储", "加油作业", "除防冰",
        "趋势预报", "TAF", "SIGMET",
        "动态",
    }

    def generate_advice(
        self,
        metar_data: Dict[str, Any],
        risk_factors: List[str],
        risk_level: str,
    ) -> str:
        """生成签派员专属建议"""
        advice = []
        factors_text = " ".join(risk_factors).lower()
        vis = metar_data.get("visibility")
        flight_rules = metar_data.get("flight_rules", "UNKNOWN")

        # 飞行规则评估
        if flight_rules in ("IFR", "LIFR"):
            advice.append(f"1. 【飞行规则】当前为{flight_rules}，需IFR放行程序")
        elif flight_rules == "MVFR":
            advice.append(f"1. 【飞行规则】当前为MVFR，VFR运行受限，建议关注变化趋势")

        # 能见度相关
        if vis is not None and vis < 3:
            vis_range = format_visibility_range(vis)
            if vis < 1:
                advice.append(f"2. 【能见度】能见度{vis_range}，运行严重受限，评估延误需求")
            else:
                advice.append(f"2. 【能见度】能见度{vis_range}，进场率可能下降")

        # 雷暴
        if "雷暴" in factors_text or "TS" in factors_text:
            advice.append("3. 【雷暴】雷暴活动将影响进离场航路，评估延误和改航方案")

        # 积冰（仅关注对运行的影响，不涉及技术细节）
        if "积冰" in factors_text or "结冰" in factors_text:
            advice.append("4. 【积冰】存在积冰条件，通知机组执行除冰程序，评估延误")

        # 根据风险等级生成签派决策建议
        if risk_level == "CRITICAL":
            advice.append("")
            advice.append("【签派决策】")
            advice.append("• 建议延误或取消航班")
            advice.append("• 准备备降方案")
            advice.append("• 通知所有受影响机组")
        elif risk_level == "HIGH":
            advice.append("")
            advice.append("【签派决策】")
            advice.append("• 条件放行，通知机组风险状况")
            advice.append("• 准备备降场方案")
            advice.append("• 监控天气变化，做好延误准备")
        elif risk_level == "MEDIUM":
            advice.append("")
            advice.append("【签派决策】")
            advice.append("• 正常放行，关注天气变化")
            advice.append("• 评估是否需要额外燃油")
        elif risk_level == "LOW":
            advice.append("")
            advice.append("【签派决策】")
            advice.append("• 正常放行")
            advice.append("• 持续监控天气趋势")

        if not advice:
            advice.append("当前运行条件正常，正常放行。")

        return "\n".join(advice)

    def get_extra_fields(
        self,
        metar_data: Dict[str, Any],
        risk_factors: List[str],
        risk_level: str,
    ) -> Dict[str, Any]:
        """签派员额外字段：放行状态、备降需求、延误概率"""
        vis = metar_data.get("visibility")
        flight_rules = metar_data.get("flight_rules", "UNKNOWN")

        # 放行状态
        if risk_level == "CRITICAL":
            release_status = "建议取消/延误"
        elif risk_level == "HIGH":
            release_status = "条件放行"
        elif risk_level == "MEDIUM":
            release_status = "正常放行（监控）"
        else:
            release_status = "正常放行"

        # 备降需求
        alternate_required = risk_level in ("CRITICAL", "HIGH")

        # 延误概率
        delay_map = {
            "CRITICAL": 90,
            "HIGH": 60,
            "MEDIUM": 20,
            "LOW": 5,
        }
        delay_probability = delay_map.get(risk_level, 10)

        return {
            "release_status": release_status,
            "alternate_required": alternate_required,
            "delay_probability": delay_probability,
        }
