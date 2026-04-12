"""
航空气象规则数据库
Weather Rules Database for Risk Assessment
"""
from typing import Dict, Any

weatherRulesDB = {
    "wind": {
        "strongWindThreshold": 17,     # 强风阈值 m/s
        "gustDeltaThreshold": 10,       # 阵风差阈值 m/s
        "crosswindThreshold": 15        # 侧风阈值 m/s
    },
    "visibility": {
        "lowThreshold": 1500,           # 低能见度阈值 m
        "veryLowThreshold": 800,        # 很低能见度阈值 m
        "criticalThreshold": 400        # 临界能见度阈值 m
    },
    "cloud": {
        "lowCloudThreshold": 300,       # 低云阈值 300m = 1000ft
        "criticalHeight": 150,          # 临界云高 150m
        "dangerousTypes": ["CB", "TCU"] # 危险云类型
    },
    "weather": {
        "thunderstormCodes": ["TS", "TSRA", "TSGR", "TSGS"],
        "severeCodes": ["FG", "HZ", "SA", "DU", "PO", "SQ", "FC"],
        "moderateCodes": ["RA", "SN", "SG", "IC", "PL", "GR", "GS", "UP"]
    },
    "riskLevels": {
        "LOW": {
            "scoreRange": [0, 29],
            "description": "天气条件良好，适宜飞行作业",
            "action": "正常签派放行",
            "color": "#10B981"
        },
        "MEDIUM": {
            "scoreRange": [30, 59],
            "description": "存在一定天气风险，需加强监控",
            "action": "签派放行但需提醒机组注意天气变化",
            "color": "#F59E0B"
        },
        "HIGH": {
            "scoreRange": [60, 99],
            "description": "天气条件较差，存在显著风险",
            "action": "建议延迟起飞或备降，需管理层决策",
            "color": "#EF4444"
        },
        "CRITICAL": {
            "scoreRange": [100, 999],
            "description": "严重天气条件，禁止飞行作业",
            "action": "立即取消航班，启动应急预案",
            "color": "#991B1B"
        }
    }
}


def get_risk_level(score: int) -> Dict[str, Any]:
    """根据分数获取风险等级配置"""
    for level, config in weatherRulesDB["riskLevels"].items():
        if config["scoreRange"][0] <= score <= config["scoreRange"][1]:
            return {"level": level, **config}
    return {"level": "LOW", **weatherRulesDB["riskLevels"]["LOW"]}
