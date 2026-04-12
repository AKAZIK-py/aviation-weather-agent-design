"""
风险评估节点 - assess_risk_node
职责：根据METAR数据评估航空风险等级
使用规则引擎+LLM辅助评估
"""
from typing import Dict, Any, List, Tuple
from langchain_core.runnables import RunnableConfig

from app.core.workflow_state import WorkflowState
from app.utils.visibility import format_visibility_range
from app.core.config import load_yaml_config

# 动态风险评估系统 (可选集成，失败时回退到原有逻辑)
try:
    from app.utils.dynamic_risk_engine import DynamicRiskEngine
    from app.utils.dynamic_weights import get_weight_for_phenomena
    from app.utils.ceiling_zones import classify as classify_ceiling
    from app.utils.wind_assessment import assess_wind
    _DYNAMIC_ENGINE_AVAILABLE = True
except ImportError:
    _DYNAMIC_ENGINE_AVAILABLE = False


class RiskAssessor:
    """风险评估器"""
    
    def __init__(self, config_dict: Dict[str, Any] = None):
        """
        初始化风险评估器
        
        Args:
            config_dict: 配置字典，可从 YAML 加载
        """
        self.config = config_dict or {}
        
        # 风险因素阈值配置（默认值）
        self.RISK_THRESHOLDS = self._load_thresholds_from_config()
    
    def _load_thresholds_from_config(self) -> Dict[str, Any]:
        """从配置加载阈值，如果配置中没有则使用默认值"""
        # 默认阈值
        default_thresholds = {
            "wind_speed": {
                "LOW": 15,
                "MEDIUM": 25,
                "HIGH": 35,
                "CRITICAL": 35,
            },
            "wind_gust": {
                "LOW": 20,
                "MEDIUM": 30,
                "HIGH": 40,
                "CRITICAL": 40,
            },
            "visibility": {
                "LOW": 5.0,       # ≥5km: 正常
                "MEDIUM": 3.0,    # 3-5km: 需关注
                "HIGH": 1.0,      # 1-3km: 高风险
                "CRITICAL": 1.0,  # <1km: 不适飞
            },
            "cloud_height": {
                "LOW": 3000,
                "MEDIUM": 1000,
                "HIGH": 500,
                "CRITICAL": 500,
            },
        }
        
        # 从配置中读取 risk_thresholds 部分
        config_thresholds = self.config.get("risk_thresholds", {})
        
        # 更新默认阈值
        if "visibility" in config_thresholds:
            vis_config = config_thresholds["visibility"]
            default_thresholds["visibility"]["CRITICAL"] = vis_config.get("critical_km", 1.0)
            default_thresholds["visibility"]["HIGH"] = vis_config.get("high_km", 3.0)
            default_thresholds["visibility"]["MEDIUM"] = vis_config.get("medium_km", 5.0)
        
        if "wind" in config_thresholds:
            wind_config = config_thresholds["wind"]
            default_thresholds["wind_speed"]["CRITICAL"] = wind_config.get("critical_kt", 35)
            default_thresholds["wind_speed"]["HIGH"] = wind_config.get("high_kt", 25)
            default_thresholds["wind_speed"]["MEDIUM"] = wind_config.get("medium_kt", 15)
        
        return default_thresholds
    
    # 高危天气现象
    HAZARDOUS_WEATHER = {
        "CRITICAL": ["TS", "TSRA", "+TSRA", "FC", "TORNADO", "GR"],
        "HIGH": ["+RA", "+SN", "FZFG", "FZRA", "SS", "DS", "VA"],
        "MEDIUM": ["RA", "SN", "FG", "BR", "HZ", "DU", "SA"],
    }
    
    # 角色相关风险权重（四角色体系）
    ROLE_RISK_WEIGHTS = {
        "pilot": {
            "wind": 1.4,      # 飞行员高度关注风对起降的影响
            "visibility": 1.3, # 能见度直接影响决断高
            "weather": 1.3,    # 天气现象影响飞行安全
            "cloud": 1.2       # 云底高影响进近方式
        },
        "dispatcher": {
            "wind": 1.1,      # 签派关注运行效率
            "visibility": 1.3, # 能见度影响航班正常性
            "weather": 1.3,    # 天气影响放行决策
            "cloud": 1.1       # 云层影响备降决策
        },
        "forecaster": {
            "wind": 1.0,      # 预报员均匀关注各项指标
            "visibility": 1.0,
            "weather": 1.0,
            "cloud": 1.0
        },
        "ground_crew": {
            "wind": 1.5,      # 地勤作业受大风影响最大
            "visibility": 1.0, # 能见度影响相对较小
            "weather": 1.2,    # 天气现象影响户外作业
            "cloud": 0.7       # 云层对地面作业影响最小
        },
    }
    
    # 角色中文名映射
    ROLE_NAMES_CN = {
        "pilot": "飞行员",
        "dispatcher": "签派管制",
        "forecaster": "预报员",
        "ground_crew": "地勤",
    }
    
    # 机场特定风险规则
    AIRPORT_SPECIFIC_RISKS = {
        "ZSPD": {
            "name": "上海浦东",
            "risks": ["海风效应，侧风风险"],
            "wind_direction_range": (90, 180),  # 东南风范围
            "wind_speed_threshold": 15,
        },
        "ZLLL": {
            "name": "兰州中川",
            "risks": ["高度修正，高海拔机场"],
            "elevation_ft": 6388,
            "visibility_adjustment": 0.9,  # 能见度修正系数
        },
        "ZUUU": {
            "name": "成都双流",
            "risks": ["盆地低能见度"],
            "fog_season_months": [10, 11, 12, 1, 2, 3],
            "visibility_threshold": 3.0,
        },
    }
    
    def assess(
        self, 
        metar_data: Dict[str, Any], 
        role: str = "dispatcher"
    ) -> Tuple[str, List[str], str]:
        """评估风险等级"""
        risk_factors = []
        risk_scores = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}
        weights = self.ROLE_RISK_WEIGHTS.get(role, self.ROLE_RISK_WEIGHTS["dispatcher"])
        
        # 1. 风速评估
        wind_speed = metar_data.get("wind_speed", 0)
        wind_gust = metar_data.get("wind_gust")
        wind_direction = metar_data.get("wind_direction")
        
        # 获取温度和露点
        temperature = metar_data.get("temperature")
        dewpoint = metar_data.get("dewpoint")
        
        if wind_speed:
            wind_risk = self._assess_wind(wind_speed, wind_gust)
            risk_scores[wind_risk] += weights["wind"]
            if wind_risk != "LOW":
                factor = f"风速{wind_speed}KT" + (f"，阵风{wind_gust}KT" if wind_gust else "")
                risk_factors.append(factor)
        
        # 2. 能见度评估
        visibility = metar_data.get("visibility")
        if visibility is not None:
            vis_risk = self._assess_visibility(visibility)
            risk_scores[vis_risk] += weights["visibility"]
            if vis_risk != "LOW":
                vis_range = format_visibility_range(visibility)
                risk_factors.append(f"能见度{vis_range}")
        
        # 3. 云层评估（仅看 ceiling: BKN/OVC/VV）
        cloud_layers = metar_data.get("cloud_layers", [])
        ceiling_types = {"BKN", "OVC", "VV"}
        ceiling_heights = [
            layer["height_feet"] for layer in cloud_layers
            if layer.get("type") in ceiling_types
        ]
        if ceiling_heights:
            lowest_ceiling = min(ceiling_heights)
            cloud_risk = self._assess_cloud(lowest_ceiling)
            risk_scores[cloud_risk] += weights["cloud"]
            if cloud_risk != "LOW":
                risk_factors.append(f"云底高{lowest_ceiling}ft")
        
        # 4. 天气现象评估
        weather = metar_data.get("present_weather", [])
        if weather:
            wx_risk = self._assess_weather(weather)
            risk_scores[wx_risk] += weights["weather"]
            if wx_risk != "LOW":
                wx_desc = ", ".join([w["description"] for w in weather])
                risk_factors.append(f"天气现象: {wx_desc}")
        
        # 5. 风切变评估（安全边界D3）
        wind_shear = metar_data.get("wind_shear")
        if wind_shear:
            risk_scores["HIGH"] += 1.5
            risk_factors.append(f"风切变: {wind_shear}")
        
        # 6. 低能见度安全边界（即使无天气代码，低能见度本身也是危险）
        if visibility is not None and visibility < 1.6:
            risk_scores["HIGH"] += 1.0
            if f"能见度{format_visibility_range(visibility)}" not in " ".join(risk_factors):
                risk_factors.append(f"低能见度: {format_visibility_range(visibility)}")
        
        # 7. 低云底高安全边界
        if ceiling_heights and min(ceiling_heights) < 500:
            risk_scores["HIGH"] += 1.0
            if not any("云底高" in f for f in risk_factors):
                risk_factors.append(f"低云底高: {min(ceiling_heights)}ft")
        
        # 8. RVR（跑道视程）评估
        rvr_data = metar_data.get("rvr", [])
        if rvr_data:
            rvr_risk = self._assess_rvr(rvr_data)
            if rvr_risk != "LOW":
                risk_scores[rvr_risk] += 1.5
                risk_factors.append(f"RVR低能见度")
        
        # 9. 叠加风险规则
        flight_rules = metar_data.get("flight_rules")
        if flight_rules:
            combined_risk_factors = self._assess_combined_risks(
                flight_rules, wind_speed, wind_gust, visibility, 
                temperature, dewpoint, ceiling_heights
            )
            for factor, risk_level in combined_risk_factors:
                risk_scores[risk_level] += 1.0
                risk_factors.append(factor)
        
        # 10. 积冰条件检测 (icing_conditions)
        if temperature is not None and dewpoint is not None:
            spread = temperature - dewpoint
            if -15 <= temperature <= 0 and spread < 3:
                risk_scores["HIGH"] += 1.5
                risk_factors.append(f"积冰条件: 温度{temperature}°C, 露点差{spread}°C")
        
        # 11. 低空颠簸检测 (low_level_turbulence)
        for layer in cloud_layers:
            tower_type = layer.get("tower_type")
            height = layer.get("height_feet", 0)
            if tower_type in ("CB", "TCU") and height < 5000:
                risk_scores["HIGH"] += 1.5
                risk_factors.append(f"低空颠簸: {tower_type}云底高{height}ft")
                break  # 只报告一次
        
        # 12. 跑道污染检测 (runway_contamination)
        icing_weather_codes = {"SN", "+SN", "-SN", "RA", "+RA", "-RA", "FZFG", "FZRA", "+FZRA", "-FZRA", "FZDZ", "+FZDZ", "-FZDZ"}
        if weather and temperature is not None and temperature <= 3:
            for wx in weather:
                wx_code = wx.get("code", "")
                if wx_code in icing_weather_codes or any(code in wx_code for code in icing_weather_codes):
                    risk_scores["CRITICAL"] += 1.0
                    risk_factors.append(f"跑道污染风险: {wx_code} + 温度{temperature}°C")
                    break  # 只报告一次
        
        # 13. VV 极端低值 (extreme_vertical_visibility)
        vv = metar_data.get("vertical_visibility")
        if vv is not None and vv < 100:
            risk_scores["CRITICAL"] += 1.0
            risk_factors.append(f"垂直能见度极低: {vv}ft")
        
        # 14. 气压异常 (pressure_anomaly)
        altimeter = metar_data.get("altimeter")
        if altimeter is not None:
            if altimeter < 980 or altimeter > 1050:
                risk_scores["MEDIUM"] += 1.0
                risk_factors.append(f"气压异常: {altimeter}hPa")
        
        # 15. 趋势恶化检测 (tempo_deterioration)
        if metar_data.get("has_trend", False):
            trend_type = metar_data.get("trend_type")
            if trend_type in ("BECMG", "TEMPO"):
                risk_scores["MEDIUM"] += 0.5
                risk_factors.append(f"趋势预报: 检测到{trend_type}组，请关注后续变化")
        
        # 16. 机场特定风险评估
        icao_code = metar_data.get("icao_code", "")
        if icao_code in self.AIRPORT_SPECIFIC_RISKS:
            airport_risk_factors = self._assess_airport_specific_risks(
                icao_code, metar_data, wind_direction, wind_speed, visibility
            )
            for factor, risk_level in airport_risk_factors:
                risk_scores[risk_level] += 1.0
                risk_factors.append(factor)

        # ===== 17. 动态风险引擎（增强评估） =====
        dynamic_report = None
        if _DYNAMIC_ENGINE_AVAILABLE:
            try:
                engine = DynamicRiskEngine()
                dynamic_report = engine.calculate(metar_data)

                # 将区间诊断信息加入 risk_factors
                if dynamic_report.ceiling_zone and dynamic_report.ceiling_zone.zone >= 3:
                    risk_factors.append(
                        f"[动态] 云底高: {dynamic_report.ceiling_zone.description}"
                    )
                if dynamic_report.vis_zone and dynamic_report.vis_zone.zone >= 3:
                    risk_factors.append(
                        f"[动态] 能见度: {dynamic_report.vis_zone.description}"
                    )

                # 缓冲区告警
                if dynamic_report.ceiling_zone and dynamic_report.ceiling_zone.in_buffer:
                    risk_factors.append(
                        f"[动态] 云底高缓冲区: {dynamic_report.ceiling_zone.description}"
                    )
                if dynamic_report.vis_zone and dynamic_report.vis_zone.in_buffer:
                    risk_factors.append(
                        f"[动态] 能见度缓冲区: {dynamic_report.vis_zone.description}"
                    )

                # 风况详情
                if dynamic_report.wind_assessment:
                    for wf in dynamic_report.wind_assessment.risk_factors:
                        if wf not in risk_factors:
                            risk_factors.append(f"[动态风况] {wf}")

                # 动态权重信息
                if dynamic_report.weights:
                    w = dynamic_report.weights
                    dominant = max(w, key=w.get)
                    risk_factors.append(
                        f"[动态权重] 主导维度: {dominant} ({w[dominant]:.2f})"
                    )

                # CRITICAL 覆盖
                if dynamic_report.override_reasons:
                    for reason in dynamic_report.override_reasons:
                        risk_scores["CRITICAL"] += 1.0
                        risk_factors.append(f"[CRITICAL覆盖] {reason}")

                # 动态分数影响风险等级
                if dynamic_report.base_score >= 80:
                    risk_scores["CRITICAL"] += 1.0
                elif dynamic_report.base_score >= 55:
                    risk_scores["HIGH"] += 1.0
                elif dynamic_report.base_score >= 30:
                    risk_scores["MEDIUM"] += 0.5

                risk_factors.append(
                    f"[动态评分] 综合={dynamic_report.base_score:.1f}, "
                    f"VIS={dynamic_report.vis_score:.1f}, "
                    f"CLG={dynamic_report.ceiling_score:.1f}, "
                    f"WIND={dynamic_report.wind_score:.1f}, "
                    f"TEMP={dynamic_report.temp_score:.1f}"
                )

            except Exception:
                # 动态引擎失败不影响原有逻辑
                pass

        # 确定最终风险等级
        if risk_scores["CRITICAL"] >= 1:
            final_risk = "CRITICAL"
        elif risk_scores["HIGH"] >= 2:
            final_risk = "HIGH"
        elif risk_scores["HIGH"] >= 1 or risk_scores["MEDIUM"] >= 2:
            final_risk = "MEDIUM"
        elif risk_scores["MEDIUM"] >= 1:
            final_risk = "MEDIUM"
        else:
            final_risk = "LOW"
        
        # 生成评估理由
        role_cn = self.ROLE_NAMES_CN.get(role, role)
        reasoning = f"{role_cn}视角下的风险评估："
        if risk_factors:
            reasoning += "发现" + "、".join(risk_factors)
        else:
            reasoning += "各项指标均在正常范围内"
        
        return final_risk, risk_factors, reasoning
    
    def _assess_wind(self, speed: int, gust: int = None) -> str:
        """评估风风险"""
        max_wind = max(speed, gust or 0)
        thresholds = self.RISK_THRESHOLDS["wind_speed"]
        
        if max_wind > thresholds["CRITICAL"]:
            return "CRITICAL"
        elif max_wind > thresholds["HIGH"]:
            return "HIGH"
        elif max_wind > thresholds["MEDIUM"]:
            return "MEDIUM"
        return "LOW"
    
    def _assess_visibility(self, vis_km: float) -> str:
        """
        评估能见度风险
        
        ICAO 标准 + 适飞标准：
        - < 1km: CRITICAL（不适飞）
        - 1-3km: HIGH
        - 3-5km: MEDIUM
        - ≥ 5km: LOW
        """
        if vis_km < 1.0:
            return "CRITICAL"
        elif vis_km < 3.0:
            return "HIGH"
        elif vis_km < 5.0:
            return "MEDIUM"
        return "LOW"
    
    def _assess_cloud(self, height_ft: int) -> str:
        """评估云层风险"""
        if height_ft < self.RISK_THRESHOLDS["cloud_height"]["CRITICAL"]:
            return "CRITICAL"
        elif height_ft < self.RISK_THRESHOLDS["cloud_height"]["HIGH"]:
            return "HIGH"
        elif height_ft < self.RISK_THRESHOLDS["cloud_height"]["MEDIUM"]:
            return "MEDIUM"
        return "LOW"
    
    def _assess_weather(self, weather: List[Dict]) -> str:
        """评估天气现象风险"""
        codes = [w["code"] for w in weather]
        
        for code in codes:
            if any(hz in code for hz in self.HAZARDOUS_WEATHER["CRITICAL"]):
                return "CRITICAL"
        
        for code in codes:
            if any(hz in code for hz in self.HAZARDOUS_WEATHER["HIGH"]):
                return "HIGH"
        
        for code in codes:
            if any(hz in code for hz in self.HAZARDOUS_WEATHER["MEDIUM"]):
                return "MEDIUM"
        
        return "LOW"
    
    def _assess_rvr(self, rvr_data: List[Dict]) -> str:
        """
        评估跑道视程风险
        
        RVR < 550m → HIGH 风险
        """
        for rvr in rvr_data:
            min_vis = rvr.get("visibility_min")
            max_vis = rvr.get("visibility_max")
            
            # 如果有变化范围，取较差值
            if min_vis is not None and max_vis is not None:
                vis_value = min(min_vis, max_vis)
            elif min_vis is not None:
                vis_value = min_vis
            elif max_vis is not None:
                vis_value = max_vis
            else:
                continue
            
            # RVR < 550m → HIGH
            if vis_value < 550:
                return "HIGH"
        
        return "LOW"
    
    def _assess_combined_risks(self, flight_rules: str, wind_speed: int, wind_gust: int,
                              visibility: float, temperature: int, dewpoint: int,
                              ceiling_heights: List[int]) -> List[Tuple[str, str]]:
        """
        评估叠加风险规则
        
        规则：
        - IFR + wind > 15kt → MEDIUM
        - IFR + temp < 0 AND dewpoint_diff < 3 → HIGH (积冰条件)
        - VIS 1-3km + ceiling < 1000ft → HIGH
        - 多个 MEDIUM 因素 ≥ 3 → 升级为 HIGH
        """
        factors = []
        medium_count = 0
        
        # IFR + wind > 15kt → MEDIUM
        if flight_rules == "IFR" and wind_speed and wind_speed > 15:
            factors.append(("IFR+大风", "MEDIUM"))
            medium_count += 1
        
        # IFR + temp < 0 AND dewpoint_diff < 3 → HIGH (积冰条件)
        if flight_rules == "IFR" and temperature is not None and dewpoint is not None:
            if temperature < 0 and (temperature - dewpoint) < 3:
                factors.append(("IFR+积冰条件", "HIGH"))
        
        # VIS 1-3km + ceiling < 1000ft → HIGH
        if visibility is not None and 1.0 <= visibility <= 3.0:
            if ceiling_heights and min(ceiling_heights) < 1000:
                factors.append(("低能见度+低云", "HIGH"))
        
        # 多个 MEDIUM 因素 ≥ 3 → 升级为 HIGH
        # 注意：这里只计算当前叠加规则产生的 MEDIUM 因素
        # 实际应用中可能需要结合其他 MEDIUM 因素
        if medium_count >= 3:
            factors.append(("多重中等风险", "HIGH"))
        
        return factors
    
    def _assess_airport_specific_risks(self, icao_code: str, metar_data: Dict[str, Any],
                                      wind_direction: int, wind_speed: int,
                                      visibility: float) -> List[Tuple[str, str]]:
        """
        评估机场特定风险
        """
        factors = []
        airport_config = self.AIRPORT_SPECIFIC_RISKS.get(icao_code, {})
        
        if not airport_config:
            return factors
        
        airport_name = airport_config.get("name", icao_code)
        
        # ZSPD: 海风效应，侧风风险
        if icao_code == "ZSPD":
            wind_dir_range = airport_config.get("wind_direction_range", (90, 180))
            wind_threshold = airport_config.get("wind_speed_threshold", 15)
            
            if wind_direction and wind_speed:
                # 检查是否在东南风范围且风速超过阈值
                if wind_dir_range[0] <= wind_direction <= wind_dir_range[1] and wind_speed > wind_threshold:
                    factors.append((f"{airport_name}海风侧风", "MEDIUM"))
        
        # ZLLL: 高度修正
        elif icao_code == "ZLLL":
            elevation_ft = airport_config.get("elevation_ft", 0)
            if elevation_ft > 5000:  # 高海拔机场
                # 高海拔机场能见度可能有偏差
                if visibility is not None and visibility < 5.0:
                    factors.append((f"{airport_name}高海拔能见度修正", "MEDIUM"))
        
        # ZUUU: 盆地低能见度
        elif icao_code == "ZUUU":
            fog_months = airport_config.get("fog_season_months", [])
            current_month = 1  # 默认值，实际应从观测时间获取
            
            # 如果当前月份在雾季，且能见度较低
            if current_month in fog_months and visibility is not None:
                vis_threshold = airport_config.get("visibility_threshold", 3.0)
                if visibility < vis_threshold:
                    factors.append((f"{airport_name}盆地雾季低能见度", "HIGH"))
        
        return factors


async def assess_risk_node(
    state: WorkflowState, 
    config: RunnableConfig
) -> Dict[str, Any]:
    """风险评估节点"""
    # 加载 YAML 配置
    yaml_config = load_yaml_config()
    assessor = RiskAssessor(yaml_config)
    
    metar_data = state.get("metar_parsed", {})
    role = state.get("detected_role", "dispatcher")
    
    risk_level, risk_factors, reasoning = assessor.assess(metar_data, role)
    
    updates = {
        "risk_level": risk_level,
        "risk_factors": risk_factors,
        "risk_reasoning": reasoning,
        "current_node": "assess_risk_node",
    }
    
    updates["reasoning_trace"] = [
        f"[assess_risk_node] 风险等级: {risk_level}，因素: {', '.join(risk_factors) if risk_factors else '无'}"
    ]
    
    return updates
