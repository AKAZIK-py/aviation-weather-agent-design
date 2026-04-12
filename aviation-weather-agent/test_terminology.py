#!/usr/bin/env python3
"""
测试术语表功能
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.utils.terminology import (
    get_term_cn,
    get_term_en,
    format_bilingual,
    translate_report,
    get_terminology_dict,
    search_terms
)

def test_terminology():
    """测试术语表功能"""
    print("测试术语表功能...")
    
    # 测试中英文翻译
    print("\n1. 测试中英文翻译")
    print(f"TS -> 中文: {get_term_cn('TS')}")
    print(f"Thunderstorm -> 中文: {get_term_cn('Thunderstorm')}")
    print(f"雷暴 -> 英文: {get_term_en('雷暴')}")
    print(f"VFR -> 中文: {get_term_cn('VFR')}")
    print(f"Visual Flight Rules -> 中文: {get_term_cn('Visual Flight Rules')}")
    
    # 测试双语格式化
    print("\n2. 测试双语格式化")
    print(f"双语格式: {format_bilingual('雷暴', 'Thunderstorm')}")
    print(f"双语格式: {format_bilingual('目视飞行规则', 'Visual Flight Rules')}")
    
    # 测试报告翻译
    print("\n3. 测试报告翻译")
    report_en = "Thunderstorm observed near airport. Wind speed 15 knots. Visibility 10km. Flight rules: VFR."
    report_cn = translate_report(report_en, "cn")
    print(f"英文报告: {report_en}")
    print(f"中文翻译: {report_cn}")
    
    # 测试反向翻译
    report_cn2 = "机场附近观测到雷暴。风速15节。能见度10公里。飞行规则：目视飞行规则。"
    report_en2 = translate_report(report_cn2, "en")
    print(f"中文报告: {report_cn2}")
    print(f"英文翻译: {report_en2}")
    
    # 测试获取术语字典
    print("\n4. 测试获取术语字典")
    weather_terms = get_terminology_dict("weather")
    print(f"天气现象术语数量: {len(weather_terms)}")
    print(f"前3个天气术语: {list(weather_terms.items())[:3]}")
    
    # 测试搜索术语
    print("\n5. 测试搜索术语")
    results = search_terms("thunder", "en")
    print(f"搜索 'thunder' 的结果: {len(results)}个")
    for result in results[:3]:
        print(f"  - {result['bilingual']}")
    
    results_cn = search_terms("雷", "cn")
    print(f"搜索 '雷' 的结果: {len(results_cn)}个")
    for result in results_cn[:3]:
        print(f"  - {result['bilingual']}")
    
    print("\n所有测试完成!")

if __name__ == "__main__":
    test_terminology()