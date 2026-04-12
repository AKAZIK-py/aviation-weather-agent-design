"""
提示词工程模块 - PE组合策略实现

模块组成：
- system_prompts: 角色特定的系统提示词
- analysis_prompts: METAR分析提示词模板
- report_prompts: 报告生成提示词模板

PE组合策略：
1. 角色扮演 (Role-playing): 针对不同角色定制提示词
2. 思维链 (Chain-of-Thought): 逐步分析推理过程
3. 结构化输出 (Structured Output): 指定JSON Schema输出格式
4. 安全约束 (Safety Constraints): 防止幻觉和越权
"""

from app.prompts.system_prompts import (
    SYSTEM_PROMPTS,
    SAFETY_CONSTRAINTS_TEMPLATE,
    ROLE_NAMES_CN,
    ROLE_FOCUS,
    get_system_prompt,
    get_role_focus,
    get_role_name_cn,
)

from app.prompts.analysis_prompts import (
    METAR_ANALYSIS_TEMPLATE,
    ROLE_SPECIFIC_INSTRUCTIONS,
    COT_ANALYSIS_STEPS,
    build_analysis_prompt,
    get_role_specific_instructions,
)

from app.prompts.report_prompts import (
    REPORT_GENERATION_TEMPLATE,
    ROLE_REPORT_FORMATS,
    ALERT_GENERATION_TEMPLATE,
    SUMMARY_TEMPLATE,
    build_report_prompt,
    get_report_format,
    build_alert_prompt,
)


__all__ = [
    # 系统提示词
    "SYSTEM_PROMPTS",
    "SAFETY_CONSTRAINTS_TEMPLATE",
    "ROLE_NAMES_CN",
    "ROLE_FOCUS",
    "get_system_prompt",
    "get_role_focus",
    "get_role_name_cn",

    # 分析提示词
    "METAR_ANALYSIS_TEMPLATE",
    "ROLE_SPECIFIC_INSTRUCTIONS",
    "COT_ANALYSIS_STEPS",
    "build_analysis_prompt",
    "get_role_specific_instructions",

    # 报告提示词
    "REPORT_GENERATION_TEMPLATE",
    "ROLE_REPORT_FORMATS",
    "ALERT_GENERATION_TEMPLATE",
    "SUMMARY_TEMPLATE",
    "build_report_prompt",
    "get_report_format",
    "build_alert_prompt",
]
