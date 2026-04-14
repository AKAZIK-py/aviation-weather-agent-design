#!/usr/bin/env python3
"""测试后端API"""
import requests
import json

BASE_URL = "http://localhost:8000/api/v1"

def test_health():
    """测试健康检查"""
    print("=" * 50)
    print("测试健康检查...")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        print(f"状态码: {response.status_code}")
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"错误: {e}")

def test_analyze():
    """测试分析接口"""
    print("\n" + "=" * 50)
    print("测试METAR分析...")
    
    payload = {
        "metar_raw": "METAR ZSPD 111800Z 24008MPS 9999 SCT030 12/08 Q1018 NOSIG",
        "role": "ground_crew"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/analyze", json=payload, timeout=30)
        print(f"状态码: {response.status_code}")
        result = response.json()
        print(json.dumps(result, indent=2, ensure_ascii=False)[:2000])
    except Exception as e:
        print(f"错误: {e}")

if __name__ == "__main__":
    test_health()
    test_analyze()
