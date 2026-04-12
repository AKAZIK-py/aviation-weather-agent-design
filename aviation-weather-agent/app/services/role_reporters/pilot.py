"""
PilotReporter - 飞行员视角的报告生成器

关注点：飞行安全与起降决策
- 允许：能见度、云底高、风/阵风、积冰、风切变、跑道污染、DH/MDA
- 过滤：[动态]前缀的技术细节、气压异常、趋势、签派相关
"""
from typing import Dict, Any, List

from app.services.role_reporters.base import BaseReporter
from app.utils.approach import format_decision_info
from app.utils.visibility import format_visibility_range


class PilotReporter(BaseReporter):
    """飞行员角色报告生成器"""

    ROLE = "pilot"
    ROLE_CN = "飞行员"

    # 允许的风险因素关键词（白名单）
    ALLOWED_RISK_KEYWORDS = {
        "能见度", "云底高", "风", "阵风", "侧风", "风切变",
        "积冰", "结冰", "冻雾", "冻雨", "FZ",
        "跑道", "污染", "积水", "积冰",
        "雷暴", "TS", "飑", "下击暴流",
        "低能见", "低云", "雾", "FG",
        "降雪", "SN", "冰雹",
        "沙尘", "SS", "DS",
        "DH", "MDA", "决断高", "进近", "ILS",
    }

    # 过滤掉的关键词（不属于飞行员核心关注）
    FILTERED_RISK_KEYWORDS = {
        "气压", "趋势", "签派", "放行", "延误", "取消",
        "预报", "TAF", "SIGMET", "对流",
        "户外作业", "设备", "维护", "机务",
        "航材", "存储", "加油作业", "除防冰程序",
        "动态",
    }

    def generate_advice(
        self,
        metar_data: Dict[str, Any],
        risk_factors: List[str],
        risk_level: str,
    ) -> str:
        """生成飞行员专属建议"""
        advice = []
        factors_text = " ".join(risk_factors).lower()
        vis = metar_data.get("visibility")
        temp = metar_data.get("temperature")
        wind = metar_data.get("wind_speed", 0) or 0
        gust = metar_data.get("wind_gust")
        wx = [w.get("code", "") for w in metar_data.get("present_weather", [])]
        wx_text = " ".join(wx)

        # 积冰相关
        if "积冰" in factors_text or "结冰" in factors_text or "FZ" in wx_text:
            advice.append("1. 【积冰应对】立即检查机翼/发动机积冰情况，执行除冰程序后方可起飞")
            if temp is not None and temp <= 0:
                advice.append(f"   当前温度 {temp}°C 处于积冰区间（0~-15°C），化油器积冰风险高")

        # 低能见度
        if vis is not None and vis < 3:
            if vis < 1:
                advice.append(f"2. 【能见度】能见度<1km不适飞，建议等待好转或选择备降场")
            else:
                vis_range = format_visibility_range(vis)
                advice.append(f"2. 【能见度】能见度{vis_range}，需执行ILS精密进近，准备复飞预案")

        # 大风/阵风
        if "阵风" in factors_text or (gust and gust > 30):
            advice.append(f"3. 【阵风应对】阵风{gust or 'N/A'}KT，着陆时注意侧风修正，准备好复飞")
        elif wind > 20:
            advice.append(f"3. 【大风应对】持续风速{wind}KT，注意风切变和颠簸，保持安全速度")

        # 雷暴
        if "TS" in wx_text or "雷暴" in factors_text:
            advice.append("4. 【雷暴应对】雷暴区域禁止进入，保持至少10nm绕飞距离，关注下击暴流")

        # 风切变
        if "风切变" in factors_text or "WS" in wx_text:
            advice.append("5. 【风切变】已检测到风切变报告，进近时保持复飞构型，随时准备推力响应")

        # 冻雾/雪
        if "FZFG" in wx_text:
            advice.append("6. 【冻雾】跑道视程可能急剧下降，建议延迟起飞至条件改善")
        if "SN" in wx_text or "雪" in factors_text:
            advice.append("6. 【降雪】检查跑道摩擦系数，必要时请求跑道状态评估")

        # 云底高
        if "云底高" in factors_text or "低云" in factors_text:
            cloud_layers = metar_data.get("cloud_layers", [])
            ceiling_types = {"BKN", "OVC", "VV"}
            ceilings = [l["height_feet"] for l in cloud_layers if l.get("type") in ceiling_types]
            if ceilings:
                lowest = min(ceilings)
                if lowest < 500:
                    advice.append(f"7. 【云底高】云底仅{lowest}ft，仅ILS CAT II/III可行，目视进近不可行")
                elif lowest < 1000:
                    advice.append(f"7. 【云底高】云底{lowest}ft，需执行ILS进近，备降场天气必须达标")

        # 跑道污染
        if "跑道污染" in factors_text or "跑道" in factors_text:
            advice.append("8. 【跑道状态】当前跑道可能结冰/积水，着陆刹车距离增加30%~50%，考虑备降")

        # 低风险情况
        if risk_level == "LOW" and not advice:
            if vis is not None and vis >= 5:
                advice.append("1. 当前能见度良好，VFR飞行条件满足")
            if wind < 15 and not gust:
                advice.append("2. 风速适中，侧风影响可控")
            if temp is not None and (temp > 5 or temp < -15):
                advice.append("3. 温度不在积冰区间，积冰风险低")
            advice.append("4. 建议持续关注天气变化趋势")

        # 高风险行动项
        if risk_level in ("HIGH", "CRITICAL"):
            advice.append("")
            advice.append("【飞行员行动项】")
            advice.append("• 检查备降场天气是否达标")
            advice.append("• 确认油量满足备降要求")
            advice.append("• 与签派确认放行状态")

        if not advice:
            advice.append("请根据实际情况谨慎决策，必要时咨询签派和气象人员。")

        return "\n".join(advice)

    def get_extra_fields(
        self,
        metar_data: Dict[str, Any],
        risk_factors: List[str],
        risk_level: str,
    ) -> Dict[str, Any]:
        """飞行员额外字段：DH/MDA进近标准表"""
        cloud_layers = metar_data.get("cloud_layers", [])
        ceiling_types = {"BKN", "OVC", "VV"}
        ceilings = [l["height_feet"] for l in cloud_layers if l.get("type") in ceiling_types]
        lowest_cloud = min(ceilings) if ceilings else None

        dh_info = format_decision_info(cloud_ceiling_ft=lowest_cloud)

        return {
            "dh_mda_info": dh_info,
        }
