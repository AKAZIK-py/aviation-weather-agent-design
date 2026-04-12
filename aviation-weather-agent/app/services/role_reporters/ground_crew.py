"""
GroundCrewReporter - 地勤机务视角的报告生成器

关注点：航空器维护与地面作业安全
- 允许：温度、降水、风力、能见度（仅地面作业影响）、积冰
- 过滤：飞行规则、DH/MDA、云底高（对地勤不重要）、进近方式
"""
from typing import Dict, Any, List

from app.services.role_reporters.base import BaseReporter
from app.utils.visibility import format_visibility_range


class GroundCrewReporter(BaseReporter):
    """地勤机务角色报告生成器"""

    ROLE = "ground_crew"
    ROLE_CN = "地勤机务"

    # 允许的风险因素关键词
    ALLOWED_RISK_KEYWORDS = {
        "温度", "低温", "高温",
        "降水", "雨", "雪", "SN", "RA", "冻雨",
        "风", "大风", "阵风", "风力",
        "能见度", "低能见", "雾", "FG", "冻雾", "FZFG",
        "积冰", "结冰", "霜",
        "沙尘", "SS", "DS",
        "雷暴", "TS",
    }

    # 过滤掉的关键词
    FILTERED_RISK_KEYWORDS = {
        "飞行规则", "VFR", "IFR", "MVFR", "LIFR",
        "DH", "MDA", "决断高", "ILS", "CAT",
        "云底高", "低云", "云层",
        "进近", "进近方式",
        "放行", "签派", "延误", "取消", "备降",
        "趋势预报", "TAF", "SIGMET",
        "动态",
    }

    def generate_advice(
        self,
        metar_data: Dict[str, Any],
        risk_factors: List[str],
        risk_level: str,
    ) -> str:
        """生成地勤机务专属建议"""
        advice = []
        factors_text = " ".join(risk_factors).lower()
        temp = metar_data.get("temperature")
        wind = metar_data.get("wind_speed", 0) or 0
        gust = metar_data.get("wind_gust")
        wx = [w.get("code", "") for w in metar_data.get("present_weather", [])]
        wx_text = " ".join(wx)

        # 积冰条件
        if "积冰" in factors_text or "结冰" in factors_text or "FZ" in wx_text:
            advice.append("1. 【积冰警告】航空器表面可能结冰，停止户外清洗/加油作业")
            if temp is not None and temp <= 0:
                advice.append(f"   当前温度{temp}°C，液体可能结冰，检查排水系统")
            advice.append("   确认除冰液储备充足，准备除冰车就位")

        # 降水+低温
        has_precip = any(p in wx_text for p in ["RA", "SN", "DZ", "FZRA", "FZDZ"])
        if has_precip and temp is not None and temp <= 5:
            advice.append("2. 【地面湿滑】降水+低温，地面湿滑，注意防滑措施")
            advice.append("   检查排水系统，防止积水结冰")

        # 大风
        if "大风" in factors_text or "阵风" in factors_text or (gust and gust > 30) or wind > 25:
            advice.append("3. 【大风警告】停止高空作业，固定地面设备和工具")
            if gust:
                advice.append(f"   阵风{gust}KT，注意登机梯、工作平台稳定性")
            advice.append("   检查系留和轮挡是否到位")

        # 低能见度
        if "低能见" in factors_text or "雾" in factors_text or "FG" in wx_text:
            vis = metar_data.get("visibility")
            if vis is not None and vis < 1:
                advice.append("4. 【低能见度】能见度<1km，车辆限速行驶，开启警示灯")
                advice.append("   暂停非必要的地面车辆调度")

        # 沙尘
        if "沙尘" in factors_text or "SS" in wx_text or "DS" in wx_text:
            advice.append("5. 【沙尘警告】停止一切户外作业，保护航空器部件免受沙尘侵害")
            advice.append("   覆盖发动机进气口和空速管")

        # 雷暴
        if "TS" in wx_text or "雷暴" in factors_text:
            advice.append("6. 【雷暴警告】停止一切户外作业，人员撤离到安全区域")
            advice.append("   确保航空器接地良好")

        # 高温
        if temp is not None and temp > 35:
            advice.append(f"7. 【高温】当前温度{temp}°C，注意人员防暑，航材存储温度限制")

        # 低风险情况
        if risk_level == "LOW" and not advice:
            advice.append("1. 户外作业条件良好")
            advice.append("2. 按常规程序执行维护作业")
            advice.append("3. 注意温度变化对航材存储的影响")

        if not advice:
            advice.append("当前作业条件正常，按常规程序执行。")

        return "\n".join(advice)

    def get_extra_fields(
        self,
        metar_data: Dict[str, Any],
        risk_factors: List[str],
        risk_level: str,
    ) -> Dict[str, Any]:
        """地勤机务额外字段：户外作业状态、设备限制、除冰需求"""
        factors_text = " ".join(risk_factors).lower()
        temp = metar_data.get("temperature")
        wind = metar_data.get("wind_speed", 0) or 0
        gust = metar_data.get("wind_gust")
        wx = [w.get("code", "") for w in metar_data.get("present_weather", [])]
        wx_text = " ".join(wx)

        # 户外作业状态
        if risk_level == "CRITICAL":
            outdoor_status = "禁止户外作业"
        elif risk_level == "HIGH":
            outdoor_status = "限制户外作业"
        elif risk_level == "MEDIUM":
            outdoor_status = "有条件户外作业"
        else:
            outdoor_status = "适宜户外作业"

        # 设备限制
        equipment_restrictions = []
        if gust and gust > 30 or wind > 25:
            equipment_restrictions.append("停止高空作业设备使用")
        if any(p in wx_text for p in ["RA", "SN", "DZ"]):
            equipment_restrictions.append("室外电器设备注意防水")
        if temp is not None and temp <= 0:
            equipment_restrictions.append("液态设备注意防冻")

        # 除冰需求
        deicing_needed = (
            "积冰" in factors_text
            or "结冰" in factors_text
            or "FZ" in wx_text
            or (temp is not None and temp <= 0 and any(p in wx_text for p in ["RA", "DZ", "FG"]))
        )

        return {
            "outdoor_status": outdoor_status,
            "equipment_restrictions": equipment_restrictions,
            "deicing_needed": deicing_needed,
        }
