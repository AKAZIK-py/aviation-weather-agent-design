"""
ForecasterReporter - 气象预报员视角的报告生成器

关注点：天气预报与趋势研判
- 允许：天气现象、趋势、气压系统、危险天气
- 过滤：进近标准、签派决策、除冰程序
"""
from typing import Dict, Any, List

from app.services.role_reporters.base import BaseReporter


class ForecasterReporter(BaseReporter):
    """气象预报员角色报告生成器"""

    ROLE = "forecaster"
    ROLE_CN = "气象预报员"

    # 允许的风险因素关键词
    ALLOWED_RISK_KEYWORDS = {
        "天气现象", "雷暴", "TS", "飑", "对流",
        "雾", "FG", "冻雾", "FZFG", "霜",
        "降水", "雨", "RA", "雪", "SN", "冰雹",
        "风", "阵风", "风切变", "WS",
        "气压", "趋势", "锋面", "低压", "高压",
        "能见度", "低能见", "云底高", "低云",
        "积冰", "颠簸", "沙尘",
        "SIGMET", "趋势预报",
    }

    # 过滤掉的关键词
    FILTERED_RISK_KEYWORDS = {
        "DH", "MDA", "决断高", "ILS", "CAT", "进近方式",
        "放行", "签派", "延误", "取消", "备降",
        "除冰程序", "除防冰", "化油器",
        "户外作业", "设备", "维护", "机务",
        "航材", "存储", "加油作业",
        "动态",
    }

    def generate_advice(
        self,
        metar_data: Dict[str, Any],
        risk_factors: List[str],
        risk_level: str,
    ) -> str:
        """生成预报员专属建议"""
        advice = []
        factors_text = " ".join(risk_factors).lower()
        temp = metar_data.get("temperature")
        dew = metar_data.get("dewpoint")
        wx = [w.get("code", "") for w in metar_data.get("present_weather", [])]
        wx_text = " ".join(wx)

        # 温度露点差分析
        if temp is not None and dew is not None:
            spread = temp - dew
            if spread <= 2:
                advice.append(f"1. 【湿度分析】温度露点差仅{spread}°C，雾或低云形成风险极高")
            elif spread <= 5:
                advice.append(f"1. 【湿度分析】温度露点差{spread}°C，需关注湿度变化趋势")

        # 雷暴
        if "TS" in wx_text or "雷暴" in factors_text:
            advice.append("2. 【对流天气】关注对流发展，建议发布SIGMET")
            advice.append("   预计雷暴活动将持续，关注移动方向和强度变化")

        # 低能见度/雾
        if "雾" in factors_text or "FG" in wx_text or "低能见" in factors_text:
            if "FZFG" in wx_text:
                advice.append("3. 【冻雾】冻雾条件下能见度极低，预计持续至温度回升")
            else:
                advice.append("3. 【雾/低能见度】关注雾的发展趋势，预计持续数小时")

        # 大风
        if "风" in factors_text and ("阵风" in factors_text or metar_data.get("wind_speed", 0) > 25):
            advice.append("4. 【大风】关注锋面过境，风向转变可能预示天气系统变化")

        # 积冰
        if "积冰" in factors_text:
            advice.append("5. 【积冰】温度处于积冰区间，关注积冰层高度和范围")

        # 气压分析
        altimeter = metar_data.get("altimeter")
        if altimeter is not None:
            if altimeter < 1000:
                advice.append(f"6. 【气压】当前气压{altimeter}hPa偏低，可能受低压系统影响")
            elif altimeter > 1030:
                advice.append(f"6. 【气压】当前气压{altimeter}hPa偏高，高压控制下天气稳定")

        # 低风险情况
        if risk_level == "LOW" and not advice:
            advice.append("1. 当前天气稳定，各要素无显著异常")
            advice.append("2. 关注午后对流发展（季节性因素）")
            advice.append("3. 温度露点差较大，短期内雾形成风险低")

        # 预报建议
        if risk_level in ("HIGH", "CRITICAL"):
            advice.append("")
            advice.append("【预报建议】")
            advice.append("• 考虑发布SIGMET或重要气象情报")
            advice.append("• 更新TAF趋势预报")
            advice.append("• 向相关用户发布预警")

        if not advice:
            advice.append("当前天气稳定，持续监控各要素变化。")

        return "\n".join(advice)

    def get_extra_fields(
        self,
        metar_data: Dict[str, Any],
        risk_factors: List[str],
        risk_level: str,
    ) -> Dict[str, Any]:
        """预报员额外字段：趋势评估、SIGMET建议"""
        factors_text = " ".join(risk_factors).lower()
        wx = [w.get("code", "") for w in metar_data.get("present_weather", [])]
        wx_text = " ".join(wx)

        # 趋势评估
        temp = metar_data.get("temperature")
        dew = metar_data.get("dewpoint")
        if temp is not None and dew is not None:
            spread = temp - dew
            if spread <= 2:
                trend = "能见度可能继续下降，雾的发展风险高"
            elif spread <= 5:
                trend = "天气可能恶化，需持续关注"
            else:
                trend = "天气相对稳定"
        else:
            trend = "数据不足，无法评估趋势"

        # SIGMET 建议
        sigmet_recommendation = None
        if "TS" in wx_text or "雷暴" in factors_text:
            sigmet_recommendation = "建议发布雷暴SIGMET"
        elif "积冰" in factors_text:
            sigmet_recommendation = "建议发布积冰SIGMET"
        elif "风切变" in factors_text:
            sigmet_recommendation = "建议发布低空风切变警告"

        return {
            "trend_assessment": trend,
            "sigmet_recommendation": sigmet_recommendation,
        }
