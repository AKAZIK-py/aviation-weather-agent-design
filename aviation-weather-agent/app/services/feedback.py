"""
用户反馈服务 - 收集和管理用户对天气分析的反馈
"""
import json
import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class FeedbackService:
    """用户反馈服务类"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.feedback_file = self.data_dir / "feedback.jsonl"
        self.stats_cache = {}
        
    def submit_feedback(
        self,
        session_id: str,
        rating: int,
        report_id: Optional[str] = None,
        corrections: Optional[Dict[str, Any]] = None,
        safety_issue: bool = False,
        comment: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        提交用户反馈
        
        Args:
            session_id: 会话ID
            rating: 评分 (1-5)
            report_id: 报告ID (可选)
            corrections: 更正数据，格式: {"field": "wind_speed", "original": "15KT", "corrected": "18KT"}
            safety_issue: 是否涉及安全问题
            comment: 用户评论
            
        Returns:
            包含反馈ID的响应
        """
        # 验证评分
        if not 1 <= rating <= 5:
            raise ValueError("评分必须在1-5之间")
            
        # 生成反馈ID
        feedback_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        # 构建反馈记录
        feedback_record = {
            "feedback_id": feedback_id,
            "session_id": session_id,
            "report_id": report_id,
            "rating": rating,
            "corrections": corrections or {},
            "safety_issue": safety_issue,
            "comment": comment,
            "timestamp": timestamp,
            "status": "pending_review" if safety_issue else "recorded"
        }
        
        # 记录到文件
        try:
            with open(self.feedback_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(feedback_record, ensure_ascii=False) + "\n")
            
            logger.info(f"反馈已记录: {feedback_id}, 评分: {rating}, 安全问题: {safety_issue}")
            
            # 如果是安全问题，记录特殊日志
            if safety_issue:
                logger.warning(f"安全问题反馈: {feedback_id}, 会话: {session_id}")
                self._log_safety_issue(feedback_record)
                
            return {
                "success": True,
                "feedback_id": feedback_id,
                "message": "反馈已提交成功",
                "timestamp": timestamp
            }
            
        except Exception as e:
            logger.error(f"保存反馈失败: {e}")
            raise RuntimeError(f"保存反馈失败: {str(e)}")
    
    def _log_safety_issue(self, feedback_record: Dict[str, Any]):
        """记录安全问题到单独文件"""
        safety_file = self.data_dir / "safety_issues.jsonl"
        try:
            with open(safety_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(feedback_record, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"记录安全问题失败: {e}")
    
    def get_feedback_stats(self) -> Dict[str, Any]:
        """
        获取反馈统计信息
        
        Returns:
            包含统计信息的字典
        """
        if not self.feedback_file.exists():
            return self._empty_stats()
        
        try:
            feedbacks = []
            with open(self.feedback_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        feedbacks.append(json.loads(line))
            
            if not feedbacks:
                return self._empty_stats()
            
            # 计算统计数据
            total_feedbacks = len(feedbacks)
            ratings = [f["rating"] for f in feedbacks]
            avg_rating = sum(ratings) / total_feedbacks if total_feedbacks > 0 else 0
            
            # 评分分布
            rating_distribution = {i: 0 for i in range(1, 6)}
            for rating in ratings:
                rating_distribution[rating] += 1
            
            # 安全问题统计
            safety_issues = [f for f in feedbacks if f.get("safety_issue", False)]
            safety_issues_count = len(safety_issues)
            
            # 更正统计
            corrections_count = sum(1 for f in feedbacks if f.get("corrections"))
            
            # 最近24小时反馈
            recent_feedbacks = []
            now = datetime.now()
            for f in feedbacks:
                try:
                    feedback_time = datetime.fromisoformat(f["timestamp"])
                    if (now - feedback_time).total_seconds() < 86400:  # 24小时
                        recent_feedbacks.append(f)
                except:
                    continue
            
            stats = {
                "total_feedbacks": total_feedbacks,
                "average_rating": round(avg_rating, 2),
                "rating_distribution": rating_distribution,
                "safety_issues_count": safety_issues_count,
                "corrections_count": corrections_count,
                "recent_24h_count": len(recent_feedbacks),
                "last_updated": datetime.now().isoformat()
            }
            
            # 缓存统计结果
            self.stats_cache = stats
            return stats
            
        except Exception as e:
            logger.error(f"获取反馈统计失败: {e}")
            return self._empty_stats()
    
    def _empty_stats(self) -> Dict[str, Any]:
        """返回空统计"""
        return {
            "total_feedbacks": 0,
            "average_rating": 0,
            "rating_distribution": {i: 0 for i in range(1, 6)},
            "safety_issues_count": 0,
            "corrections_count": 0,
            "recent_24h_count": 0,
            "last_updated": datetime.now().isoformat()
        }
    
    def get_safety_issues(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取安全问题列表"""
        safety_file = self.data_dir / "safety_issues.jsonl"
        if not safety_file.exists():
            return []
        
        try:
            issues = []
            with open(safety_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        issues.append(json.loads(line))
            
            # 按时间倒序排序
            issues.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            return issues[:limit]
            
        except Exception as e:
            logger.error(f"获取安全问题失败: {e}")
            return []
    
    def get_feedback_by_session(self, session_id: str) -> List[Dict[str, Any]]:
        """获取指定会话的所有反馈"""
        if not self.feedback_file.exists():
            return []
        
        try:
            session_feedbacks = []
            with open(self.feedback_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        feedback = json.loads(line)
                        if feedback.get("session_id") == session_id:
                            session_feedbacks.append(feedback)
            
            return session_feedbacks
            
        except Exception as e:
            logger.error(f"获取会话反馈失败: {e}")
            return []


# 创建全局实例
feedback_service = FeedbackService()


def get_feedback_service() -> FeedbackService:
    """获取反馈服务实例"""
    return feedback_service