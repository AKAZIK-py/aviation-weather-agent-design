"""
风险评估服务
Risk Assessment Service (Layer 2: 风险诊断)
"""
from typing import List, Dict, Any
from app.models import ParsedMETAR, RiskAssessment, RiskLevel
from app.utils.rules_db import weatherRulesDB, get_risk_level


class RiskAssessor:
    """风险评估器"""
    
    def assess(self, parsed: ParsedMETAR) -> RiskAssessment:
        """执行风险评估"""
        score = 0
        warnings = []
        
        # 风险评分维度1: 风速评估
        if parsed.wind.speed:
            # 强风 (>=17m/s)
            if parsed.wind.speed >= weatherRulesDB["wind"]["strongWindThreshold"]:
                score += 40
                warnings.append(f"强风风速{parsed.wind.speed}m/s")
            
            # 阵风增量 (>=10m/s)
            if parsed.wind.gust and parsed.wind.gust - parsed.wind.speed >= weatherRulesDB["wind"]["gustDeltaThreshold"]:
                score += 20
                warnings.append(f"阵风{parsed.wind.gust}m/s")
        
        # 风险评分维度2: 能见度评估
        if parsed.visibility.value:
            # 临界能见度 (<400m)
            if parsed.visibility.value < weatherRulesDB["visibility"]["criticalThreshold"]:
                score += 100
                warnings.append(f"临界能见度{parsed.visibility.value}m")
            # 很低能见度 (<800m)
            elif parsed.visibility.value < weatherRulesDB["visibility"]["veryLowThreshold"]:
                score += 60
                warnings.append(f"很低能见度{parsed.visibility.value}m")
            # 低能见度 (<1500m)
            elif parsed.visibility.value < weatherRulesDB["visibility"]["lowThreshold"]:
                score += 40
                warnings.append(f"低能见度{parsed.visibility.value}m")
        
        # 风险评分维度3: 云层评估
        for cloud in parsed.clouds:
            # 危险云类型 (CB/TCU)
            if cloud.type in weatherRulesDB["cloud"]["dangerousTypes"]:
                score += 30
                warnings.append(f"危险云{cloud.type}")
            
            # 低云 (<300m)
            if cloud.height < weatherRulesDB["cloud"]["lowCloudThreshold"]:
                score += 20
                warnings.append(f"低云高{cloud.height}m")
        
        # 风险评分维度4: 天气现象评估
        for weather in parsed.weather:
            # 雷暴相关
            if weather.code in weatherRulesDB["weather"]["thunderstormCodes"]:
                if weather.intensity == "heavy":
                    score += 50
                else:
                    score += 40
                warnings.append(f"雷暴{weather.code}")
            
            # 严重天气
            elif weather.code in weatherRulesDB["weather"]["severeCodes"]:
                score += 30
                warnings.append(f"严重天气{weather.code}")
            
            # 中等天气
            elif weather.code in weatherRulesDB["weather"]["moderateCodes"]:
                score += 10
                warnings.append(f"降水{weather.code}")
        
        # 确定风险等级
        risk_config = get_risk_level(score)
        level = RiskLevel[risk_config["level"]]
        
        return RiskAssessment(
            level=level,
            score=score,
            warnings=warnings
        )


# 全局评估器实例
risk_assessor = RiskAssessor()
