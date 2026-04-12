"""
METAR分析提示词模板 - 思维链(CoT) + 结构化输出(Structured Output)
应用场景：指导LLM进行逐步分析并输出结构化结果
"""
from typing import Dict, Any, List
import json


# ==================== METAR分析提示词模板 ====================

METAR_ANALYSIS_TEMPLATE = """请根据以下METAR报文，以{role_cn}角色进行专业的天气分析：

【原始METAR报文】
{raw_metar}

【解析后的天气数据】
{parsed_data}

【当前风险等级】
{risk_level}

【主要风险因素】
{risk_factors}

【分析要求】
1. 基于你的角色定位，重点关注与该角色相关的气象参数
2. 按照思维链路逐步分析
3. 输出结构化的分析结果（JSON格式）
4. 确保所有建议符合安全约束

【强制规则 - 违反即判0分】
- 能见度描述必须使用区间：<1km、1-2km、2-4km、4-6km、6-10km、>10km，禁止输出9.999等精确数值
- 禁止编造METAR报文中不存在的天气现象
- 所有数值引用必须直接来自METAR原文
- 不确定的信息必须标注"待确认"

【分析深度要求 - 反模板化】
- 你的分析必须基于当前METAR的具体数值，不同数据产生不同结论
- 禁止使用"天气条件良好"等万能模板语句，必须具体分析每个参数的含义
- 即使条件良好，也需分析潜在风险点（温度露点差、风向趋势、气压变化等）
- 建议必须有针对性：不同风速/温度/能见度组合必须产生不同建议
- 结合时间因素（如清晨辐射雾风险、午后热对流等）给出情境化分析

{additional_instructions}

请严格按照指定的JSON Schema格式输出。
"""


# ==================== 角色特定的分析指令 ====================

ROLE_SPECIFIC_INSTRUCTIONS = {
    "pilot": """
【飞行员专项分析指令】
重点分析以下内容：

1. **起飞条件评估**
   - 跑道视程(RVR)是否满足起飞最低标准
   - 侧风分量是否在机型限制内
   - 云底高是否影响目视离场

2. **进近着陆评估**
   - 能见度/云底高是否满足进近最低标准
   - 是否存在风切变风险
   - 推荐的进近方式（ILS/VOR/目视）

3. **积冰风险评估**
   - 温度露点差 < 3°C时积冰风险
   - 云中飞行积冰可能性
   - 化油器积冰风险

4. **备降决策**
   - 是否需要备降场
   - 备降场天气要求
   - 燃油储备建议

请输出符合以下JSON Schema的结果：
{
  "flight_critical_parameters": {
    "icing_condition": {...},
    "cloud_conditions": {...},
    "visibility": {...},
    "wind": {...}
  },
  "flight_decision": {
    "vfr_suitability": "...",
    "ifr_approach": "...",
    "go_no_go": "GO/NO-GO/CONDITIONAL",
    "risk_summary": "...",
    "action_items": ["..."]
  }
}
""",

    "dispatcher": """
【签派管制专项分析指令】
重点分析以下内容：

1. **天气趋势判断**
   - 过去1小时天气变化
   - 未来2-4小时演变预测
   - 好转/恶化/稳定趋势

2. **运行影响评估**
   - 跑道运行能力（到达率/离场率）
   - 进近程序选择
   - 飞行类别（VFR/MVFR/IFR/LIFR）

3. **航班影响量化**
   - 延误概率评估（0-100%）
   - 取消风险等级（低/中/高）
   - 是否需要备降场

4. **资源优化建议**
   - 燃油策略（正常/额外）
   - 时刻调整建议
   - 流量管理建议

请输出符合以下JSON Schema的结果：
{
  "dispatch_critical_parameters": {
    "weather_trend": {...},
    "runway_operations": {...},
    "approach_minima": {...},
    "flight_category": {...}
  },
  "dispatch_decision": {
    "release_status": "...",
    "alternate_required": true/false,
    "fuel_strategy": "...",
    "delay_probability": 0-100,
    "action_items": ["..."]
  }
}
""",

    "forecaster": """
【预报员专项分析指令】
重点分析以下内容：

1. **天气系统识别**
   - 气压系统分析（高压/低压/锋面）
   - 气团性质（冷/暖/干/湿）
   - 天气形势判断

2. **要素演变分析**
   - 能见度变化趋势
   - 风向风速变化趋势
   - 温度变化趋势
   - 天气现象演变预期

3. **危险天气判断**
   - 雷暴发展可能性
   - 积冰潜势评估
   - 颠簸预报
   - 雾的发展趋势

4. **预报建议**
   - TAF趋势预报建议
   - SIGMET发布建议
   - 关键变化预警

请输出符合以下JSON Schema的结果：
{
  "weather_analysis": {
    "synoptic_situation": {...},
    "trend_analysis": {...},
    "hazard_assessment": {...}
  },
  "forecast_recommendations": {
    "taf_trend": "...",
    "sigmet_advisory": "...",
    "critical_changes": ["..."],
    "action_items": ["..."]
  }
}
""",

    "ground_crew": """
【机务地勤专项分析指令】
重点分析以下内容：

1. **户外作业影响**
   - 温度、降水、风对作业的影响
   - 是否适宜户外作业
   - 作业限制条件

2. **航空器服务**
   - 加油作业限制
   - 除防冰需求评估
   - 地面电源使用建议

3. **设备使用限制**
   - 受影响的地面设备
   - 温度限制下的设备使用
   - 风力限制下的设备使用

4. **航材存储**
   - 温度敏感航材存储建议
   - 湿度对航材的影响
   - 特殊防护措施

请输出符合以下JSON Schema的结果：
{
  "maintenance_conditions": {
    "outdoor_operations": {...},
    "aircraft_servicing": {...},
    "equipment_limitations": {...},
    "material_storage": {...}
  },
  "maintenance_decision": {
    "work_priority": ["..."],
    "postponable_work": ["..."],
    "special_precautions": ["..."],
    "action_items": ["..."]
  }
}
""",
}


# ==================== 思维链(CoT)分析步骤模板 ====================

COT_ANALYSIS_STEPS = """
【逐步分析流程】
按照以下步骤进行分析：

步骤1: 数据完整性检查
- 核对METAR报文要素是否齐全
- 识别缺失或异常数据
- 标注数据可信度

步骤2: 关键参数提取
- 风向风速（含阵风）
- 主导能见度（含RVR）
- 天气现象（降水/雾/雷暴等）
- 云层（云量/云底高）
- 温度/露点
- 气压（QNH）

步骤3: 风险识别
- 对照运行标准识别超标项
- 评估危险天气（积冰/风切变/雷暴）
- 判断复合风险

步骤4: 影响评估
- 对运行的影响程度
- 持续时间判断
- 影响范围

步骤5: 建议生成
- 明确的行动建议
- 风险缓解措施
- 后续监控要点
"""


# ==================== 辅助函数 ====================

def build_analysis_prompt(
    role: str,
    raw_metar: str,
    parsed_data: Dict[str, Any],
    risk_level: str,
    risk_factors: List[str]
) -> str:
    """
    构建METAR分析提示词

    Args:
        role: 角色
        raw_metar: 原始METAR报文
        parsed_data: 解析后的数据
        risk_level: 风险等级
        risk_factors: 风险因素列表

    Returns:
        完整的提示词
    """
    from app.prompts.system_prompts import get_role_name_cn

    role_cn = get_role_name_cn(role)
    additional_instructions = ROLE_SPECIFIC_INSTRUCTIONS.get(
        role,
        ROLE_SPECIFIC_INSTRUCTIONS["dispatcher"]
    )

    prompt = METAR_ANALYSIS_TEMPLATE.format(
        role_cn=role_cn,
        raw_metar=raw_metar,
        parsed_data=json.dumps(parsed_data, ensure_ascii=False, indent=2),
        risk_level=risk_level,
        risk_factors="\n".join(f"- {f}" for f in risk_factors[:5]),
        additional_instructions=additional_instructions
    )

    return f"{prompt}\n\n{COT_ANALYSIS_STEPS}"


def get_role_specific_instructions(role: str) -> str:
    """获取角色特定的分析指令"""
    return ROLE_SPECIFIC_INSTRUCTIONS.get(role, ROLE_SPECIFIC_INSTRUCTIONS["dispatcher"])


# 导出
__all__ = [
    "METAR_ANALYSIS_TEMPLATE",
    "ROLE_SPECIFIC_INSTRUCTIONS",
    "COT_ANALYSIS_STEPS",
    "build_analysis_prompt",
    "get_role_specific_instructions",
]
