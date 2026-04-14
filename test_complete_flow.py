"""
完整链路功能测试脚本
测试机场列表API和分析API
"""
import requests
import json
import time
import sys

BASE_URL = "http://localhost:8000/api/v1"

def print_separator(title):
    """打印分隔符"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

def print_response(response, show_body=True):
    """格式化打印响应"""
    print(f"状态码: {response.status_code}")
    print(f"响应时间: {response.elapsed.total_seconds() * 1000:.2f}ms")
    
    if show_body:
        print("\n响应内容:")
        try:
            data = response.json()
            print(json.dumps(data, indent=2, ensure_ascii=False))
        except Exception as e:
            print(response.text)
    
    return response

def test_health():
    """测试健康检查接口"""
    print_separator("测试1: 健康检查 GET /api/v1/health")
    
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        print_response(response)
        return response.status_code == 200
    except Exception as e:
        print(f"❌ 错误: {str(e)}")
        return False

def test_airports_list():
    """测试机场列表API"""
    print_separator("测试2: 机场列表 GET /api/v1/airports")
    
    try:
        response = requests.get(f"{BASE_URL}/airports", timeout=5)
        print_response(response)
        
        if response.status_code == 200:
            data = response.json()
            airports = data.get("airports", [])
            print(f"\n✅ 成功获取 {len(airports)} 个机场")
            
            # 显示部分机场信息
            if airports:
                print("\n机场列表示例:")
                for airport in airports[:5]:
                    print(f"  - {airport.get('icao')}: {airport.get('name')} ({airport.get('city')})")
            
            return True
        return False
    except Exception as e:
        print(f"❌ 错误: {str(e)}")
        return False

def test_analyze_zspd_pilot():
    """测试分析API - ZSPD机场，飞行员角色"""
    print_separator("测试3: 分析API - ZSPD机场 (飞行员)")
    
    payload = {
        "airport_icao": "ZSPD",
        "role": "pilot"
    }
    
    print(f"请求体: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(
            f"{BASE_URL}/analyze",
            json=payload,
            timeout=30
        )
        print_response(response)
        
        if response.status_code == 200:
            data = response.json()
            
            # 验证响应结构
            print("\n验证响应结构:")
            
            # 检查airport_info
            if "airport_info" in data:
                print("✅ 包含 airport_info")
                airport = data["airport_info"]
                print(f"   机场: {airport.get('name')} ({airport.get('icao')})")
            else:
                print("❌ 缺少 airport_info")
            
            # 检查METAR数据
            if "metar" in data:
                print("✅ 包含 METAR 数据")
                metar = data["metar"]
                if isinstance(metar, dict):
                    print(f"   原始报文: {metar.get('raw', 'N/A')[:60]}...")
            else:
                print("❌ 缺少 METAR 数据")
            
            # 检查角色特定解释
            if "role_specific_explanation" in data:
                print("✅ 包含 role_specific_explanation")
                explanation = data["role_specific_explanation"]
                if isinstance(explanation, str):
                    print(f"   解释长度: {len(explanation)} 字符")
                elif isinstance(explanation, dict):
                    print(f"   解释字段: {list(explanation.keys())}")
            else:
                print("❌ 缺少 role_specific_explanation")
            
            # 检查风险等级
            if "risk_level" in data:
                print(f"✅ 包含 risk_level: {data['risk_level']}")
            else:
                print("⚠️  缺少 risk_level")
            
            return True
        else:
            print(f"❌ 请求失败: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ 错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_analyze_zsss_ground_crew():
    """测试分析API - ZSSS机场，地勤角色"""
    print_separator("测试4: 分析API - ZSSS机场 (地勤)")
    
    payload = {
        "airport_icao": "ZSSS",
        "role": "ground_crew"
    }
    
    print(f"请求体: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(
            f"{BASE_URL}/analyze",
            json=payload,
            timeout=30
        )
        print_response(response)
        
        if response.status_code == 200:
            data = response.json()
            
            # 验证响应结构
            print("\n验证响应结构:")
            
            # 检查airport_info
            if "airport_info" in data:
                print("✅ 包含 airport_info")
                airport = data["airport_info"]
                print(f"   机场: {airport.get('name')} ({airport.get('icao')})")
            else:
                print("❌ 缺少 airport_info")
            
            # 检查METAR数据
            if "metar" in data:
                print("✅ 包含 METAR 数据")
                metar = data["metar"]
                if isinstance(metar, dict):
                    print(f"   原始报文: {metar.get('raw', 'N/A')[:60]}...")
            else:
                print("❌ 缺少 METAR 数据")
            
            # 检查角色特定解释
            if "role_specific_explanation" in data:
                print("✅ 包含 role_specific_explanation")
                explanation = data["role_specific_explanation"]
                if isinstance(explanation, str):
                    print(f"   解释长度: {len(explanation)} 字符")
                    # 显示部分解释内容
                    if len(explanation) > 200:
                        print(f"   内容预览: {explanation[:200]}...")
                elif isinstance(explanation, dict):
                    print(f"   解释字段: {list(explanation.keys())}")
            else:
                print("❌ 缺少 role_specific_explanation")
            
            # 检查风险等级
            if "risk_level" in data:
                print(f"✅ 包含 risk_level: {data['risk_level']}")
            else:
                print("⚠️  缺少 risk_level")
            
            # 对比飞行员和地勤的解释差异
            print("\n地勤角色特点:")
            if "role_specific_explanation" in data:
                explanation = data["role_specific_explanation"]
                if isinstance(explanation, str):
                    keywords = ["地面", "停机", "能见度", "滑行", "除冰"]
                    found_keywords = [kw for kw in keywords if kw in explanation]
                    if found_keywords:
                        print(f"   发现地勤相关关键词: {', '.join(found_keywords)}")
            
            return True
        else:
            print(f"❌ 请求失败: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ 错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主测试函数"""
    print_separator("航空气象Agent完整链路测试")
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"基础URL: {BASE_URL}")
    
    results = {
        "健康检查": False,
        "机场列表": False,
        "ZSPD分析(飞行员)": False,
        "ZSSS分析(地勤)": False
    }
    
    # 执行测试
    results["健康检查"] = test_health()
    time.sleep(0.5)
    
    results["机场列表"] = test_airports_list()
    time.sleep(0.5)
    
    results["ZSPD分析(飞行员)"] = test_analyze_zspd_pilot()
    time.sleep(0.5)
    
    results["ZSSS分析(地勤)"] = test_analyze_zsss_ground_crew()
    
    # 打印测试总结
    print_separator("测试总结")
    
    for test_name, passed in results.items():
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{test_name:20s}: {status}")
    
    total = len(results)
    passed = sum(results.values())
    print(f"\n总计: {passed}/{total} 测试通过")
    
    # 返回退出码
    if passed == total:
        print("\n🎉 所有测试通过!")
        return 0
    else:
        print("\n⚠️  部分测试失败")
        return 1

if __name__ == "__main__":
    sys.exit(main())
