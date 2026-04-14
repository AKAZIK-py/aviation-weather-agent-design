#!/usr/bin/env python3
"""
完整API链路测试
测试航空气象Agent后端的完整工作流程
"""
import requests
import json
import sys
from datetime import datetime

BASE_URL = "http://localhost:8000/api/v1"

def test_health():
    """测试健康检查"""
    print("\n" + "="*60)
    print("测试1: 健康检查 /health")
    print("="*60)
    
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=10)
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(json.dumps(data, indent=2, ensure_ascii=False))
            return True
        else:
            print(f"失败: {response.text}")
            return False
    except Exception as e:
        print(f"❌ 错误: {e}")
        return False


def test_analyze_api(metar_raw, role="pilot", user_query=""):
    """测试分析API"""
    print("\n" + "="*60)
    print(f"测试2: 分析API /analyze")
    print(f"METAR: {metar_raw}")
    print(f"角色: {role}")
    print(f"问题: {user_query}")
    print("="*60)
    
    payload = {
        "metar_raw": metar_raw,
        "role": role,
        "user_query": user_query,
        "session_id": f"test-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/analyze",
            json=payload,
            timeout=30
        )
        
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("\n" + "─"*60)
            print("返回结果:")
            print("─"*60)
            print(json.dumps(data, indent=2, ensure_ascii=False))
            return data
        else:
            print(f"失败: {response.text}")
            return None
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return None


def verify_response(response):
    """验证响应数据完整性"""
    print("\n" + "="*60)
    print("测试3: 验证响应数据完整性")
    print("="*60)
    
    if not response:
        print("❌ 响应为空")
        return False
    
    checks = {
        "success": response.get("success"),
        "metar_parsed": response.get("metar_parsed") is not None,
        "detected_role": response.get("detected_role") is not None,
        "risk_level": response.get("risk_level") is not None,
        "explanation": response.get("explanation") is not None,
        "processing_time_ms": response.get("processing_time_ms") is not None,
    }
    
    all_passed = True
    for key, value in checks.items():
        status = "✓" if value else "✗"
        print(f"{status} {key}: {value}")
        if not value:
            all_passed = False
    
    return all_passed


def main():
    """主测试流程"""
    print("\n" + "🚀"*30)
    print("航空气象Agent API完整链路测试")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("🚀"*30)
    
    # 测试1: 健康检查
    health_ok = test_health()
    if not health_ok:
        print("\n❌ 服务不可用，停止测试")
        return 1
    
    # 测试2: 分析API - 上海浦东机场
    metar_zspd = "METAR ZSPD 111800Z 27008MPS 9999 FEW040 18/08 Q1018 NOSIG"
    response = test_analyze_api(
        metar_raw=metar_zspd,
        role="ground_crew",
        user_query="当前天气适合地面作业吗？"
    )
    
    if not response:
        print("\n❌ API调用失败")
        return 1
    
    # 测试3: 验证响应
    verify_ok = verify_response(response)
    
    # 测试4: 测试高风险场景
    print("\n" + "="*60)
    print("测试4: 高风险天气场景")
    print("="*60)
    
    metar_high_risk = "METAR ZBAA 111800Z 27025G35MPS 3000 TSRA SCT010 CB 15/14 Q0985 TEMPO TL2020 25030G45MPS 1500 TSRA"
    response2 = test_analyze_api(
        metar_raw=metar_high_risk,
        role="pilot",
        user_query="能起飞吗？"
    )
    
    # 汇总结果
    print("\n" + "="*60)
    print("📊 测试结果汇总")
    print("="*60)
    print(f"{'✓' if health_ok else '✗'} 健康检查")
    print(f"{'✓' if response else '✗'} API调用")
    print(f"{'✓' if verify_ok else '✗'} 数据完整性验证")
    
    if health_ok and response:
        print("\n✅ 核心功能正常")
        return 0
    else:
        print("\n❌ 存在问题")
        return 1


if __name__ == "__main__":
    sys.exit(main())
