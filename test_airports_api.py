"""
测试机场列表API端点
"""
import requests
import json

BASE_URL = "http://localhost:8000"

def test_airports_endpoint():
    """测试 GET /api/v1/airports 端点"""
    url = f"{BASE_URL}/api/v1/airports"
    
    print(f"测试端点: {url}")
    print("-" * 50)
    
    try:
        response = requests.get(url, timeout=10)
        
        print(f"状态码: {response.status_code}")
        print(f"响应头: {dict(response.headers)}\n")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 成功获取机场列表")
            print(f"机场总数: {len(data.get('airports', []))}")
            print("\n前5个机场:")
            for i, airport in enumerate(data.get('airports', [])[:5], 1):
                print(f"  {i}. {airport['icao']} ({airport['iata']}) - {airport['name']} ({airport['city']})")
            
            # 验证响应格式
            assert 'airports' in data, "响应缺少 'airports' 字段"
            assert isinstance(data['airports'], list), "'airports' 应该是列表"
            
            if len(data['airports']) > 0:
                first_airport = data['airports'][0]
                required_fields = ['icao', 'name', 'city', 'iata']
                for field in required_fields:
                    assert field in first_airport, f"机场数据缺少 '{field}' 字段"
                
                print("\n✅ 响应格式验证通过")
                print("\n完整响应示例（第一个机场）:")
                print(json.dumps(first_airport, ensure_ascii=False, indent=2))
        else:
            print(f"❌ 请求失败: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("❌ 无法连接到服务器，请确保服务已启动")
        print("   启动命令: python -m uvicorn app.main:app --reload")
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")


if __name__ == "__main__":
    test_airports_endpoint()
