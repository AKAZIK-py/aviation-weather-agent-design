"""
V3 API 路由 - Agent 模式

与 V2 的区别：
- V2: 8步硬编排 Pipeline，LLM 只做分析
- V3: ReAct Agent 循环，LLM 自主决策

向后兼容：V1/V2 API 不受影响
"""
from fastapi import APIRouter, HTTPException
from datetime import datetime
import time
import logging
from typing import Optional, List, Dict

from app.agent.graph import run_agent

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/chat")
async def agent_chat(request: dict):
    """
    V3 Agent 对话端点

    支持：
    1. 单轮分析: { "query": "ZBAA能落地吗", "role": "pilot" }
    2. 多轮对话: { "query": "那2小时后呢", "role": "pilot", "session_id": "abc123" }
    3. 直接METAR: { "metar_raw": "METAR ...", "query": "分析一下", "role": "pilot" }
    4. 指定provider: { "query": "...", "provider": "deepseek" }
    5. 带会话记忆: { "query": "...", "session_id": "abc123", "user_id": "u001" }

    与V2的区别：
    - 不需要指定 airport_icao + user_role 的固定组合
    - LLM 自己决定需要获取哪些数据、调用什么工具
    - 支持多轮对话上下文（通过 session_id 自动管理）
    - 输出格式由 LLM 根据问题自适应

    Returns:
        {
            "success": true,
            "answer": "LLM的分析回答",
            "tool_calls": [{"tool": "fetch_metar", "args": {...}, "result": "..."}],
            "role": "pilot",
            "iterations": 2,
            "processing_time_ms": 3500,
            "session_id": "abc123"   // 启用记忆时返回
        }
    """
    try:
        query = request.get("query", "")
        icao = request.get("icao") or request.get("airport_icao")
        metar_raw = request.get("metar_raw")
        role = request.get("role", request.get("user_role", "pilot"))
        provider = request.get("provider")
        history = request.get("history", [])
        max_iterations = request.get("max_iterations", 5)
        session_id = request.get("session_id")
        user_id = request.get("user_id", "default")

        if not query and not icao and not metar_raw:
            raise HTTPException(
                status_code=400,
                detail="至少提供 query、icao、metar_raw 之一"
            )

        # 运行 Agent（传入 session 记忆参数）
        result = await run_agent(
            user_query=query,
            icao=icao,
            metar_raw=metar_raw,
            role=role,
            provider=provider,
            conversation_history=history,
            max_iterations=max_iterations,
            session_id=session_id,
            user_id=user_id,
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"V3 chat 异常: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "answer": f"服务异常: {str(e)}",
            "timestamp": datetime.now().isoformat(),
        }


# ==================== 会话管理端点 ====================

@router.get("/sessions")
async def list_sessions(user_id: str = None, limit: int = 10):
    """列出会话摘要"""
    from app.services.memory import get_memory_store
    store = get_memory_store()
    return {
        "sessions": store.list_sessions(user_id=user_id, limit=limit),
    }


@router.get("/sessions/{session_id}")
async def get_session_detail(session_id: str):
    """获取会话详情（含完整消息历史）"""
    from app.services.memory import get_memory_store
    store = get_memory_store()
    session = store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"会话 {session_id} 不存在")
    return session.to_dict()


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """删除会话"""
    from app.services.memory import get_memory_store
    store = get_memory_store()
    ok = store.delete_session(session_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"会话 {session_id} 不存在")
    return {"deleted": True, "session_id": session_id}


@router.get("/memory/{user_id}")
async def get_user_memory(user_id: str):
    """获取用户跨会话记忆（偏好设置）"""
    from app.services.memory import get_memory_store
    store = get_memory_store()
    memory = store.get_user_memory(user_id)
    return memory.to_dict()


@router.put("/memory/{user_id}")
async def update_user_memory(user_id: str, request: dict):
    """
    更新用户跨会话记忆

    Body: { "preferences": { "preferred_role": "pilot", "home_base": "ZSPD", ... } }
    """
    from app.services.memory import get_memory_store
    store = get_memory_store()
    memory = store.get_user_memory(user_id)

    prefs = request.get("preferences", {})
    for key, value in prefs.items():
        memory.set(key, value)

    store.save_user_memory(memory)
    return memory.to_dict()


@router.get("/roles")
async def get_available_roles():
    """获取可用的角色列表"""
    from app.agent.prompts import ROLE_CONSTRAINTS
    return {
        "roles": [
            {
                "id": role_id,
                "name": constraints["name"],
                "identity": constraints["identity"],
                "focus_count": len(constraints["focus"]),
            }
            for role_id, constraints in ROLE_CONSTRAINTS.items()
        ]
    }


@router.get("/health")
async def agent_health():
    """Agent 模式健康检查"""
    try:
        from app.agent.graph import get_langchain_llm
        from app.tools.weather_tools import get_all_tools

        tools = get_all_tools()
        tool_names = [t.name for t in tools]

        return {
            "status": "healthy",
            "mode": "agent",
            "tools_available": tool_names,
            "tool_count": len(tool_names),
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        return {
            "status": "degraded",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }
