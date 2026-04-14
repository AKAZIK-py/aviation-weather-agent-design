"""
Agent 图 - 使用 LangGraph create_react_agent 构建真正的 Agent 循环

核心变化：
- 从 8 步硬编排 → LLM 自主决策循环
- 从固定工具调用顺序 → LLM 自主选择工具
- 从单次 LLM 调用 → ReAct 循环（思考→行动→观察→再思考）
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langgraph.prebuilt import create_react_agent

from app.agent.prompts import ROLE_CONSTRAINTS, build_first_message, build_system_prompt
from app.core.metrics import aggregate_langchain_token_usage, get_metrics
from app.core.telemetry import (
    get_langfuse_trace_info,
    get_tracer,
    langfuse_trace_context,
    mark_span_error,
)
from app.tools.weather_tools import get_all_tools

logger = logging.getLogger(__name__)


# ==================== LLM 适配层 ====================

# 任务类型 → 温度映射（来源: EVOLUTION_PLAN.md 温度配置章节）
TASK_TEMPERATURE = {
    "metar_parse": 0.0,  # METAR解析 / 数据抽取
    "risk_assessment": 0.0,  # 风险评估决策 (GO/NO-GO)
    "role_identify": 0.3,  # 角色识别
    "report_generation": 0.7,  # 自然语言报告生成
    "llm_judge": 0.0,  # 评测裁判 (LLM-as-Judge)
}


def get_llm_for_task(task_type: str, provider: str = None):
    """
    按任务类型返回对应温度的 LLM 实例。

    Args:
        task_type: 任务类型，见 TASK_TEMPERATURE 字典。
        provider:  指定 LLM Provider，None 则自动选择。

    Returns:
        LangChain 兼容的 LLM 实例。
    """
    temperature = TASK_TEMPERATURE.get(task_type, 0.3)
    logger.info("任务 '%s' 使用温度 %.1f", task_type, temperature)
    return get_langchain_llm(provider=provider, temperature=temperature)


def _normalize_deepseek_base_url(base_url: str) -> str:
    """
    规范化 DeepSeek base_url，避免 /v1 重复拼接。

    ChatOpenAI 内部会将 base_url 拼接 /chat/completions。
    如果 base_url 已包含尾部 /v1，应先剥离，防止最终路径
    变成 /v1/v1/chat/completions。
    """
    url = base_url.rstrip("/")
    # 剥离尾部 /v1（大小写不敏感）
    if url.lower().endswith("/v1"):
        url = url[:-3]
    return url


def get_langchain_llm(provider: str = None, temperature: float = 0.3):
    """
    获取 LangChain 兼容的 LLM 实例。

    优先使用 OpenAI 兼容端点（百度千帆 V2、DeepSeek），
    如果都不可用则使用 Anthropic。
    """
    from app.core.config import get_settings

    settings = get_settings()

    if provider is None:
        if settings.openai_api_key:
            provider = "openai"
        elif settings.deepseek_api_key:
            provider = "deepseek"
        elif settings.anthropic_api_key:
            provider = "anthropic"
        elif settings.qianfan_api_base_url and settings.qianfan_api_key:
            provider = "qianfan_v2"
        else:
            raise ValueError("没有可用的 LLM Provider，请在 .env 中配置")

    logger.info("Agent使用LLM Provider: %s", provider)

    if provider == "openai":
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=temperature,
            max_tokens=2500,
        )
        setattr(llm, "_aviation_provider", provider)
        setattr(llm, "_aviation_model", settings.openai_model)
        return llm

    if provider == "qianfan_v2":
        from langchain_openai import ChatOpenAI

        base_url = settings.qianfan_api_base_url.rstrip("/")
        if not base_url.endswith("/chat/completions"):
            base_url = f"{base_url}/chat/completions"
        llm = ChatOpenAI(
            model=settings.qianfan_model,
            api_key=settings.qianfan_api_key,
            base_url=base_url,
            temperature=temperature,
            max_tokens=2500,
        )
        setattr(llm, "_aviation_provider", provider)
        setattr(llm, "_aviation_model", settings.qianfan_model)
        return llm

    if provider == "deepseek":
        from langchain_openai import ChatOpenAI

        base_url = _normalize_deepseek_base_url(settings.deepseek_base_url)
        llm = ChatOpenAI(
            model=settings.deepseek_model or "deepseek-chat",
            api_key=settings.deepseek_api_key,
            base_url=base_url,
            temperature=temperature,
            max_tokens=2500,
        )
        setattr(llm, "_aviation_provider", provider)
        setattr(llm, "_aviation_model", settings.deepseek_model or "deepseek-chat")
        return llm

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        llm = ChatAnthropic(
            model=settings.anthropic_model,
            api_key=settings.anthropic_api_key,
            temperature=temperature,
            max_tokens=2500,
        )
        setattr(llm, "_aviation_provider", provider)
        setattr(llm, "_aviation_model", settings.anthropic_model)
        return llm

    raise ValueError(f"不支持的 Provider: {provider}")


# ==================== Agent 创建 ====================


def create_aviation_agent(
    role: str = "pilot",
    provider: str = None,
    max_iterations: int = 5,
    temperature: float = 0.3,
):
    """
    创建航空气象 Agent。
    """
    del max_iterations  # recursion_limit 在调用时控制

    if role not in ROLE_CONSTRAINTS:
        logger.warning("未知角色 '%s'，使用默认 'pilot'", role)
        role = "pilot"

    llm = get_langchain_llm(provider=provider, temperature=temperature)
    tools = get_all_tools()
    system_prompt = build_system_prompt(role=role)

    try:
        agent = create_react_agent(model=llm, tools=tools, prompt=system_prompt)
    except TypeError:
        agent = create_react_agent(model=llm, tools=tools, state_modifier=system_prompt)

    setattr(
        agent,
        "_aviation_provider",
        getattr(llm, "_aviation_provider", provider or "unknown"),
    )
    setattr(agent, "_aviation_model", getattr(llm, "_aviation_model", "unknown"))
    return agent


def _build_langfuse_config(
    *,
    role: str,
    provider: str,
    session_id: str | None,
    user_id: str,
    icao: str | None,
    max_iterations: int,
):
    return {
        "recursion_limit": max_iterations * 2 + 1,
        "run_name": "aviation-weather-agent",
        "metadata": {
            "langfuse_user_id": user_id,
            "langfuse_session_id": session_id or "adhoc-session",
            "langfuse_tags": [
                "aviation-weather-agent",
                f"role:{role}",
                f"provider:{provider}",
            ],
            "icao": icao,
            "role": role,
        },
    }


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
    temperature: float = 0.3,
    task_type: str = None,
) -> Dict[str, Any]:
    """
    运行航空气象 Agent。

    Args:
        task_type: 可选任务类型（见 TASK_TEMPERATURE）。
                   指定后自动使用对应温度，忽略 temperature 参数。
    """
    # 若指定了 task_type，用对应温度覆盖 temperature
    if task_type is not None:
        temperature = TASK_TEMPERATURE.get(task_type, temperature)
        logger.info("run_agent task_type=%s → temperature=%.1f", task_type, temperature)

    start_time = datetime.now()
    metrics = get_metrics()
    tracer = get_tracer(__name__)

    memory_store = None
    session = None
    if session_id is not None:
        from app.services.memory import get_memory_store

        memory_store = get_memory_store()
        session = memory_store.get_or_create_session(session_id, user_id=user_id)

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
        agent = create_aviation_agent(
            role=role,
            provider=provider,
            max_iterations=max_iterations,
            temperature=temperature,
        )
        resolved_provider = getattr(agent, "_aviation_provider", provider or "auto")
        resolved_model = getattr(agent, "_aviation_model", "unknown")

        messages: List[BaseMessage] = []
        history_source = conversation_history
        if not history_source and session:
            recent = session.get_recent_messages(max_count=20)
            history_source = [m.to_dict() for m in recent]

        if history_source:
            for msg in history_source:
                if msg["role"] == "user":
                    messages.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "assistant":
                    messages.append(AIMessage(content=msg["content"]))

        first_message = build_first_message(
            user_query=user_query,
            icao=icao,
            metar_raw=metar_raw,
            user_role=role,
        )
        messages.append(HumanMessage(content=first_message))

        if session:
            session.add_message("user", user_query or first_message)

        logger.info(
            "[Agent] 开始运行: role=%s, query=%s...", role, (user_query or "")[:50]
        )

        with tracer.start_as_current_span("aviation_agent.run") as span:
            span.set_attribute("aviation.role", role)
            span.set_attribute("aviation.provider", resolved_provider)
            span.set_attribute("aviation.model", resolved_model)
            span.set_attribute("aviation.max_iterations", max_iterations)
            span.set_attribute("aviation.session_id", session_id or "")
            span.set_attribute("aviation.user_id", user_id or "")
            span.set_attribute("aviation.icao", icao or "")

            langfuse_handler = None
            config = _build_langfuse_config(
                role=role,
                provider=resolved_provider,
                session_id=session_id,
                user_id=user_id,
                icao=icao,
                max_iterations=max_iterations,
            )
            with langfuse_trace_context(
                trace_name="aviation-agent-run",
                role=role,
                provider=resolved_provider,
                session_id=session_id,
                user_id=user_id,
            ) as handler:
                langfuse_handler = handler
                if handler is not None:
                    config["callbacks"] = [handler]

                agent_result = await agent.ainvoke(
                    {"messages": messages},
                    config=config,
                )

        all_messages = agent_result.get("messages", [])
        tool_calls: List[Dict[str, Any]] = []
        iterations = 0

        for msg in all_messages:
            if isinstance(msg, AIMessage) and msg.tool_calls:
                iterations += 1
                for tool_call in msg.tool_calls:
                    tool_calls.append(
                        {
                            "tool": tool_call["name"],
                            "args": tool_call["args"],
                            "id": tool_call["id"],
                        }
                    )
            elif isinstance(msg, ToolMessage):
                for tool_call in reversed(tool_calls):
                    if tool_call.get("id") == msg.tool_call_id:
                        tool_call["result"] = msg.content[:500]
                        break

        final_answer = ""
        for msg in reversed(all_messages):
            if isinstance(msg, AIMessage) and not msg.tool_calls:
                final_answer = msg.content
                break

        end_time = datetime.now()
        processing_ms = (end_time - start_time).total_seconds() * 1000

        serialized_messages = []
        for msg in all_messages:
            if isinstance(msg, HumanMessage):
                serialized_messages.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                entry = {"role": "assistant", "content": msg.content or ""}
                if msg.tool_calls:
                    entry["tool_calls"] = [
                        {"name": tool_call["name"], "args": tool_call["args"]}
                        for tool_call in msg.tool_calls
                    ]
                serialized_messages.append(entry)
            elif isinstance(msg, ToolMessage):
                serialized_messages.append(
                    {
                        "role": "tool",
                        "content": msg.content[:1000],
                        "tool_call_id": msg.tool_call_id,
                    }
                )

        prompt_tokens, completion_tokens, total_tokens, detected_model = (
            aggregate_langchain_token_usage(all_messages)
        )
        if total_tokens > 0:
            metrics.record_token_usage(
                provider=resolved_provider,
                model=detected_model or resolved_model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
            )
            metrics.record_llm_call(
                provider=resolved_provider,
                model=detected_model or resolved_model,
                status="success",
            )

        if session:
            session.add_message("assistant", final_answer)
            memory_store.save_session(session)

        metrics.record_agent_run(
            role=role,
            provider=resolved_provider,
            status="success",
            duration_seconds=processing_ms / 1000.0,
            iterations=iterations,
        )
        metrics.record_agent_request(
            role=role,
            provider=resolved_provider,
            status="success",
            duration_seconds=processing_ms / 1000.0,
        )

        result = {
            "success": True,
            "answer": final_answer,
            "tool_calls": tool_calls,
            "messages": serialized_messages,
            "iterations": iterations,
            "processing_time_ms": round(processing_ms, 2),
            "role": role,
            "provider": resolved_provider,
            "model": detected_model or resolved_model,
            "timestamp": end_time.isoformat(),
            "token_usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            },
        }
        if session:
            result["session_id"] = session.session_id
        result.update(get_langfuse_trace_info(langfuse_handler))
        return result

    except Exception as exc:
        logger.error("[Agent] 运行失败: %s", exc, exc_info=True)
        end_time = datetime.now()
        processing_ms = (end_time - start_time).total_seconds() * 1000
        metrics.record_agent_run(
            role=role,
            provider=provider or "auto",
            status="error",
            duration_seconds=processing_ms / 1000.0,
        )
        metrics.record_agent_request(
            role=role,
            provider=provider or "auto",
            status="error",
            duration_seconds=processing_ms / 1000.0,
        )
        metrics.record_error("agent", exc.__class__.__name__)
        if "span" in locals():
            mark_span_error(span, exc)

        result = {
            "success": False,
            "error": str(exc),
            "answer": f"Agent运行出错: {str(exc)}",
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
