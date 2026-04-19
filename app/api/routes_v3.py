"""
V3 API 路由 - Agent 模式

与 V2 的区别：
- V2: 8步硬编排 Pipeline，LLM 只做分析
- V3: ReAct Agent 循环，LLM 自主决策

向后兼容：V1/V2 API 不受影响
"""
import asyncio
import json
import re
from datetime import datetime
from typing import AsyncGenerator, Optional, List, Dict

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import logging

from app.agent.graph import run_agent
from app.services.auto_evaluator import evaluate_response

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
    6. 调整温度: { "query": "...", "temperature": 0.5 }

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
        temperature = request.get("temperature", 0.3)

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
            temperature=temperature,
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


# ==================== SSE 流式对话端点 ====================


def _sse_event(event_type: str, data: dict) -> str:
    """构造 SSE 事件字符串。"""
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _generate_sse_stream(request: dict) -> AsyncGenerator[str, None]:
    """生成 SSE 事件流。"""
    try:
        query = request.get("query", "")
        icao = request.get("icao") or request.get("airport_icao")
        metar_raw = request.get("metar_raw")
        role = request.get("role", request.get("user_role", "pilot"))
        provider = request.get("provider")
        history = request.get("history", [])
        max_iterations = request.get("max_iterations", 5)
        session_id = request.get("session_id")
        # 自动创建 session_id（前端首次对话未传时）
        if not session_id:
            import uuid
            session_id = f"session-{uuid.uuid4().hex[:12]}"
        user_id = request.get("user_id", "default")
        temperature = request.get("temperature", 0.3)

        if not query and not icao and not metar_raw:
            yield _sse_event("error", {"message": "至少提供 query、icao、metar_raw 之一"})
            yield _sse_event("done", {"status": "error"})
            return

        # 1. thinking event
        yield _sse_event("thinking", {"content": "Agent 正在分析..."})

        # 2. Run agent
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
            temperature=temperature,
        )

        if not result.get("success"):
            yield _sse_event("error", {"message": result.get("error", "Agent 运行失败")})
            yield _sse_event("done", {"status": "error"})
            return

        # 3. tool_call / tool_result events
        tool_calls = result.get("tool_calls", [])
        for tc in tool_calls:
            tool_name = tc.get("tool", "unknown")
            args = tc.get("args", {})
            tc_result = tc.get("result", "")

            yield _sse_event("tool_call", {"tool": tool_name, "args": args})
            await asyncio.sleep(0.05)
            yield _sse_event("tool_result", {"tool": tool_name, "result": tc_result[:500]})
            await asyncio.sleep(0.05)

        # 4. answer event
        answer = result.get("answer", "")
        yield _sse_event("answer", {"content": answer})

        # 5. eval event
        eval_scores = evaluate_response(
            query=query or "",
            answer=answer,
            role=role,
            tool_calls=tool_calls,
        )
        yield _sse_event("eval", eval_scores)

        # 5b. 存储评测结果
        from app.services.eval_store import record_eval_result
        token_usage = result.get("token_usage", {})
        record_eval_result(
            session_id=session_id or "",
            query=query or "",
            role=role,
            eval_scores=eval_scores,
            processing_time_ms=result.get("processing_time_ms", 0),
            tool_calls_count=len(tool_calls),
            prompt_tokens=token_usage.get("prompt_tokens", 0),
            completion_tokens=token_usage.get("completion_tokens", 0),
            provider=result.get("provider", ""),
            model=result.get("model", ""),
        )

        # 5c. eval 不通过时自动写入 badcase（过滤无效查询）
        _query_stripped = (query or "").strip()
        _is_invalid_query = (
            len(_query_stripped) < 3
            or _query_stripped.isdigit()
            or re.match(r"^[a-zA-Z]$", _query_stripped) is not None
        )
        if not _is_invalid_query and (
            not eval_scores.get("task_complete") or eval_scores.get("hallucination_rate", 0) > 0.3
        ):
            from app.evaluation.badcase_manager import BadcaseManager
            manager = BadcaseManager()
            manager.add_badcase(
                category="task_not_finished" if not eval_scores.get("task_complete") else "hallucination",
                input_data={
                    "metar": result.get("metar_raw", ""),
                    "role": role,
                    "query": query or "",
                },
                expected={"behavior": "task_complete with key info and usable output"},
                actual={
                    "output": answer,
                    "eval_scores": eval_scores,
                },
                source="auto_eval",
                notes=f"eval_scores={eval_scores}",
            )

        # 6. 记录到实时指标
        from app.services.live_metrics import record_request
        token_usage = result.get("token_usage", {})
        record_request(
            role=role,
            provider=result.get("provider", "unknown"),
            model=result.get("model", "unknown"),
            status="success",
            latency_ms=result.get("processing_time_ms", 0),
            prompt_tokens=token_usage.get("prompt_tokens", 0),
            completion_tokens=token_usage.get("completion_tokens", 0),
            iterations=result.get("iterations", 1),
            query=query or "",
            session_id=session_id or "",
        )

        # 7. done
        yield _sse_event("done", {"status": "success", "session_id": result.get("session_id")})

    except Exception as e:
        logger.error(f"SSE stream error: {e}", exc_info=True)
        from app.services.live_metrics import record_request
        record_request(
            role=request.get("role", "pilot"),
            provider="unknown",
            model="unknown",
            status="error",
            latency_ms=0,
            query=request.get("query", ""),
        )
        yield _sse_event("error", {"message": str(e)})
        yield _sse_event("done", {"status": "error"})


@router.post("/chat/stream")
async def agent_chat_stream(request: dict):
    """SSE 流式对话端点。

    请求体同 /chat: { query, role, icao, metar_raw, session_id, ... }

    SSE event 格式:
      event: thinking    data: {"content":"Agent 正在分析..."}
      event: tool_call   data: {"tool":"fetch_metar","args":{"icao":"ZSSS"}}
      event: tool_result data: {"tool":"fetch_metar","result":"METAR ZSSS..."}
      event: answer      data: {"content":"虹桥目前能见度800米..."}
      event: eval        data: {"task_complete":true,"key_info_hit":"3/3",...}
      event: done        data: {"status":"success"}
    """
    return StreamingResponse(
        _generate_sse_stream(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


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


# ==================== 语义记忆端点 ====================

@router.post("/memory/{user_id}/search")
async def search_semantic_memory(user_id: str, request: dict):
    """
    搜索语义记忆

    Body: { "query": "ZSSS天气", "limit": 5, "min_importance": 1 }
    """
    from app.services.memory import get_semantic_memory
    mem = get_semantic_memory()

    query = request.get("query", "")
    if not query:
        raise HTTPException(status_code=400, detail="query 不能为空")

    limit = request.get("limit", 5)
    min_importance = request.get("min_importance", 1)

    results = mem.search_memory(
        query=query,
        user_id=user_id,
        limit=limit,
        min_importance=min_importance,
    )

    return {"query": query, "results": results, "count": len(results)}


@router.post("/memory/{user_id}/store")
async def store_semantic_memory(user_id: str, request: dict):
    """
    存储语义记忆

    Body: { "content": "ZSSS能见度良好，适合VFR飞行", "importance": 4, "tags": "weather,zsss" }
    """
    from app.services.memory import get_semantic_memory
    mem = get_semantic_memory()

    content = request.get("content", "")
    if not content:
        raise HTTPException(status_code=400, detail="content 不能为空")

    importance = request.get("importance", 3)
    tags = request.get("tags", "")
    session_id = request.get("session_id")

    memory_id = mem.store_memory(
        content=content,
        importance=importance,
        session_id=session_id,
        user_id=user_id,
        tags=tags,
    )

    return {"stored": True, "memory_id": memory_id}


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
