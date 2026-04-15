from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class EvalScenario:
    id: str
    query: str
    metar_raw: str
    role: str = "pilot"
    provider: Optional[str] = None
    max_iterations: int = 5
    expected_output: str = ""
    expected_tools: List[str] = field(default_factory=list)
    distractor_contexts: List[str] = field(default_factory=list)
    conversation_history: List[Dict[str, str]] = field(default_factory=list)
    user_id: str = "deepeval"


HALLUCINATION_CASES: List[EvalScenario] = [
    EvalScenario(
        id="hallucination-no-invented-hazard",
        role="pilot",
        metar_raw="METAR ZSPD 110800Z 25012KT 9999 SCT040 28/22 Q1008",
        query="只根据这条METAR回答：是否提到了雷暴、风切变、积冰或跑道关闭？如果没有，请明确说报文没有提供这些信息。",
        expected_output=(
            "这条METAR显示ZSPD当前能见度良好、散云约4000英尺、风250度12节、QNH 1008。"
            "报文没有提到雷暴、风切变、积冰，也没有提供任何跑道关闭信息，因此不能编造额外风险。"
        ),
        expected_tools=["parse_metar", "assess_risk"],
    ),
    EvalScenario(
        id="hallucination-low-vis-no-extra-weather",
        role="pilot",
        metar_raw="METAR ZSSS 110830Z 18008KT 0800 FG VV002 10/09 Q1013",
        query="只基于报文本身说明主要风险。若没有写到雷暴、风切变或冻雨，请直接说明未提及。",
        expected_output=(
            "这条METAR的主要风险是0800米低能见度、浓雾和垂直能见度200英尺，对进近和滑行都有明显限制。"
            "报文没有提到雷暴、风切变或冻雨，因此不应额外添加这些天气现象。"
        ),
        expected_tools=["parse_metar", "assess_risk"],
    ),
]


TOOL_CALL_CASES: List[EvalScenario] = [
    EvalScenario(
        id="tool-call-ifr-risk-assessment",
        role="pilot",
        metar_raw="METAR ZSSS 110830Z 18008KT 0800 FG VV002 10/09 Q1013",
        query="我是机长。请解析这条METAR并判断当前进近风险，重点说清飞行规则和主要风险。",
        expected_output=(
            "应先解析METAR，再给出飞行规则和风险评估。当前条件受低能见度、浓雾和极低云底影响，"
            "属于明显的IFR/LIFR风险场景，需要谨慎评估是否继续进近。"
        ),
        expected_tools=["parse_metar", "assess_risk"],
    ),
    EvalScenario(
        id="tool-call-visibility-broadcast",
        role="dispatcher",
        metar_raw="METAR ZSNJ 110900Z 24015G25KT 0400 FG VV001 08/07 Q1015",
        query="请把这条报文转换成飞行规则结论，并把能见度改写成便于对外播报的区间描述。",
        expected_output=(
            "应先解析METAR，再结合能见度和云底判断飞行规则，并把能见度转换成区间化口径。"
            "该报文能见度仅400米、垂直能见度100英尺，属于极低能见度场景。"
        ),
        expected_tools=["parse_metar", "get_flight_rules", "format_visibility"],
    ),
]


CONTEXT_PRECISION_CASES: List[EvalScenario] = [
    EvalScenario(
        id="context-precision-ifr-priority",
        role="pilot",
        metar_raw="METAR ZSSS 110830Z 18008KT 0800 FG VV002 10/09 Q1013",
        query="请基于这条METAR，给我一个简短的进近风险判断和操作建议。",
        expected_output=(
            "应优先围绕低能见度、浓雾和极低云底作出判断：当前更像高风险IFR运行，"
            "需要核对运行最低标准并准备复飞/备降方案。"
        ),
        expected_tools=["parse_metar", "assess_risk"],
        distractor_contexts=[
            "无关上下文：另一个机场天气晴朗，VFR训练飞行条件优秀。",
            "无关上下文：旅客服务通知，值机柜台开放时间调整。",
        ],
    ),
    EvalScenario(
        id="context-precision-vfr-focus",
        role="dispatcher",
        metar_raw="METAR ZSPD 110800Z 25012KT 9999 SCT040 28/22 Q1008",
        query="请给出放行视角的简短天气结论，只突出这条报文里最相关的信息。",
        expected_output=(
            "应重点说明ZSPD当前能见度良好、散云4000英尺、风250度12节，整体偏VFR、运行条件较稳定；"
            "不要把与该报文无关的恶劣天气背景放在前面。"
        ),
        expected_tools=["parse_metar", "assess_risk"],
        distractor_contexts=[
            "无关上下文：ZSNJ当前0400米浓雾、垂直能见度100英尺，属于LIFR。",
            "无关上下文：上一班机因雷暴备降，与本条METAR无直接关系。",
        ],
    ),
]
