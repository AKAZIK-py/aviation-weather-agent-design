#!/usr/bin/env python3
"""
单元测试 - 定位具体错误位置
"""
import sys
sys.path.insert(0, '/mnt/user-data/workspace/aviation-weather-agent')

import asyncio
from app.nodes.parse_metar_node import METARParser
from app.nodes.assess_risk_node import RiskAssessor
from app.nodes.check_safety_node import SafetyChecker

def test_parse():
    """测试METAR解析"""
    print("\n" + "="*60)
    print("测试1: METAR解析")
    print("="*60)
    
    parser = METARParser()
    
    # 简单案例
    metar1 = "METAR ZSPD 111800Z 27008MPS 9999 FEW040 18/08 Q1018 NOSIG"
    data1, success1, errors1 = parser.parse(metar1)
    print(f"\n简单METAR: {success1}")
    print(f"天气现象: {data1.get('present_weather')}")
    
    # 复杂案例
    metar2 = "METAR ZBAA 111800Z 27025G35MPS 3000 TSRA SCT010 CB 15/14 Q0985"
    data2, success2, errors2 = parser.parse(metar2)
    print(f"\n复杂METAR: {success2}")
    print(f"天气现象: {data2.get('present_weather')}")
    if errors2:
        print(f"错误: {errors2}")
    
    return data1, data2


def test_risk_assessment(data1, data2):
    """测试风险评估"""
    print("\n" + "="*60)
    print("测试2: 风险评估")
    print("="*60)
    
    assessor = RiskAssessor()
    
    # 简单案例
    risk1, factors1, reasoning1 = assessor.assess(data1, "ground_crew")
    print(f"\n简单METAR风险: {risk1}")
    print(f"风险因素: {factors1}")
    print(f"类型检查: {[type(f) for f in factors1]}")
    
    # 复杂案例
    try:
        risk2, factors2, reasoning2 = assessor.assess(data2, "pilot")
        print(f"\n复杂METAR风险: {risk2}")
        print(f"风险因素: {factors2}")
        print(f"类型检查: {[type(f) for f in factors2]}")
    except Exception as e:
        print(f"\n风险评估失败: {e}")
        import traceback
        traceback.print_exc()


def test_safety_check(data1, data2):
    """测试安全检查"""
    print("\n" + "="*60)
    print("测试3: 安全检查")
    print("="*60)
    
    checker = SafetyChecker()
    
    # 构建状态
    state1 = {
        "metar_parsed": data1,
        "risk_level": "LOW",
        "detected_role": "ground_crew"
    }
    
    state2 = {
        "metar_parsed": data2,
        "risk_level": "CRITICAL",
        "detected_role": "pilot"
    }
    
    # 简单案例
    result1 = checker.check(state1)
    print(f"\n简单METAR安全检查: {result1['passed']}")
    print(f"违规: {result1['violations']}")
    
    # 复杂案例
    try:
        result2 = checker.check(state2)
        print(f"\n复杂METAR安全检查: {result2['passed']}")
        print(f"违规: {result2['violations']}")
        print(f"干预原因: {result2['intervention_reason']}")
    except Exception as e:
        print(f"\n安全检查失败: {e}")
        import traceback
        traceback.print_exc()


def main():
    print("\n" + "🔧"*30)
    print("单元测试 - 定位错误")
    print("🔧"*30)
    
    data1, data2 = test_parse()
    test_risk_assessment(data1, data2)
    test_safety_check(data1, data2)
    
    print("\n" + "="*60)
    print("单元测试完成")
    print("="*60)


if __name__ == "__main__":
    main()
