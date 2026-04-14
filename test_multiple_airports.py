"""
多机场测试脚本
"""
import requests
import json
import time

BASE_URL = "http://localhost:8000/api/v1"

def test_airport(icao, role="pilot"):
    """测试单个机场"""
    print(f"\n{'='*60}")
    print(f"测试机场: {icao} (角色: {role})")
    print(f"{'='*60}")
    
    try:
        response = requests.post(
            f"{BASE_URL}/analyze",
            json={"airport_icao": icao, "role": role},
            timeout=60
        )
        
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            metar = data.get("metar_parsed", {})
            print(f"✅ 成功!")
            print(f"   METAR: {metar.get('raw_text', 'N/A')[:60]}...")
            print(f"   温度: {metar.get('temperature')}°C")
            print(f"   风速: {metar.get('wind_speed')}KT")
            print(f"   能见度: {metar.get('visibility')}km")
            print(f"   飞行规则: {metar.get('flight_rules')}")
            print(f"   风险等级: {data.get('risk_level')}")
            return True
        else:
            print(f"❌ 失败: {response.json().get('detail', 'Unknown error')}")
            return False
            
    except Exception as e:
        print(f"❌ 异常: {str(e)}")
        return False

def main():
    """测试多个机场"""
    print("="*80)
    print("多机场METAR数据获取测试")
    print("="*80)
    
    # 测试配置
    test_cases = [
        ("ZSPD", "pilot"),           # 上海浦东 - 飞行员
        ("ZSHC", "ground_crew"),     # 杭州萧山 - 地勤
        ("ZSNJ", "dispatcher"),      # 南京禄口 - 运控
        ("ZSSS", "pilot"),           # 上海虹桥 - 飞行员
    ]
    
    results = {}
    
    for icao, role in test_cases:
        success = test_airport(icao, role)
        results[f"{icao}({role})"] = success
        time.sleep(1)  # 避免请求过快
    
    # 总结
    print("\n" + "="*80)
    print("测试总结")
    print("="*80)
    
    for test_name, passed in results.items():
        status = "✅" if passed else "❌"
        print(f"{status} {test_name}")
    
    total = len(results)
    passed = sum(results.values())
    print(f"\n通过率: {passed}/{total} ({passed/total*100:.0f}%)")
    
    return results

if __name__ == "__main__":
    main()
