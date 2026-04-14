import requests
import json

# 重试ZSSS
print('重试 ZSSS 机场分析...')
response = requests.post(
    'http://localhost:8000/api/v1/analyze',
    json={'airport_icao': 'ZSSS', 'role': 'ground_crew'},
    timeout=60
)
print(f'状态码: {response.status_code}')
if response.status_code == 200:
    print('成功！')
    data = response.json()
    print(json.dumps(data, indent=2, ensure_ascii=False))
else:
    print(f'失败: {response.json()}')
