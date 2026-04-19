"""
对话记忆服务 - Phase 4 核心

两层记忆：
1. Session Store: 单次对话的消息历史（会话级）
2. User Memory: 跨会话的用户偏好持久化（用户级）
3. Semantic Memory: SQLite FTS5 全文搜索语义记忆

存储策略：
- L1: 进程内 dict（即时访问）
- L2: SQLite FTS5（语义搜索）
- L3: 文件持久化 JSON（重启恢复）
- 无需 Redis，M3 MacBook 单机足够
"""
import json
import os
import sqlite3
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
    title: str = ""
    last_message: str = ""

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
        if not self.title and role == "user":
            self.title = content[:30]
        self.last_message = content[:50]
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
            "title": self.title,
            "last_message": self.last_message,
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
            title=d.get("title", ""),
            last_message=d.get("last_message", ""),
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
                "title": s.title or "未命名对话",
                "last_message": s.last_message or "",
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


# ==================== 语义记忆 (SQLite FTS5) ====================

class SemanticMemory:
    """
    语义记忆层 - SQLite FTS5 全文搜索

    存储结构：{content, importance(1-5), timestamp, session_id, tags}
    支持：关键词搜索 + importance 排序 + 时间衰减
    """

    def __init__(self, db_path: Optional[str] = None):
        self._db_path = db_path or os.path.join(os.getcwd(), ".cache", "memory", "semantic.db")
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path)
        self._conn.row_factory = sqlite3.Row
        self._init_tables()
        logger.info("SemanticMemory initialized: db=%s", self._db_path)

    def _init_tables(self):
        """初始化 FTS5 表"""
        cursor = self._conn.cursor()

        # 主表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                importance INTEGER DEFAULT 3,
                timestamp TEXT NOT NULL,
                session_id TEXT,
                user_id TEXT DEFAULT 'default',
                tags TEXT DEFAULT '',
                decay_factor REAL DEFAULT 1.0,
                created_at REAL NOT NULL
            )
        """)

        # FTS5 虚拟表
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                content,
                tags,
                content='memories',
                content_rowid='id',
                tokenize='unicode61'
            )
        """)

        # 触发器：同步 FTS 索引
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
                INSERT INTO memories_fts(rowid, content, tags)
                VALUES (new.id, new.content, new.tags);
            END
        """)
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
                INSERT INTO memories_fts(memories_fts, rowid, content, tags)
                VALUES ('delete', old.id, old.content, old.tags);
            END
        """)
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
                INSERT INTO memories_fts(memories_fts, rowid, content, tags)
                VALUES ('delete', old.id, old.content, old.tags);
                INSERT INTO memories_fts(rowid, content, tags)
                VALUES (new.id, new.content, new.tags);
            END
        """)

        self._conn.commit()

    def store_memory(
        self,
        content: str,
        importance: int = 3,
        session_id: Optional[str] = None,
        user_id: str = "default",
        tags: str = "",
    ) -> int:
        """
        存储一条记忆

        Args:
            content: 记忆内容
            importance: 重要性 (1-5)
            session_id: 关联会话ID
            user_id: 用户ID
            tags: 标签（逗号分隔）

        Returns:
            记忆ID
        """
        now = datetime.now()
        cursor = self._conn.cursor()
        cursor.execute(
            """INSERT INTO memories (content, importance, timestamp, session_id, user_id, tags, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (content, max(1, min(5, importance)), now.isoformat(), session_id, user_id, json.dumps(tags) if isinstance(tags, list) else tags, time.time()),
        )
        self._conn.commit()
        memory_id = cursor.lastrowid
        logger.info("Stored memory id=%d importance=%d", memory_id, importance)
        return memory_id

    def search_memory(
        self,
        query: str,
        user_id: str = "default",
        limit: int = 5,
        min_importance: int = 1,
    ) -> List[Dict[str, Any]]:
        """
        搜索相关记忆

        检索策略：FTS5 关键词匹配 + importance 排序 + 时间衰减

        Args:
            query: 搜索关键词
            user_id: 用户ID
            limit: 返回数量限制
            min_importance: 最低重要性

        Returns:
            记忆列表
        """
        cursor = self._conn.cursor()

        # FTS5 搜索（兼容中文：先试 MATCH，失败或无结果 fallback LIKE）
        rows = []
        try:
            cursor.execute("""
                SELECT m.id, m.content, m.importance, m.timestamp, m.session_id, m.tags
                FROM memories_fts fts
                JOIN memories m ON m.id = fts.rowid
                WHERE memories_fts MATCH ?
                  AND m.user_id = ?
                  AND m.importance >= ?
                ORDER BY m.importance DESC, m.created_at DESC
                LIMIT ?
            """, (query, user_id, min_importance, limit))
            rows = cursor.fetchall()
        except Exception:
            pass

        if not rows:
            cursor.execute("""
                SELECT id, content, importance, timestamp, session_id, tags
                FROM memories
                WHERE content LIKE ?
                  AND user_id = ?
                  AND importance >= ?
                ORDER BY importance DESC, created_at DESC
                LIMIT ?
            """, (f"%{query}%", user_id, min_importance, limit))
            rows = cursor.fetchall()

        results = []
        for row in rows:
            results.append({
                "id": row["id"],
                "content": row["content"],
                "importance": row["importance"],
                "timestamp": row["timestamp"],
                "session_id": row["session_id"],
                "tags": row["tags"],
            })

        return results

    def auto_summarize(
        self,
        session_id: str,
        messages: List[Dict[str, str]],
    ) -> str:
        """
        自动生成会话摘要

        简单实现：提取关键信息组合成摘要（不调用LLM）

        Args:
            session_id: 会话ID
            messages: 消息列表 [{"role": str, "content": str}]

        Returns:
            摘要文本
        """
        user_msgs = [m["content"] for m in messages if m.get("role") == "user"]
        assistant_msgs = [m["content"] for m in messages if m.get("role") == "assistant"]

        # 提取关键信息
        user_query = user_msgs[-1] if user_msgs else ""
        assistant_answer = assistant_msgs[-1] if assistant_msgs else ""

        # 截取摘要
        summary_parts = []
        if user_query:
            summary_parts.append(f"用户问题: {user_query[:200]}")
        if assistant_answer:
            # 提取前200字作为摘要
            summary_parts.append(f"回答要点: {assistant_answer[:300]}")

        summary = " | ".join(summary_parts) if summary_parts else f"会话 {session_id}"

        # 存储摘要为记忆
        self.store_memory(
            content=summary,
            importance=2,
            session_id=session_id,
            tags="auto_summary",
        )

        return summary

    def decay_importance(self, days_threshold: int = 7):
        """
        自动衰减旧记忆的重要性

        Args:
            days_threshold: 超过多少天的记忆开始衰减
        """
        cursor = self._conn.cursor()
        cutoff = time.time() - days_threshold * 86400

        cursor.execute("""
            UPDATE memories
            SET decay_factor = MAX(0.1, decay_factor * 0.9)
            WHERE created_at < ?
              AND importance <= 3
        """, (cutoff,))

        self._conn.commit()
        count = cursor.rowcount
        if count > 0:
            logger.info("Decayed %d memories older than %d days", count, days_threshold)

    def delete_old_memories(self, max_age_days: int = 90):
        """清理过期记忆"""
        cursor = self._conn.cursor()
        cutoff = time.time() - max_age_days * 86400
        cursor.execute("DELETE FROM memories WHERE created_at < ? AND importance <= 2", (cutoff,))
        self._conn.commit()
        count = cursor.rowcount
        if count > 0:
            logger.info("Deleted %d old memories", count)


# ==================== 全局单例 ====================

_memory_store: Optional[MemoryStore] = None
_semantic_memory: Optional[SemanticMemory] = None


def get_memory_store(storage_dir: Optional[str] = None) -> MemoryStore:
    """获取记忆存储单例"""
    global _memory_store
    if _memory_store is None:
        _memory_store = MemoryStore(storage_dir=storage_dir)
    return _memory_store


def get_semantic_memory() -> SemanticMemory:
    """获取语义记忆单例"""
    global _semantic_memory
    if _semantic_memory is None:
        _semantic_memory = SemanticMemory()
    return _semantic_memory
