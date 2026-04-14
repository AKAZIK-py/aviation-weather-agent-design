"""
Agent 图 - 使用 LangGraph create_react_agent 构建真正的 Agent 循环

核心变化：
- 从 8 步硬编排 → LLM 自主决策循环
- 从固定工具调用顺序 → LLM 自主选择工具
- 从单次 LLM 调用 → ReAct 循环（思考→行动→观察→再思考）
"""
import logging
from typing import Dict, Any, Optional, List, Annotated, Sequence
from datetime import datetime

from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    SystemMessage,
    AIMessage,
    ToolMessage,
)
from langchain_core.tools import BaseTool
from langgraph.prebuilt import create_react_agent
from langgraph.graph import StateGraph, MessagesState, END
from langgraph.prebuilt.tool_node import ToolNode

from app.tools.weather_tools import get_all_tools
from app.agent.prompts import build_system_prompt, build_first_message, ROLE_CONSTRAINTS

logger = logging.getLogger(__name__)


# ==================== LLM 适配层 ====================

def get_langchain_llm(provider: str = None, temperature: float = 0.3):
    """
    获取 LangChain 兼容的 LLM 实例

    优先使用 OpenAI 兼容端点（百度千帆 V2、DeepSeek、Moonshot 都支持），
    如果都不可用则使用 Anthropic。

    Args:
        provider: 指定 provider，None 则自动选择
        temperature: 温度参数
    """
    from app.core.config import get_settings
    settings = get_settings()

    # 自动选择 provider
    if provider is None:
        # 优先使用 OpenAI 兼容且 tool_calling 支持好的 provider
        if settings.openai_api_key:
            provider = "openai"
        elif settings.deepseek_api_key:
            # DeepSeek 原生支持 OpenAI tool_calling 格式
            provider = "deepseek"
        elif settings.anthropic_api_key:
            provider = "anthropic"
        elif settings.qianfan_api_base_url and settings.qianfan_api_key:
            # 千帆V2 作为 fallback（tool_calling 兼容性待验证）
            provider = "qianfan_v2"
        else:
            raise ValueError("没有可用的 LLM Provider，请在 .env 中配置")

    logger.info(f"Agent使用LLM Provider: {provider}")

    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=temperature,
            max_tokens=2500,
        )

    elif provider == "qianfan_v2":
        # 百度千帆 V2 API - OpenAI 兼容模式
        from langchain_openai import ChatOpenAI
        base_url = settings.qianfan_api_base_url.rstrip('/')
        # 如果URL已经包含chat/completions路径，不再追加
        if not base_url.endswith('/chat/completions'):
            base_url = f"{base_url}/chat/completions"
        return ChatOpenAI(
            model=settings.qianfan_model,
            api_key=settings.qianfan_api_key,
            base_url=base_url,
            temperature=temperature,
            max_tokens=2500,
        )

    elif provider == "deepseek":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=settings.deepseek_model or "deepseek-chat",
            api_key=settings.deepseek_api_key,
            base_url="https://api.deepseek.com/v1",
            temperature=temperature,
            max_tokens=2500,
        )

    elif provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=settings.anthropic_model,
            api_key=settings.anthropic_api_key,
            temperature=temperature,
            max_tokens=2500,
        )

    else:
        raise ValueError(f"不支持的 Provider: {provider}")


# ==================== Agent 创建 ====================

def create_aviation_agent(
    role: str = "pilot",
    provider: str = None,
    max_iterations: int = 5,
    temperature: float = 0.3,
):
    """
    创建航空气象 Agent

    使用 LangGraph create_react_agent 构建 ReAct 循环：
    LLM思考 → 调用工具 → 观察结果 → 继续思考 → ... → 最终回答

    Args:
        role: 用户角色 (pilot/dispatcher/forecaster/ground_crew)
        provider: LLM provider，None则自动选择
        max_iterations: 最大迭代次数，防止无限循环
        temperature: LLM温度

    Returns:
        编译好的 LangGraph agent
    """
    if role not in ROLE_CONSTRAINTS:
        logger.warning(f"未知角色 '{role}'，使用默认 'pilot'")
        role = "pilot"

    # 1. 获取 LLM
    llm = get_langchain_llm(provider=provider, temperature=temperature)

    # 2. 获取工具
    tools = get_all_tools()

    # 3. 构建系统提示词
    system_prompt = build_system_prompt(role=role)

    # 4. 创建 ReAct Agent
    # 兼容新旧 langgraph API（state_modifier vs prompt）
    try:
        agent = create_react_agent(
            model=llm,
            tools=tools,
            prompt=system_prompt,
        )
    except TypeError:
        # 旧版 langgraph 使用 state_modifier
        agent = create_react_agent(
            model=llm,
            tools=tools,
            state_modifier=system_prompt,
        )

    return agent


# ==================== 高层封装 ====================

async def run_agent(
    user_query: str,
    icao: str = None,
    metar_raw: str = None,
    role: str = "pilot",
    provider: str = None,
    conversation_history: List[Dict[str, str]] = None,
    max_iterations: int = 5,
    session_id: str = None,
    user_id: str = "default",
) -> Dict[str, Any]:
    """
    运行航空气象 Agent

    这是对外的高层接口，替代原来的 workflow_engine.run_full_workflow。

    Args:
        user_query: 用户自然语言查询
        icao: 机场ICAO代码（可选）
        metar_raw: 原始METAR报文（可选）
        role: 用户角色
        provider: LLM provider
        conversation_history: 对话历史 [{"role": "user/assistant", "content": "..."}]
        max_iterations: 最大工具调用迭代次数
        session_id: 会话ID（可选，传入则启用会话记忆）
        user_id: 用户ID（用于跨会话记忆）

    Returns:
        {
            "success": bool,
            "answer": str,           # Agent的最终回答
            "tool_calls": [...],     # 工具调用记录
            "messages": [...],       # 完整消息历史
            "iterations": int,       # 实际迭代次数
            "processing_time_ms": float,
            "role": str,
            "provider": str,
            "session_id": str,       # 会话ID（启用记忆时返回）
        }
    """
    start_time = datetime.now()

    # ---- Phase 4: 对话记忆集成 ----
    memory_store = None
    session = None
    if session_id is not None:
        from app.services.memory import get_memory_store
        memory_store = get_memory_store()
        session = memory_store.get_or_create_session(session_id, user_id=user_id)

        # 从用户记忆中补充默认值
        user_mem = memory_store.get_user_memory(user_id)
        if not role or role == "pilot":
            preferred = user_mem.get("preferred_role")
            if preferred:
                role = preferred
        if not icao:
            home_base = user_mem.get("home_base")
            if home_base and not metar_raw:
                icao = home_base

    try:
        # 1. 创建 Agent
        agent = create_aviation_agent(
            role=role,
            provider=provider,
            max_iterations=max_iterations,
        )

        # 2. 构建消息列表
        messages: List[BaseMessage] = []

        # 优先级: conversation_history 参数 > session 记忆
        history_source = conversation_history
        if not history_source and session:
            # 从 session 取最近的消息（跳过最后一条，那是当前消息）
            recent = session.get_recent_messages(max_count=20)
            history_source = [m.to_dict() for m in recent]

        if history_source:
            for msg in history_source:
                if msg["role"] == "user":
                    messages.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "assistant":
                    messages.append(AIMessage(content=msg["content"]))

        # 构建当前用户消息
        first_message = build_first_message(
            user_query=user_query,
            icao=icao,
            metar_raw=metar_raw,
            user_role=role,
        )
        messages.append(HumanMessage(content=first_message))

        # 记录用户消息到 session
        if session:
            session.add_message("user", user_query or first_message)

        # 3. 运行 Agent
        logger.info(f"[Agent] 开始运行: role={role}, query={user_query[:50]}...")

        result = await agent.ainvoke(
            {"messages": messages},
            config={"recursion_limit": max_iterations * 2 + 1},  # 每轮最多1次思考+1次工具调用
        )

        # 4. 解析结果
        all_messages = result.get("messages", [])
        tool_calls = []
        iterations = 0

        for msg in all_messages:
            if isinstance(msg, AIMessage) and msg.tool_calls:
                iterations += 1
                for tc in msg.tool_calls:
                    tool_calls.append({
                        "tool": tc["name"],
                        "args": tc["args"],
                        "id": tc["id"],
                    })
            elif isinstance(msg, ToolMessage):
                # 找到对应的工具调用结果
                for tc in reversed(tool_calls):
                    if tc.get("id") == msg.tool_call_id:
                        tc["result"] = msg.content[:500]  # 截断长结果
                        break

        # 获取最终回答（最后一条非工具消息）
        final_answer = ""
        for msg in reversed(all_messages):
            if isinstance(msg, AIMessage) and not msg.tool_calls:
                final_answer = msg.content
                break

        # 5. 构建响应
        end_time = datetime.now()
        processing_ms = (end_time - start_time).total_seconds() * 1000

        # 序列化消息历史
        serialized_messages = []
        for msg in all_messages:
            if isinstance(msg, HumanMessage):
                serialized_messages.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                entry = {"role": "assistant", "content": msg.content or ""}
                if msg.tool_calls:
                    entry["tool_calls"] = [
                        {"name": tc["name"], "args": tc["args"]}
                        for tc in msg.tool_calls
                    ]
                serialized_messages.append(entry)
            elif isinstance(msg, ToolMessage):
                serialized_messages.append({
                    "role": "tool",
                    "content": msg.content[:1000],
                    "tool_call_id": msg.tool_call_id,
                })

        # 记录助手回答到 session
        if session:
            session.add_message("assistant", final_answer)
            memory_store.save_session(session)

        result = {
            "success": True,
            "answer": final_answer,
            "tool_calls": tool_calls,
            "messages": serialized_messages,
            "iterations": iterations,
            "processing_time_ms": round(processing_ms, 2),
            "role": role,
            "provider": provider or "auto",
            "timestamp": end_time.isoformat(),
        }
        if session:
            result["session_id"] = session.session_id
        return result

    except Exception as e:
        logger.error(f"[Agent] 运行失败: {e}", exc_info=True)
        end_time = datetime.now()
        processing_ms = (end_time - start_time).total_seconds() * 1000

        result = {
            "success": False,
            "error": str(e),
            "answer": f"Agent运行出错: {str(e)}",
            "tool_calls": [],
            "iterations": 0,
            "processing_time_ms": round(processing_ms, 2),
            "role": role,
            "provider": provider or "auto",
            "timestamp": end_time.isoformat(),
        }
        if session:
            result["session_id"] = session.session_id
        return result
