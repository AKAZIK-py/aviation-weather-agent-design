from __future__ import annotations

import pytest

pytest.importorskip("deepeval")

from deepeval import assert_test
from deepeval.metrics import ContextualPrecisionMetric
from deepeval.test_case import LLMTestCase

from tests.evaluation.deepeval_support import (
    assert_agent_success,
    build_input_text,
    build_retrieval_context,
    execute_scenario,
    get_metric_model,
    metric_threshold,
)
from tests.evaluation.scenarios import CONTEXT_PRECISION_CASES, EvalScenario


@pytest.mark.evaluation
@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", CONTEXT_PRECISION_CASES, ids=lambda case: case.id)
async def test_context_precision(scenario: EvalScenario):
    result = await execute_scenario(scenario)
    assert_agent_success(result, scenario)

    test_case = LLMTestCase(
        input=build_input_text(scenario),
        actual_output=result["answer"],
        expected_output=scenario.expected_output,
        retrieval_context=build_retrieval_context(scenario, result),
    )
    metric = ContextualPrecisionMetric(
        threshold=metric_threshold("CONTEXT_PRECISION_THRESHOLD", 0.70),
        model=get_metric_model(),
        include_reason=True,
        async_mode=False,
    )
    assert_test(test_case=test_case, metrics=[metric], run_async=False)
