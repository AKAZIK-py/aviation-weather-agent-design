#!/usr/bin/env python3
"""
METAR测试场景生成器
用于航空气象Agent PE评测
"""

import json
from pathlib import Path

# 20个METAR测试场景
TEST_SCENARIOS = [
    # === 低能见度场景 (4个) ===
    {
        "id": "LOWVIS_001",
        "category": "低能见度",
        "severity": "CRITICAL",
        "metar_raw": "ZBAA 110800Z 00000KT 0050 R36L/0400V0600N FG VV001 02/01 Q1023 NOSIG",
        "airport": "ZBAA 北京首都",
        "description": "大雾LIFR条件，能见度50米",
        "expected": {
            "flight_rules": "LIFR",
            "visibility_m": 50,
            "weather": ["FG"],
            "risk_level": "CRITICAL",
            "key_risks": ["极低能见度", "大雾"]
        }
    },
    {
        "id": "LOWVIS_002",
        "category": "低能见度",
        "severity": "HIGH",
        "metar_raw": "ZSPD 110900Z 24005MPS 3000 BR BKN004 08/07 Q1015",
        "airport": "ZSPD 上海浦东",
        "description": "薄雾MVFR条件，能见度3000米",
        "expected": {
            "flight_rules": "MVFR",
            "visibility_m": 3000,
            "weather": ["BR"],
            "risk_level": "HIGH"
        }
    },
    {
        "id": "LOWVIS_003",
        "category": "低能见度",
        "severity": "HIGH",
        "metar_raw": "ZLXN 111000Z 32006MPS 0800 SA DSCT FEW030 25/M02 Q1008",
        "airport": "ZLXN 兰州中川",
        "description": "沙尘暴，能见度800米",
        "expected": {
            "flight_rules": "IFR",
            "visibility_m": 800,
            "weather": ["SA", "DSCT"],
            "risk_level": "HIGH"
        }
    },
    {
        "id": "LOWVIS_004",
        "category": "低能见度",
        "severity": "MEDIUM",
        "metar_raw": "ZGGG 111100Z 18008KT 1500 RA BR BKN008 OVC015 15/14 Q1012",
        "airport": "ZGGG 广州白云",
        "description": "降雨伴薄雾",
        "expected": {
            "flight_rules": "IFR",
            "visibility_m": 1500,
            "weather": ["RA", "BR"],
            "risk_level": "MEDIUM"
        }
    },
    
    # === 强风场景 (4个) ===
    {
        "id": "WIND_001",
        "category": "强风",
        "severity": "CRITICAL",
        "metar_raw": "ZWWW 111200Z 27035G50KT 3000 DS BKN030 28/M05 Q1006",
        "airport": "ZWWW 乌鲁木齐",
        "description": "强侧风35节阵风50节",
        "expected": {
            "flight_rules": "IFR",
            "wind_speed_kt": 35,
            "wind_gust_kt": 50,
            "weather": ["DS"],
            "risk_level": "CRITICAL"
        }
    },
    {
        "id": "WIND_002",
        "category": "强风",
        "severity": "HIGH",
        "metar_raw": "ZSAM 111300Z 32028G38KT 9999 SCT040 12/M03 Q1018 WS R23",
        "airport": "ZSAM 厦门高崎",
        "description": "强风伴风切变",
        "expected": {
            "flight_rules": "VFR",
            "wind_speed_kt": 28,
            "wind_gust_kt": 38,
            "wind_shear": True,
            "risk_level": "HIGH"
        }
    },
    {
        "id": "WIND_003",
        "category": "强风",
        "severity": "HIGH",
        "metar_raw": "ZYTX 111400Z 06045G58KT 5000 SHRA BKN025 08/05 Q0998",
        "airport": "ZYTX 沈阳桃仙",
        "description": "台风外围强风",
        "expected": {
            "flight_rules": "MVFR",
            "wind_speed_kt": 45,
            "wind_gust_kt": 58,
            "weather": ["SHRA"],
            "risk_level": "HIGH"
        }
    },
    {
        "id": "WIND_004",
        "category": "强风",
        "severity": "MEDIUM",
        "metar_raw": "ZJHK 111500Z 20022G32KT CAVOK 32/25 Q1008",
        "airport": "ZJHK 海口美兰",
        "description": "季风强风",
        "expected": {
            "flight_rules": "VFR",
            "wind_speed_kt": 22,
            "wind_gust_kt": 32,
            "risk_level": "MEDIUM"
        }
    },
    
    # === 雷暴场景 (4个) ===
    {
        "id": "TSTORM_001",
        "category": "雷暴",
        "severity": "CRITICAL",
        "metar_raw": "ZBHH 111600Z 18012G25KT 2000 TSRA SCT030CB BKN040 22/19 Q1002",
        "airport": "ZBHH 呼和浩特",
        "description": "雷暴伴CB云",
        "expected": {
            "flight_rules": "IFR",
            "visibility_m": 2000,
            "weather": ["TSRA", "CB"],
            "risk_level": "CRITICAL"
        }
    },
    {
        "id": "TSTORM_002",
        "category": "雷暴",
        "severity": "HIGH",
        "metar_raw": "ZKPY 111700Z 35008KT 9999 SCT040TCU 18/12 Q1015",
        "airport": "ZKPY 平壤",
        "description": "TCU发展",
        "expected": {
            "flight_rules": "VFR",
            "weather": ["TCU"],
            "risk_level": "HIGH"
        }
    },
    {
        "id": "TSTORM_003",
        "category": "雷暴",
        "severity": "CRITICAL",
        "metar_raw": "ZPPP 111800Z 24015G30KT 1500 TSGRRA BKN025CB 24/22 Q1000",
        "airport": "ZPPP 昆明长水",
        "description": "雷暴伴冰雹",
        "expected": {
            "flight_rules": "IFR",
            "visibility_m": 1500,
            "weather": ["TSGRRA", "CB"],
            "risk_level": "CRITICAL"
        }
    },
    {
        "id": "TSTORM_004",
        "category": "雷暴",
        "severity": "HIGH",
        "metar_raw": "ZHHH 111900Z 08010KT 6000 TS FEW030CB SCT050 30/24 Q1005",
        "airport": "ZHHH 武汉天河",
        "description": "孤立雷暴",
        "expected": {
            "flight_rules": "MVFR",
            "visibility_m": 6000,
            "weather": ["TS", "CB"],
            "risk_level": "HIGH"
        }
    },
    
    # === 积冰场景 (4个) ===
    {
        "id": "ICING_001",
        "category": "积冰",
        "severity": "HIGH",
        "metar_raw": "ZYTL 112000Z 32015KT 5000 FZFG OVC002 M02/M03 Q1025",
        "airport": "ZYTL 大连周水子",
        "description": "冻雾",
        "expected": {
            "flight_rules": "IFR",
            "visibility_m": 5000,
            "temperature_c": -2,
            "weather": ["FZFG"],
            "risk_level": "HIGH"
        }
    },
    {
        "id": "ICING_002",
        "category": "积冰",
        "severity": "HIGH",
        "metar_raw": "ZSSS 112100Z 29012KT 2000 FZDZ BR BKN006 OVC015 M01/M02 Q1022",
        "airport": "ZSSS 上海虹桥",
        "description": "冻毛毛雨",
        "expected": {
            "flight_rules": "IFR",
            "visibility_m": 2000,
            "temperature_c": -1,
            "weather": ["FZDZ", "BR"],
            "risk_level": "HIGH"
        }
    },
    {
        "id": "ICING_003",
        "category": "积冰",
        "severity": "HIGH",
        "metar_raw": "ZUUU 112200Z 36010KT 8000 SN BKN010 OVC020 M05/M07 Q1030",
        "airport": "ZUUU 成都双流",
        "description": "降雪条件",
        "expected": {
            "flight_rules": "IFR",
            "visibility_m": 8000,
            "temperature_c": -5,
            "weather": ["SN"],
            "risk_level": "HIGH"
        }
    },
    {
        "id": "ICING_004",
        "category": "积冰",
        "severity": "MEDIUM",
        "metar_raw": "ZYHB 112300Z 27008KT 9999 SCT015 BKN030 M08/M12 Q1035",
        "airport": "ZYHB 哈尔滨太平",
        "description": "低温干燥",
        "expected": {
            "flight_rules": "VFR",
            "temperature_c": -8,
            "dewpoint_c": -12,
            "risk_level": "MEDIUM"
        }
    },
    
    # === 高温极端场景 (2个) ===
    {
        "id": "HEAT_001",
        "category": "高温极端",
        "severity": "HIGH",
        "metar_raw": "ZWWW 120000Z 28015KT 9999 FU SCT050 45/12 Q1002",
        "airport": "ZWWW 乌鲁木齐",
        "description": "极端高温45度",
        "expected": {
            "flight_rules": "VFR",
            "temperature_c": 45,
            "weather": ["FU"],
            "risk_level": "HIGH"
        }
    },
    {
        "id": "HEAT_002",
        "category": "高温极端",
        "severity": "MEDIUM",
        "metar_raw": "ZSSS 120100Z 18010KT 9999 FEW040 38/22 Q1008",
        "airport": "ZSSS 上海虹桥",
        "description": "夏季高温38度",
        "expected": {
            "flight_rules": "VFR",
            "temperature_c": 38,
            "risk_level": "MEDIUM"
        }
    },
    
    # === 正常天气场景 (2个) ===
    {
        "id": "NORMAL_001",
        "category": "正常天气",
        "severity": "LOW",
        "metar_raw": "ZBAA 120200Z 36006KT 9999 FEW040 22/15 Q1015 NOSIG",
        "airport": "ZBAA 北京首都",
        "description": "标准好天气",
        "expected": {
            "flight_rules": "VFR",
            "visibility_m": 9999,
            "risk_level": "LOW"
        }
    },
    {
        "id": "NORMAL_002",
        "category": "正常天气",
        "severity": "LOW",
        "metar_raw": "ZGGG 120300Z 18012KT CAVOK 28/18 Q1012",
        "airport": "ZGGG 广州白云",
        "description": "CAVOK条件",
        "expected": {
            "flight_rules": "VFR",
            "cavok": True,
            "risk_level": "LOW"
        }
    }
]

def main():
    """生成测试数据文件"""
    output = {
        "metadata": {
            "description": "航空气象Agent PE评测测试集",
            "created": "2026-04-11",
            "total_scenarios": len(TEST_SCENARIOS),
            "categories": ["低能见度", "强风", "雷暴", "积冰", "高温极端", "正常天气"],
            "evaluation_metrics": ["准确率", "召回率", "F1 Score"]
        },
        "test_scenarios": TEST_SCENARIOS
    }
    
    output_path = Path(__file__).parent / "metar_test_scenarios.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 已生成 {len(TEST_SCENARIOS)} 个测试场景")
    print(f"📄 输出文件: {output_path}")
    
    # 统计各类别数量
    categories = {}
    for s in TEST_SCENARIOS:
        cat = s["category"]
        categories[cat] = categories.get(cat, 0) + 1
    
    print("\n📊 场景分布:")
    for cat, count in categories.items():
        print(f"  - {cat}: {count}个")

if __name__ == "__main__":
    main()