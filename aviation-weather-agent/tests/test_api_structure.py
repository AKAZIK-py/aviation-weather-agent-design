#!/usr/bin/env python3
"""测试API实际输出结构"""
import requests
import json

response = requests.post(
    'http://127.0.0.1:8000/api/v1/analyze',
    json={
        'metar_raw': 'METAR ZUUU 110800Z 00000KT 0300 FG VV002 M02/M02 Q1023',
        'role': 'pilot'
    }
)
print(json.dumps(response.json(), indent=2, ensure_ascii=False))
