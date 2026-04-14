#!/usr/bin/env python3
"""
测试反馈服务功能
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.feedback import FeedbackService

def test_feedback_service():
    """测试反馈服务"""
    print("测试反馈服务...")
    
    # 创建反馈服务实例
    feedback_service = FeedbackService(data_dir="test_data")
    
    # 测试提交反馈
    print("\n1. 测试提交反馈")
    result = feedback_service.submit_feedback(
        session_id="test-session-001",
        rating=4,
        report_id="report-001",
        corrections={
            "field": "wind_speed",
            "original": "15KT",
            "corrected": "18KT"
        },
        safety_issue=False,
        comment="风速解析准确，但建议考虑阵风因素"
    )
    print(f"提交结果: {result}")
    
    # 测试提交安全问题反馈
    print("\n2. 测试提交安全问题反馈")
    result = feedback_service.submit_feedback(
        session_id="test-session-002",
        rating=1,
        report_id="report-002",
        corrections={
            "field": "visibility",
            "original": "10km",
            "corrected": "5km"
        },
        safety_issue=True,
        comment="能见度数据严重错误，可能影响飞行安全"
    )
    print(f"安全问题提交结果: {result}")
    
    # 测试获取反馈统计
    print("\n3. 测试获取反馈统计")
    stats = feedback_service.get_feedback_stats()
    print(f"反馈统计: {stats}")
    
    # 测试获取安全问题列表
    print("\n4. 测试获取安全问题列表")
    safety_issues = feedback_service.get_safety_issues()
    print(f"安全问题数量: {len(safety_issues)}")
    for issue in safety_issues:
        print(f"  - {issue['feedback_id']}: {issue['comment']}")
    
    # 测试获取会话反馈
    print("\n5. 测试获取会话反馈")
    session_feedbacks = feedback_service.get_feedback_by_session("test-session-001")
    print(f"会话反馈数量: {len(session_feedbacks)}")
    
    print("\n所有测试完成!")

if __name__ == "__main__":
    test_feedback_service()