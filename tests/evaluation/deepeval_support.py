from __future__ import annotations

import asyncio
import json
import os
from functools import lru_cache
from typing import Any, Dict, Iterable, List

from app.agent.graph import get_langchain_llm, run_agent
from app.core.config import get_settings
from app.tools.weather_tools import TOOL_REGISTRY
from tests.evaluation.scenarios import EvalScenario

try:
    from deepeval.models import DeepEvalBaseLLM
except Exception:  # pragma: no cover - compatibility fallback
    from deepeval.models.base_model import DeepEvalBaseLLM  # type: ignore

try:
    from deepeval.test_case import ToolCall
except Exception:  # pragma: no cover - compatibility fallback
    from deepeval.test_case.llm_test_case import ToolCall  # type: ignore


FALSEY = {"0", "false", "no", "off"}


class AviationEvalJudge(DeepEvalBaseLLM):
    """Use the project's own multi-provider LangChain model as the DeepEval judge."""

    def __init__(self, provider: str | None = None, temperature: float = 0.0):
        self.provider = provider
        self.temperature = temperature
        self._model = None

    def load_model(self):
        if self._model is None:
            self._model = get_langchain_llm(
                provider=self.provider,
                temperature=self.temperature,
            )
        return self._model

    def get_model_name(self) -> str:
        model = self.load_model()
        return getattr(model, "model_name", None) or getattr(model, "model", None) or "aviation-agent-eval-judge"

    def _extract_text(self, response: Any) -> str:
        if hasattr(response, "content"):
            content = response.content
        else:
            content = response
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "\n".join(str(item) for item in content)
        return json.dumps(content, ensure_ascii=False, default=str)

    def generate(self, prompt: str, *args, **kwargs) -> str:
        response = self.load_model().invoke(str(prompt))
        return self._extract_text(response)

    async def a_generate(self, prompt: str, *args, **kwargs) -> str:
        response = await self.load_model().ainvoke(str(prompt))
        return self._extract_text(response)


@lru_cache(maxsize=1)
def ensure_eval_environment_ready() -> None:
    settings = get_settings()
    available_keys = [
        settings.openai_api_key,
        settings.deepseek_api_key,
        settings.anthropic_api_key,
        settings.qianfan_api_key,
        settings.moonshot_api_key,
    ]
    if not any(available_keys):
        raise RuntimeError(
            "DeepEval 评测需要至少一个可用的 LLM Provider Key。"
            "请在 .env 或 CI secrets 中配置 OPENAI_API_KEY / DEEPSEEK_API_KEY / "
            "ANTHROPIC_API_KEY / QIANFAN_API_KEY / MOONSHOT_API_KEY 之一。"
        )


@lru_cache(maxsize=1)
def get_metric_model() -> Any:
    use_project_llm = os.getenv("DEEPEVAL_USE_PROJECT_LLM", "1").strip().lower() not in FALSEY
    if use_project_llm:
        return AviationEvalJudge(provider=os.getenv("DEEPEVAL_JUDGE_PROVIDER"))
    return os.getenv("DEEPEVAL_MODEL", "gpt-4.1")


@lru_cache(maxsize=1)
def get_available_tools() -> List[ToolCall]:
    return [
        ToolCall(name=name, description=spec.get("description", ""))
        for name, spec in TOOL_REGISTRY.items()
    ]


async def execute_scenario(scenario: EvalScenario) -> Dict[str, Any]:
    ensure_eval_environment_ready()
    session_id = f"deepeval-{scenario.id}"
    return await run_agent(
        user_query=scenario.query,
        metar_raw=scenario.metar_raw,
        role=scenario.role,
        provider=scenario.provider or os.getenv("EVAL_AGENT_PROVIDER"),
        conversation_history=list(scenario.conversation_history),
        max_iterations=scenario.max_iterations,
        session_id=session_id,
        user_id=scenario.user_id,
    )


def run_scenario_sync(scenario: EvalScenario) -> Dict[str, Any]:
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():  # pragma: no cover - defensive branch
        raise RuntimeError("run_scenario_sync 不能在已运行的事件循环中调用")
    return asyncio.run(execute_scenario(scenario))


def build_input_text(scenario: EvalScenario) -> str:
    return f"role={scenario.role}\nquery={scenario.query}\nmetar={scenario.metar_raw}"


def format_tool_context(tool_call: Dict[str, Any]) -> str:
    result = tool_call.get("result", "")
    if not isinstance(result, str):
        result = json.dumps(result, ensure_ascii=False, default=str)
    args = json.dumps(tool_call.get("args", {}), ensure_ascii=False, sort_keys=True)
    return f"tool={tool_call.get('tool')}\nargs={args}\nresult={result}"


def build_hallucination_context(scenario: EvalScenario, result: Dict[str, Any]) -> List[str]:
    contexts = [f"raw_metar={scenario.metar_raw}"]
    contexts.extend(format_tool_context(call) for call in result.get("tool_calls", []))
    return contexts


def build_retrieval_context(scenario: EvalScenario, result: Dict[str, Any]) -> List[str]:
    retrieval_context = [format_tool_context(call) for call in result.get("tool_calls", [])]
    retrieval_context.extend(scenario.distractor_contexts)
    if not retrieval_context:
        retrieval_context.append(f"raw_metar={scenario.metar_raw}")
    return retrieval_context


def to_tool_calls(tool_names: Iterable[str]) -> List[ToolCall]:
    tool_calls: List[ToolCall] = []
    for name in tool_names:
        description = TOOL_REGISTRY.get(name, {}).get("description", "")
        tool_calls.append(ToolCall(name=name, description=description))
    return tool_calls


def to_actual_tool_calls(result: Dict[str, Any]) -> List[ToolCall]:
    converted: List[ToolCall] = []
    for call in result.get("tool_calls", []):
        converted.append(
            ToolCall(
                name=call.get("tool", "unknown"),
                description=TOOL_REGISTRY.get(call.get("tool", ""), {}).get("description", ""),
                input=call.get("args", {}),
            )
        )
    return converted


def assert_agent_success(result: Dict[str, Any], scenario: EvalScenario) -> None:
    assert result.get("success") is True, f"Agent 执行失败: {scenario.id}: {result}"
    assert result.get("answer"), f"Agent 未返回最终回答: {scenario.id}: {result}"


def metric_threshold(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))
