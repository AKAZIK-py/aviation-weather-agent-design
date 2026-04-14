#!/usr/bin/env python3
"""
最终验证测试 - 完整API链路验证报告
"""
import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:8000/api/v1"

def test_health():
    """测试健康检查"""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=10)
        return response.status_code == 200, response.json()
    except Exception as e:
        return False, {"error": str(e)}


def test_analyze(metar_raw, role, user_query=""):
    """测试分析API"""
    payload = {
        "metar_raw": metar_raw,
        "role": role,
        "user_query": user_query,
        "session_id": f"test-{datetime.now().strftime('%H%M%S')}"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/analyze", json=payload, timeout=30)
        data = response.json()
        return data.get("success", False), data
    except Exception as e:
        return False, {"error": str(e)}


def main():
    print("\n" + "="*80)
    print("航空气象Agent API完整链路验证报告")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    
    # 测试结果汇总
    results = []
    
    # 1. 健康检查
    print("\n【测试1】健康检查")
    success, data = test_health()
    print(f"  状态: {'✓ 通过' if success else '✗ 失败'}")
    print(f"  LLM可用: {data.get('llm_available', False)}")
    results.append(("健康检查", success))
    
    # 2. 测试场景
    test_scenarios = [
        {
            "name": "上海浦东-地勤-低风险",
            "metar": "METAR ZSPD 111800Z 27008MPS 9999 FEW040 18/08 Q1018 NOSIG",
            "role": "ground_crew",
            "query": "当前天气适合地面作业吗？",
            "expected_risk": "LOW"
        },
        {
            "name": "北京首都-飞行员-高风险",
            "metar": "METAR ZBAA 111800Z 27025G35MPS 3000 TSRA SCT010 CB 15/14 Q0985",
            "role": "pilot",
            "query": "能起飞吗？",
            "expected_risk": "CRITICAL"
        },
        {
            "name": "广州白云-签派员-中风险",
            "metar": "METAR ZGGG 111800Z 18015KT 6000 -RA BKN015 20/18 Q1010",
            "role": "dispatcher",
            "query": "需要备降吗？",
            "expected_risk": "MEDIUM"
        },
        {
            "name": "成都双流-预报员-低风险",
            "metar": "METAR ZUUU 111800Z 24008G15KT 3000 BR SCT030 08/06 Q1018 NOSIG",
            "role": "forecaster",
            "query": "天气趋势如何？",
            "expected_risk": "MEDIUM"
        }
    ]
    
    # 执行测试
    for i, scenario in enumerate(test_scenarios, 2):
        print(f"\n【测试{i}】{scenario['name']}")
        print(f"  METAR: {scenario['metar'][:50]}...")
        print(f"  角色: {scenario['role']}")
        
        success, data = test_analyze(
            scenario['metar'],
            scenario['role'],
            scenario['query']
        )
        
        if success:
            print(f"  状态: ✓ 通过")
            print(f"  风险等级: {data.get('risk_level')} (预期: {scenario['expected_risk']})")
            print(f"  干预需求: {'是' if data.get('intervention_required') else '否'}")
            print(f"  处理时间: {data.get('processing_time_ms', 0):.2f}ms")
            
            # 验证关键字段
            has_parsed = data.get('metar_parsed') is not None
            has_role = data.get('detected_role') is not None
            has_explanation = data.get('explanation') is not None
            
            print(f"  数据完整性: 解析{'✓' if has_parsed else '✗'} 角色{'✓' if has_role else '✗'} 解释{'✓' if has_explanation else '✗'}")
            
            results.append((scenario['name'], success and has_parsed and has_role and has_explanation))
        else:
            print(f"  状态: ✗ 失败")
            print(f"  错误: {data.get('error', '未知错误')}")
            results.append((scenario['name'], False))
    
    # 汇总报告
    print("\n" + "="*80)
    print("测试结果汇总")
    print("="*80)
    
    passed = sum(1 for _, s in results if s)
    total = len(results)
    
    for name, success in results:
        status = "✓ 通过" if success else "✗ 失败"
        print(f"  {status}  {name}")
    
    print(f"\n总计: {passed}/{total} 通过")
    print(f"通过率: {passed/total*100:.1f}%")
    
    if passed == total:
        print("\n✅ 所有测试通过！API链路工作正常")
        return 0
    else:
        print(f"\n⚠️  {total-passed}个测试失败，需要修复")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
