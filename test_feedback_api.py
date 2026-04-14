#!/usr/bin/env python3
"""
测试反馈API端点
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient
from app.main import app

def test_feedback_api():
    """测试反馈API端点"""
    print("测试反馈API端点...")
    
    client = TestClient(app)
    
    # 测试提交反馈
    print("\n1. 测试提交反馈")
    feedback_data = {
        "session_id": "test-session-api-001",
        "rating": 4,
        "report_id": "report-api-001",
        "corrections": {
            "field": "wind_speed",
            "original": "15KT",
            "corrected": "18KT"
        },
        "safety_issue": False,
        "comment": "API测试反馈"
    }
    
    response = client.post("/api/v1/feedback", json=feedback_data)
    print(f"状态码: {response.status_code}")
    print(f"响应: {response.json()}")
    
    # 测试提交安全问题反馈
    print("\n2. 测试提交安全问题反馈")
    safety_feedback_data = {
        "session_id": "test-session-api-002",
        "rating": 1,
        "report_id": "report-api-002",
        "corrections": {
            "field": "visibility",
            "original": "10km",
            "corrected": "5km"
        },
        "safety_issue": True,
        "comment": "API测试安全问题"
    }
    
    response = client.post("/api/v1/feedback", json=safety_feedback_data)
    print(f"状态码: {response.status_code}")
    print(f"响应: {response.json()}")
    
    # 测试获取反馈统计
    print("\n3. 测试获取反馈统计")
    response = client.get("/api/v1/feedback/stats")
    print(f"状态码: {response.status_code}")
    print(f"响应: {response.json()}")
    
    # 测试获取安全问题列表
    print("\n4. 测试获取安全问题列表")
    response = client.get("/api/v1/feedback/safety-issues")
    print(f"状态码: {response.status_code}")
    print(f"响应: {response.json()}")
    
    # 测试健康检查
    print("\n5. 测试健康检查")
    response = client.get("/api/v1/health")
    print(f"状态码: {response.status_code}")
    print(f"响应: {response.json()}")
    
    print("\n所有API测试完成!")

if __name__ == "__main__":
    test_feedback_api()