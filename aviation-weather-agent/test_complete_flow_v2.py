"""
完整链路功能测试脚本 v2
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

def test_analyze(icao, role):
    """测试分析API"""
    print_separator(f"测试: 分析API - {icao}机场 ({role})")
    
    payload = {
        "airport_icao": icao,
        "role": role
    }
    
    print(f"请求体: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(
            f"{BASE_URL}/analyze",
            json=payload,
            timeout=60
        )
        
        # 打印响应
        print(f"状态码: {response.status_code}")
        print(f"响应时间: {response.elapsed.total_seconds() * 1000:.2f}ms")
        
        if response.status_code == 200:
            data = response.json()
            
            # 打印响应内容（截断长文本）
            print("\n响应内容:")
            display_data = {
                "success": data.get("success"),
                "metar_parsed": data.get("metar_parsed"),
                "metar_metadata": {
                    k: v for k, v in (data.get("metar_metadata") or {}).items()
                    if k in ["icao", "station_name", "temperature", "wind_speed", "visibility"]
                } if data.get("metar_metadata") else None,
                "detected_role": data.get("detected_role"),
                "risk_level": data.get("risk_level"),
                "risk_factors": data.get("risk_factors"),
                "explanation": (data.get("explanation") or "")[:300] + "..." if data.get("explanation") and len(data.get("explanation", "")) > 300 else data.get("explanation"),
                "intervention_required": data.get("intervention_required"),
                "llm_calls": data.get("llm_calls"),
                "processing_time_ms": data.get("processing_time_ms"),
            }
            print(json.dumps(display_data, indent=2, ensure_ascii=False))
            
            # 验证响应结构
            print("\n验证响应结构:")
            
            validation_passed = True
            
            # 检查success标志
            if data.get("success"):
                print("✅ success: true")
            else:
                print(f"❌ success: {data.get('success')}")
                validation_passed = False
            
            # 检查METAR解析数据
            if data.get("metar_parsed"):
                print("✅ 包含 metar_parsed")
                metar = data["metar_parsed"]
                print(f"   ICAO: {metar.get('icao_code')}")
                print(f"   温度: {metar.get('temperature')}°C")
                print(f"   风速: {metar.get('wind_speed')}KT")
                print(f"   能见度: {metar.get('visibility')}km")
                print(f"   飞行规则: {metar.get('flight_rules')}")
            else:
                print("❌ 缺少 metar_parsed")
                validation_passed = False
            
            # 检查METAR元数据
            if data.get("metar_metadata"):
                print("✅ 包含 metar_metadata")
                meta = data["metar_metadata"]
                print(f"   机场: {meta.get('station_name')}")
            else:
                print("⚠️  缺少 metar_metadata（可能使用直接输入的METAR）")
            
            # 检查角色检测
            if data.get("detected_role"):
                print(f"✅ 检测到角色: {data['detected_role']}")
                if data['detected_role'] == role:
                    print(f"   ✅ 角色匹配请求: {role}")
                else:
                    print(f"   ⚠️  角色不匹配请求: 请求={role}, 检测={data['detected_role']}")
            else:
                print("❌ 缺少 detected_role")
                validation_passed = False
            
            # 检查风险等级
            if data.get("risk_level"):
                print(f"✅ 包含 risk_level: {data['risk_level']}")
            else:
                print("❌ 缺少 risk_level")
                validation_passed = False
            
            # 检查风险因素
            if data.get("risk_factors"):
                print(f"✅ 包含 risk_factors: {data['risk_factors']}")
            else:
                print("⚠️  无风险因素")
            
            # 检查解释
            if data.get("explanation"):
                explanation = data["explanation"]
                print(f"✅ 包含 explanation ({len(explanation)} 字符)")
                
                # 检查角色特定内容
                role_keywords = {
                    "pilot": ["飞行员", "飞行", "起降", "进近"],
                    "ground_crew": ["地勤", "机务", "地面", "维护"],
                    "dispatcher": ["运控", "签派", "调度"],
                    "forecaster": ["预报", "气象", "趋势"]
                }
                
                if role in role_keywords:
                    found = [kw for kw in role_keywords[role] if kw in explanation]
                    if found:
                        print(f"   发现角色相关关键词: {', '.join(found)}")
            else:
                print("❌ 缺少 explanation")
                validation_passed = False
            
            # 检查推理轨迹
            if data.get("reasoning_trace"):
                print(f"✅ 包含 reasoning_trace ({len(data['reasoning_trace'])} 条)")
                print("   推理步骤预览:")
                for trace in data['reasoning_trace'][:3]:
                    print(f"   - {trace[:80]}...")
            else:
                print("⚠️  缺少 reasoning_trace")
            
            # 检查处理时间
            if data.get("processing_time_ms"):
                print(f"✅ 处理时间: {data['processing_time_ms']:.2f}ms")
            
            return validation_passed
        else:
            # 非200响应
            print("\n响应内容:")
            print(json.dumps(response.json(), indent=2, ensure_ascii=False))
            print(f"❌ 请求失败: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ 错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主测试函数"""
    print_separator("航空气象Agent完整链路测试 v2")
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
    time.sleep(0.3)
    
    results["机场列表"] = test_airports_list()
    time.sleep(0.3)
    
    results["ZSPD分析(飞行员)"] = test_analyze("ZSPD", "pilot")
    time.sleep(0.3)
    
    results["ZSSS分析(地勤)"] = test_analyze("ZSSS", "ground_crew")
    
    # 打印测试总结
    print_separator("测试总结")
    
    for test_name, passed in results.items():
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{test_name:25s}: {status}")
    
    total = len(results)
    passed = sum(results.values())
    print(f"\n总计: {passed}/{total} 测试通过")
    
    # 返回退出码
    if passed == total:
        print("\n🎉 所有测试通过!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} 个测试失败")
        return 1

if __name__ == "__main__":
    sys.exit(main())
