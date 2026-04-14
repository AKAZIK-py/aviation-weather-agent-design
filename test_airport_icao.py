#!/usr/bin/env python3
"""
测试airport_icao参数完整链路
验证：airport_icao → METAR fetch → parse METAR → generate explanation
"""
import requests
import json
import sys
from datetime import datetime

BASE_URL = "http://localhost:8000/api/v1"


def test_analyze_with_airport_icao(icao_code, role="pilot", user_query=""):
    """测试使用airport_icao参数调用analyze"""
    print("\n" + "="*70)
    print(f"测试: 使用airport_icao={icao_code}调用分析API")
    print("="*70)
    
    payload = {
        "airport_icao": icao_code,
        "role": role,
        "user_query": user_query or f"分析{icao_code}机场当前天气状况",
        "session_id": f"test-icao-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    }
    
    print(f"\n请求数据:")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    
    try:
        response = requests.post(
            f"{BASE_URL}/analyze",
            json=payload,
            timeout=30
        )
        
        print(f"\n状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("\n" + "─"*70)
            print("响应结果:")
            print("─"*70)
            
            # 提取关键字段
            print(f"✓ 成功: {data.get('success')}")
            print(f"✓ 风险等级: {data.get('risk_level')}")
            print(f"✓ 检测角色: {data.get('detected_role')}")
            print(f"✓ LLM调用次数: {data.get('llm_calls')}")
            print(f"✓ 处理时间: {data.get('processing_time_ms'):.2f}ms")
            
            # METAR元数据（仅从ICAO获取时有）
            if data.get('metar_metadata'):
                print(f"\nMETAR元数据:")
                metadata = data['metar_metadata']
                print(f"  - ICAO: {metadata.get('icao')}")
                print(f"  - 获取时间: {metadata.get('fetch_time')}")
                print(f"  - 观测时间: {metadata.get('observation_time')}")
                print(f"  - 飞行类别: {metadata.get('flight_category')}")
            
            # 解析后的METAR
            if data.get('metar_parsed'):
                print(f"\n解析后的METAR:")
                parsed = data['metar_parsed']
                print(f"  - ICAO: {parsed.get('icao_code')}")
                print(f"  - 风向: {parsed.get('wind_direction')}°")
                print(f"  - 风速: {parsed.get('wind_speed')} m/s")
                print(f"  - 能见度: {parsed.get('visibility')} m")
                print(f"  - 温度: {parsed.get('temperature')}°C")
                print(f"  - 飞行规则: {parsed.get('flight_rules')}")
            
            # 解释
            if data.get('explanation'):
                print(f"\n个性化解释:")
                print("─"*70)
                print(data['explanation'][:500] + "..." if len(data.get('explanation', '')) > 500 else data['explanation'])
            
            return data
        else:
            print(f"\n❌ 请求失败: {response.text}")
            return None
            
    except requests.exceptions.ConnectionError:
        print(f"\n❌ 无法连接到服务器 {BASE_URL}")
        print("请确保服务已启动: python -m uvicorn app.main:app --reload")
        return None
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_analyze_with_metar_raw(metar_raw, role="pilot"):
    """测试使用metar_raw参数调用analyze（对比测试）"""
    print("\n" + "="*70)
    print(f"测试: 使用metar_raw调用分析API（对比测试）")
    print("="*70)
    
    payload = {
        "metar_raw": metar_raw,
        "role": role,
        "user_query": "分析当前天气状况",
        "session_id": f"test-metar-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/analyze",
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ 成功，风险等级: {data.get('risk_level')}")
            return data
        else:
            print(f"❌ 失败: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ 错误: {e}")
        return None


def test_validation_errors():
    """测试参数验证错误"""
    print("\n" + "="*70)
    print("测试: 参数验证错误场景")
    print("="*70)
    
    # 测试1: 同时提供metar_raw和airport_icao（应失败）
    print("\n1. 同时提供metar_raw和airport_icao:")
    payload = {
        "metar_raw": "ZBAA 110530Z 35008MPS 9999 FEW040 12/M05 Q1018",
        "airport_icao": "ZBAA",
        "role": "pilot"
    }
    response = requests.post(f"{BASE_URL}/analyze", json=payload, timeout=10)
    print(f"   状态码: {response.status_code}")
    if response.status_code == 400:
        print(f"   ✓ 正确返回400错误: {response.json().get('detail')}")
    else:
        print(f"   ✗ 应该返回400，实际返回{response.status_code}")
    
    # 测试2: 两者都不提供（应失败）
    print("\n2. 不提供metar_raw和airport_icao:")
    payload = {"role": "pilot"}
    response = requests.post(f"{BASE_URL}/analyze", json=payload, timeout=10)
    print(f"   状态码: {response.status_code}")
    if response.status_code == 400:
        print(f"   ✓ 正确返回400错误: {response.json().get('detail')}")
    else:
        print(f"   ✗ 应该返回400，实际返回{response.status_code}")
    
    # 测试3: 无效的ICAO代码
    print("\n3. 无效的ICAO代码（不是4位）:")
    payload = {"airport_icao": "ABC", "role": "pilot"}
    response = requests.post(f"{BASE_URL}/analyze", json=payload, timeout=10)
    print(f"   状态码: {response.status_code}")


def main():
    """主测试流程"""
    print("\n" + "🛫"*35)
    print("航空气象Agent - airport_icao完整链路测试")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("🛫"*35)
    
    # 测试支持的江浙沪机场
    test_airports = [
        ("ZSPD", "上海浦东"),
        ("ZSSS", "上海虹桥"),
        ("ZSNJ", "南京禄口"),
    ]
    
    results = []
    
    for icao, name in test_airports:
        print(f"\n\n{'='*70}")
        print(f"测试机场: {name} ({icao})")
        print('='*70)
        
        result = test_analyze_with_airport_icao(
            icao_code=icao,
            role="pilot",
            user_query=f"分析{name}机场当前天气，是否适合起降？"
        )
        
        results.append({
            "icao": icao,
            "name": name,
            "success": result is not None and result.get("success"),
            "risk_level": result.get("risk_level") if result else None
        })
    
    # 测试参数验证
    test_validation_errors()
    
    # 汇总结果
    print("\n\n" + "="*70)
    print("📊 测试结果汇总")
    print("="*70)
    
    for r in results:
        status = "✅" if r["success"] else "❌"
        risk = r.get("risk_level", "N/A")
        print(f"{status} {r['name']} ({r['icao']}): 风险等级={risk}")
    
    success_count = sum(1 for r in results if r["success"])
    total_count = len(results)
    
    print(f"\n成功率: {success_count}/{total_count} ({success_count/total_count*100:.0f}%)")
    
    if success_count == total_count:
        print("\n✅ 所有测试通过！airport_icao链路正常工作")
        return 0
    else:
        print("\n⚠️  部分测试失败，请检查METAR服务或网络连接")
        return 1


if __name__ == "__main__":
    sys.exit(main())
