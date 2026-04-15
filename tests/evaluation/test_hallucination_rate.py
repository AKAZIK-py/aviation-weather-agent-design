from __future__ import annotations

import pytest

pytest.importorskip("deepeval")

from deepeval import assert_test
from deepeval.metrics import HallucinationMetric
from deepeval.test_case import LLMTestCase

from tests.evaluation.deepeval_support import (
    assert_agent_success,
    build_hallucination_context,
    build_input_text,
    get_metric_model,
    metric_threshold,
    execute_scenario,
)
from tests.evaluation.scenarios import HALLUCINATION_CASES, EvalScenario


@pytest.mark.evaluation
@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", HALLUCINATION_CASES, ids=lambda case: case.id)
async def test_hallucination_rate(scenario: EvalScenario):
    result = await execute_scenario(scenario)
    assert_agent_success(result, scenario)

    test_case = LLMTestCase(
        input=build_input_text(scenario),
        actual_output=result["answer"],
        context=build_hallucination_context(scenario, result),
    )
    metric = HallucinationMetric(
        threshold=metric_threshold("HALLUCINATION_THRESHOLD", 0.05),
        model=get_metric_model(),
        include_reason=True,
        async_mode=False,
    )
    assert_test(test_case=test_case, metrics=[metric], run_async=False)
