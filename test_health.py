#!/usr/bin/env python3
import requests

try:
    r = requests.get('http://127.0.0.1:8000/api/v1/health')
    print(r.json())
except Exception as e:
    print(f'Error: {e}')
