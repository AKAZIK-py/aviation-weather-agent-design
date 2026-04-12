"""
航空天气AI系统 - 评测模块
Phase 1: 边界天气识别能力评测
"""

from .golden_set_generator import (
    GoldenSetGenerator,
    TestCase,
    TestType,
    WeatherCategory
)

from .evaluator import (
    WeatherAIEvaluator,
    EvaluationResult,
    EvaluationReport
)

from .report_generator import ReportGenerator

from .api_protection import (
    APIProtection,
    CircuitBreaker,
    TimeoutHandler,
    RetryMechanism,
    with_api_protection
)

# 导入核心评测模块
from .core.hallucination_detector import (
    HallucinationDetector,
    HallucinationItem,
    HallucinationReport,
    Severity
)

from .core.precision_recall import (
    MetricsCalculator,
    MetricsResult,
    DimensionScores
)

from .core.llm_judge import (
    LLMJudge,
    JudgeResult,
    JudgeScore,
    JudgeDimension
)

from .core.role_evaluator import (
    RoleEvaluator,
    RoleEvaluationResult,
    UserRole,
    RoleConfig
)

# 导入自动化评测执行器
from .runners.automated_scoring import (
    AutomatedScorer,
    ScoringReport,
    TestCaseResult
)

__all__ = [
    # Golden Set
    "GoldenSetGenerator",
    "TestCase",
    "TestType",
    "WeatherCategory",

    # Evaluator
    "WeatherAIEvaluator",
    "EvaluationResult",
    "EvaluationReport",

    # Report Generator
    "ReportGenerator",

    # API Protection
    "APIProtection",
    "CircuitBreaker",
    "TimeoutHandler",
    "RetryMechanism",
    "with_api_protection",

    # Hallucination Detection
    "HallucinationDetector",
    "HallucinationItem",
    "HallucinationReport",
    "Severity",

    # Precision/Recall Metrics
    "MetricsCalculator",
    "MetricsResult",
    "DimensionScores",

    # LLM-as-Judge
    "LLMJudge",
    "JudgeResult",
    "JudgeScore",
    "JudgeDimension",

    # Role Evaluator
    "RoleEvaluator",
    "RoleEvaluationResult",
    "UserRole",
    "RoleConfig",

    # Automated Scoring
    "AutomatedScorer",
    "ScoringReport",
    "TestCaseResult"
]

__version__ = "2.0.0"
