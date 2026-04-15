from __future__ import annotations

import pytest

pytest.importorskip("deepeval")

from deepeval import assert_test
from deepeval.metrics import ToolCorrectnessMetric
from deepeval.test_case import LLMTestCase

from tests.evaluation.deepeval_support import (
    assert_agent_success,
    build_input_text,
    execute_scenario,
    get_available_tools,
    get_metric_model,
    metric_threshold,
    to_actual_tool_calls,
    to_tool_calls,
)
from tests.evaluation.scenarios import TOOL_CALL_CASES, EvalScenario


@pytest.mark.evaluation
@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", TOOL_CALL_CASES, ids=lambda case: case.id)
async def test_tool_calling_correctness(scenario: EvalScenario):
    result = await execute_scenario(scenario)
    assert_agent_success(result, scenario)

    test_case = LLMTestCase(
        input=build_input_text(scenario),
        actual_output=result["answer"],
        tools_called=to_actual_tool_calls(result),
        expected_tools=to_tool_calls(scenario.expected_tools),
    )
    metric = ToolCorrectnessMetric(
        threshold=metric_threshold("TOOL_CORRECTNESS_THRESHOLD", 0.67),
        model=get_metric_model(),
        available_tools=get_available_tools(),
        include_reason=True,
        should_exact_match=False,
        should_consider_ordering=False,
        verbose_mode=False,
    )
    assert_test(test_case=test_case, metrics=[metric], run_async=False)
