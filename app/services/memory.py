"""
对话记忆服务 - Phase 4 核心

两层记忆：
1. Session Store: 单次对话的消息历史（会话级）
2. User Memory: 跨会话的用户偏好持久化（用户级）

存储策略：
- L1: 进程内 dict（即时访问）
- L3: 文件持久化 JSON（重启恢复）
- 无需 Redis，M3 MacBook 单机足够
"""
import json
import os
import time
import logging
import hashlib
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)


# ==================== 数据模型 ====================

@dataclass
class Message:
    """单条对话消息"""
    role: str          # "user" | "assistant" | "tool"
    content: str
    timestamp: str = ""
    tool_calls: Optional[List[Dict]] = None
    tool_call_id: Optional[str] = None

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        d = {"role": self.role, "content": self.content, "timestamp": self.timestamp}
        if self.tool_calls:
            d["tool_calls"] = self.tool_calls
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        return d

    @classmethod
    def from_dict(cls, d: Dict) -> "Message":
        return cls(
            role=d["role"],
            content=d.get("content", ""),
            timestamp=d.get("timestamp", ""),
            tool_calls=d.get("tool_calls"),
            tool_call_id=d.get("tool_call_id"),
        )


@dataclass
class Session:
    """对话会话"""
    session_id: str
    user_id: str = "default"
    messages: List[Message] = field(default_factory=list)
    created_at: str = ""
    last_active: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        now = datetime.now().isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.last_active:
            self.last_active = now

    def add_message(self, role: str, content: str, **kwargs):
        """添加消息并更新活跃时间"""
        msg = Message(role=role, content=content, **kwargs)
        self.messages.append(msg)
        self.last_active = datetime.now().isoformat()
        return msg

    def get_recent_messages(self, max_count: int = 20) -> List[Message]:
        """获取最近N条消息（避免上下文溢出）"""
        return self.messages[-max_count:]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "messages": [m.to_dict() for m in self.messages],
            "created_at": self.created_at,
            "last_active": self.last_active,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "Session":
        return cls(
            session_id=d["session_id"],
            user_id=d.get("user_id", "default"),
            messages=[Message.from_dict(m) for m in d.get("messages", [])],
            created_at=d.get("created_at", ""),
            last_active=d.get("last_active", ""),
            metadata=d.get("metadata", {}),
        )


@dataclass
class UserMemory:
    """跨会话用户偏好"""
    user_id: str = "default"
    preferences: Dict[str, Any] = field(default_factory=dict)
    # 常见字段：
    #   preferred_role: str      # pilot/dispatcher/forecaster/ground_crew
    #   aircraft_type: str       # heavy/regional/helicopter
    #   home_base: str           # ICAO 如 ZSPD
    #   frequent_airports: list  # 常用机场列表
    #   flight_phase: str        # 默认飞行阶段
    updated_at: str = ""

    def __post_init__(self):
        if not self.updated_at:
            self.updated_at = datetime.now().isoformat()

    def get(self, key: str, default=None):
        return self.preferences.get(key, default)

    def set(self, key: str, value: Any):
        self.preferences[key] = value
        self.updated_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "preferences": self.preferences,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "UserMemory":
        return cls(
            user_id=d.get("user_id", "default"),
            preferences=d.get("preferences", {}),
            updated_at=d.get("updated_at", ""),
        )


# ==================== 存储引擎 ====================

class MemoryStore:
    """
    对话记忆存储引擎

    L1: 进程内 dict（即时读写）
    L3: 文件 JSON（持久化，启动时加载）
    """

    def __init__(self, storage_dir: Optional[str] = None):
        self._sessions: Dict[str, Session] = {}
        self._user_memories: Dict[str, UserMemory] = {}

        # 持久化目录
        self._storage_dir = Path(
            storage_dir or os.path.join(os.getcwd(), ".cache", "memory")
        )
        self._sessions_dir = self._storage_dir / "sessions"
        self._users_dir = self._storage_dir / "users"
        self._sessions_dir.mkdir(parents=True, exist_ok=True)
        self._users_dir.mkdir(parents=True, exist_ok=True)

        # 启动时加载持久化数据
        self._load_all()
        logger.info(
            f"MemoryStore initialized: "
            f"{len(self._sessions)} sessions, "
            f"{len(self._user_memories)} users, "
            f"dir={self._storage_dir}"
        )

    # ---------- Session 操作 ----------

    def get_or_create_session(
        self,
        session_id: Optional[str] = None,
        user_id: str = "default",
    ) -> Session:
        """获取或创建会话"""
        if session_id and session_id in self._sessions:
            session = self._sessions[session_id]
            session.last_active = datetime.now().isoformat()
            return session

        # 生成新 session_id
        if not session_id:
            session_id = self._generate_session_id(user_id)

        session = Session(session_id=session_id, user_id=user_id)
        self._sessions[session_id] = session
        self._save_session(session)
        logger.info(f"Created new session: {session_id} (user={user_id})")
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """获取已有会话"""
        return self._sessions.get(session_id)

    def save_session(self, session: Session):
        """保存会话到持久化存储"""
        session.last_active = datetime.now().isoformat()
        self._sessions[session.session_id] = session
        self._save_session(session)

    def list_sessions(
        self,
        user_id: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """列出会话摘要"""
        sessions = list(self._sessions.values())
        if user_id:
            sessions = [s for s in sessions if s.user_id == user_id]

        # 按最近活跃排序
        sessions.sort(key=lambda s: s.last_active, reverse=True)

        return [
            {
                "session_id": s.session_id,
                "user_id": s.user_id,
                "message_count": len(s.messages),
                "created_at": s.created_at,
                "last_active": s.last_active,
            }
            for s in sessions[:limit]
        ]

    def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        if session_id in self._sessions:
            del self._sessions[session_id]
            path = self._sessions_dir / f"{session_id}.json"
            path.unlink(missing_ok=True)
            logger.info(f"Deleted session: {session_id}")
            return True
        return False

    # ---------- UserMemory 操作 ----------

    def get_user_memory(self, user_id: str = "default") -> UserMemory:
        """获取用户记忆（不存在则创建空的）"""
        if user_id not in self._user_memories:
            self._user_memories[user_id] = UserMemory(user_id=user_id)
        return self._user_memories[user_id]

    def save_user_memory(self, memory: UserMemory):
        """保存用户记忆"""
        memory.updated_at = datetime.now().isoformat()
        self._user_memories[memory.user_id] = memory
        self._save_user_memory(memory)

    # ---------- 持久化 ----------

    def _save_session(self, session: Session):
        """持久化单个会话"""
        path = self._sessions_dir / f"{session.session_id}.json"
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(session.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save session {session.session_id}: {e}")

    def _save_user_memory(self, memory: UserMemory):
        """持久化用户记忆"""
        path = self._users_dir / f"{memory.user_id}.json"
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(memory.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save user memory {memory.user_id}: {e}")

    def _load_all(self):
        """启动时加载所有持久化数据"""
        # 加载会话
        if self._sessions_dir.exists():
            for path in self._sessions_dir.glob("*.json"):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    session = Session.from_dict(data)
                    self._sessions[session.session_id] = session
                except Exception as e:
                    logger.warning(f"Failed to load session {path.name}: {e}")

        # 加载用户记忆
        if self._users_dir.exists():
            for path in self._users_dir.glob("*.json"):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    memory = UserMemory.from_dict(data)
                    self._user_memories[memory.user_id] = memory
                except Exception as e:
                    logger.warning(f"Failed to load user memory {path.name}: {e}")

    def cleanup_old_sessions(self, max_age_hours: int = 24):
        """清理过期会话"""
        cutoff = time.time() - max_age_hours * 3600
        to_delete = []
        for sid, session in self._sessions.items():
            try:
                last = datetime.fromisoformat(session.last_active).timestamp()
                if last < cutoff:
                    to_delete.append(sid)
            except (ValueError, TypeError):
                pass

        for sid in to_delete:
            self.delete_session(sid)

        if to_delete:
            logger.info(f"Cleaned up {len(to_delete)} expired sessions")

    @staticmethod
    def _generate_session_id(user_id: str) -> str:
        """生成唯一会话ID"""
        ts = datetime.now().isoformat()
        raw = f"{user_id}:{ts}:{os.getpid()}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ==================== 全局单例 ====================

_memory_store: Optional[MemoryStore] = None


def get_memory_store(storage_dir: Optional[str] = None) -> MemoryStore:
    """获取记忆存储单例"""
    global _memory_store
    if _memory_store is None:
        _memory_store = MemoryStore(storage_dir=storage_dir)
    return _memory_store
