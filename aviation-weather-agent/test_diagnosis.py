#!/usr/bin/env python3
"""
详细诊断测试 - 定位API错误
"""
import requests
import json
import traceback

BASE_URL = "http://localhost:8000/api/v1"

def test_simple_case():
    """测试简单案例"""
    print("\n" + "="*60)
    print("测试简单METAR")
    print("="*60)
    
    metar = "METAR ZSPD 111800Z 27008MPS 9999 FEW040 18/08 Q1018 NOSIG"
    
    payload = {
        "metar_raw": metar,
        "role": "ground_crew",
        "user_query": "测试",
        "session_id": "test-001"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/analyze", json=payload, timeout=30)
        print(f"状态码: {response.status_code}")
        data = response.json()
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return data
    except Exception as e:
        print(f"错误: {e}")
        traceback.print_exc()
        return None


def test_complex_case():
    """测试复杂案例（带天气现象）"""
    print("\n" + "="*60)
    print("测试复杂METAR（带雷暴）")
    print("="*60)
    
    # 这个METAR包含雷暴、低能见度等复杂天气
    metar = "METAR ZBAA 111800Z 27025G35MPS 3000 TSRA SCT010 CB 15/14 Q0985"
    
    payload = {
        "metar_raw": metar,
        "role": "pilot",
        "user_query": "能起飞吗？",
        "session_id": "test-002"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/analyze", json=payload, timeout=30)
        print(f"状态码: {response.status_code}")
        data = response.json()
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return data
    except Exception as e:
        print(f"错误: {e}")
        traceback.print_exc()
        return None


def test_edge_case():
    """测试边缘案例"""
    print("\n" + "="*60)
    print("测试边缘案例（TEMPO趋势预报）")
    print("="*60)
    
    # 这个METAR包含TEMPO趋势预报
    metar = "METAR ZBAA 111800Z 27025G35MPS 3000 TSRA SCT010 CB 15/14 Q0985 TEMPO TL2020 25030G45MPS 1500 TSRA"
    
    payload = {
        "metar_raw": metar,
        "role": "dispatcher",
        "user_query": "需要备降吗？",
        "session_id": "test-003"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/analyze", json=payload, timeout=30)
        print(f"状态码: {response.status_code}")
        data = response.json()
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return data
    except Exception as e:
        print(f"错误: {e}")
        traceback.print_exc()
        return None


def main():
    print("\n" + "🔍"*30)
    print("API诊断测试")
    print("🔍"*30)
    
    # 测试1: 简单案例
    result1 = test_simple_case()
    
    # 测试2: 复杂案例
    result2 = test_complex_case()
    
    # 测试3: 边缘案例
    result3 = test_edge_case()
    
    print("\n" + "="*60)
    print("诊断结果汇总")
    print("="*60)
    
    for i, (name, result) in enumerate([
        ("简单METAR", result1),
        ("复杂METAR", result2),
        ("边缘案例", result3)
    ], 1):
        status = "✓" if result and result.get("success") else "✗"
        error = result.get("error", "无") if result else "请求失败"
        print(f"{status} 测试{i}: {name} - {error if status == '✗' else '成功'}")


if __name__ == "__main__":
    main()
