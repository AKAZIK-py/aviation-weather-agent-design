"""
报告生成提示词模板 - 结构化报告输出
应用场景：生成角色特定的天气分析报告和警报
"""
from typing import Dict, Any, List
import json


# ==================== 报告生成模板 ====================

REPORT_GENERATION_TEMPLATE = """请根据以下分析结果，生成{role_cn}专用的天气分析报告：

【METAR报文信息】
机场: {airport_icao}
观测时间: {observation_time}
原始报文: {raw_metar}

【分析结果】
{analysis_result}

【报告要求】
1. 使用专业但易懂的语言
2. 突出与{role_cn}相关的关键信息
3. 明确风险等级和警报
4. 给出具体可执行的建议

【强制规则 - 违反即判0分】
- 能见度描述必须使用区间：<1km、1-2km、2-4km、4-6km、6-10km、>10km
- 禁止输出 9.999、10000、9999 等精确数值作为能见度描述
- 所有气象数据引用必须来自METAR原文，禁止编造

{report_format_instructions}

请生成完整的分析报告。
"""


# ==================== 角色特定的报告格式 ====================

ROLE_REPORT_FORMATS = {
    "pilot": """
【飞行员天气报告格式】

【重要规则】
- 能见度必须使用区间表示：<1km、1-2km、2-4km、4-6km、6-10km、>10km，禁止写精确数值如9.999
- 必须包含零点高度（决断高/最低下降高MDA）
- GO/NO-GO建议必须明确，给出基于当前天气的飞行决策
- 侧风分量必须计算并标注是否超标

## 一、快速概览
- 飞行类别：VFR/MVFR/IFR/LIFR
- 风险等级：LOW/MEDIUM/HIGH/CRITICAL
- GO/NO-GO建议：[明确给出]
- 决断高/MDA：[根据进近方式给出具体数值]

## 二、关键气象参数
### 1. 风况分析
- 风向风速：XXX°/XX KT
- 阵风：XX KT（如有）
- 侧风分量：XX KT（左/右侧风）
- 风切变风险：有/无（低空风切变评估）

### 2. 能见度与云况
- 主导能见度：[使用区间：<1km / 1-2km / 2-4km / 4-6km / 6-10km / >10km]
- RVR（如有）：XX m
- 云底高：XX ft
- 云量：FEW/SCT/BKN/OVC
- 零点高度（DH/DA）：XX ft — 用于ILS进近时的决断高度
- 最低下降高（MDA）：XX ft — 用于非精密进近

### 3. 天气现象
- 当前天气：[描述]
- 积冰风险：[评估，温度<0°C且存在水汽时高风险]
- 颠簸风险：[评估]

## 三、进近与着陆分析
### 决断高/MDA详细
- ILS CAT I 决断高：200 ft (标准)
- ILS CAT II 决断高：100 ft (标准)
- 非精密进近 MDA：[根据进近程序计算]
- 当前云底高 vs DH/MDA：[对比，是否满足]

### 推荐进近方式
- [基于当前天气推荐最适合的进近方式]
- 最低标准对比：[当前条件 vs 进近最低标准]

### 起飞条件
- 是否满足起飞最低标准
- 需要特别注意的事项

### 备降决策
- 是否需要备降场
- 推荐备降场（如有）

## 四、行动项清单
1. [具体行动建议1]
2. [具体行动建议2]
3. [具体行动建议3]

## 五、安全警报（如有）
⚠️ [警报内容]
""",

    "dispatcher": """
【签派管制天气报告格式】

## 一、运行概况
- 飞行类别：VFR/MVFR/IFR/LIFR
- 运行状态：正常/受限/暂停
- 风险等级：LOW/MEDIUM/HIGH/CRITICAL

## 二、天气趋势分析
### 过去1小时变化
[描述天气演变]

### 未来2-4小时预测
[趋势预测]

### 演变方向
- 好转/恶化/稳定

## 三、运行影响评估
### 跑道运行
- 使用跑道：XX
- 到达率：XX架次/小时
- 离场率：XX架次/小时

### 进近程序
- 主要进近：[方式]
- 备用进近：[方式]
- 天气vs标准：[对比结果]

## 四、航班影响
### 延误概率：XX%
### 取消风险：低/中/高
### 备降需求：是/否

## 五、决策建议
### 放行状态
- 正常放行/条件放行/延误/取消

### 燃油策略
- 正常燃油/额外燃油建议

### 流量管理
[流量控制建议]

## 六、行动项清单
1. [签派建议1]
2. [签派建议2]
3. [签派建议3]

## 七、重要提示（如有）
⚠️ [重要提示内容]
""",

    "forecaster": """
【预报员天气报告格式】

## 一、天气形势
### 气压系统
[高压/低压/锋面描述]

### 气团性质
[冷/暖/干/湿气团]

### 天气系统
[天气系统描述]

## 二、要素演变分析
### 能见度趋势
[过去变化 + 未来趋势]

### 风向风速趋势
[变化分析]

### 温度趋势
[变化分析]

### 天气现象演变
[降水/雾/雷暴等演变预测]

## 三、危险天气评估
### 雷暴风险
[风险评估]

### 积冰潜势
[积冰类型 + 强度 + 高度层]

### 颠簸预报
[强度 + 范围]

### 其他危险天气
[低能见度/风切变等]

## 四、预报建议
### TAF趋势
[TAF趋势预报建议]

### SIGMET建议
[是否发布SIGMET + 内容]

### 关键变化预警
1. [预警1]
2. [预警2]

## 五、预报依据
[列出预报的科学依据]

## 六、不确定性说明
[预报不确定性的来源和影响]
""",

    "ground_crew": """
【机务地勤天气报告格式】

## 一、作业环境概况
- 温度：XX°C
- 天气现象：[降水/雾/晴等]
- 风力：XX级
- 风险等级：LOW/MEDIUM/HIGH/CRITICAL

## 二、户外作业评估
### 作业状态
- 适宜/限制/禁止户外作业

### 限制条件
[列出所有限制条件]

### 安全措施
1. [措施1]
2. [措施2]

## 三、航空器服务
### 加油作业
- 条件：适宜/限制/禁止
- 注意事项：[说明]

### 除防冰需求
- 是否需要：是/否
- 类型：除冰/防冰
- 建议混合比：[如有]

### 地面电源
- 使用建议：[说明]

## 四、设备使用限制
### 受影响设备
1. [设备1]：[限制说明]
2. [设备2]：[限制说明]

### 温度限制
[温度对设备的影响]

### 风力限制
[风力对设备的影响]

## 五、航材存储
### 温度敏感航材
[存储建议]

### 湿度影响
[湿度影响评估]

## 六、作业建议
### 优先处理工作
1. [工作项1]
2. [工作项2]

### 可延期工作
1. [工作项1]
2. [工作项2]

## 七、安全警报（如有）
⚠️ [警报内容]

## 八、特殊注意事项
[其他需要注意的事项]
""",
}


# ==================== 警报生成模板 ====================

ALERT_GENERATION_TEMPLATE = """
【警报生成指令】
根据风险等级 {risk_level}，生成相应的警报信息：

风险因素：
{risk_factors}

请生成：
1. 警报标题（简洁明确）
2. 警报内容（详细说明）
3. 影响范围
4. 建议措施
5. 生效时间窗口

格式要求：
- CRITICAL级别：使用红色警告标识 ⛔
- HIGH级别：使用橙色警告标识 ⚠️
- MEDIUM级别：使用黄色提示标识 ⚡
- LOW级别：使用蓝色信息标识 ℹ️
"""


# ==================== 报告总结模板 ====================

SUMMARY_TEMPLATE = """
【天气总结】

机场：{airport_icao}
时间：{observation_time}
风险等级：{risk_level}

核心发现：
{key_findings}

主要建议：
{key_recommendations}

下一步行动：
{next_steps}

{alert_section}
"""


# ==================== 辅助函数 ====================

def build_report_prompt(
    role: str,
    airport_icao: str,
    observation_time: str,
    raw_metar: str,
    analysis_result: Dict[str, Any]
) -> str:
    """
    构建报告生成提示词

    Args:
        role: 角色
        airport_icao: 机场ICAO代码
        observation_time: 观测时间
        raw_metar: 原始METAR报文
        analysis_result: 分析结果

    Returns:
        完整的提示词
    """
    from app.prompts.system_prompts import get_role_name_cn

    role_cn = get_role_name_cn(role)
    report_format = ROLE_REPORT_FORMATS.get(role, ROLE_REPORT_FORMATS["dispatcher"])

    prompt = REPORT_GENERATION_TEMPLATE.format(
        role_cn=role_cn,
        airport_icao=airport_icao,
        observation_time=observation_time,
        raw_metar=raw_metar,
        analysis_result=json.dumps(analysis_result, ensure_ascii=False, indent=2),
        report_format_instructions=report_format
    )

    return prompt


def get_report_format(role: str) -> str:
    """获取角色特定的报告格式"""
    return ROLE_REPORT_FORMATS.get(role, ROLE_REPORT_FORMATS["dispatcher"])


def build_alert_prompt(risk_level: str, risk_factors: List[str]) -> str:
    """构建警报生成提示词"""
    return ALERT_GENERATION_TEMPLATE.format(
        risk_level=risk_level,
        risk_factors="\n".join(f"- {f}" for f in risk_factors)
    )


# 导出
__all__ = [
    "REPORT_GENERATION_TEMPLATE",
    "ROLE_REPORT_FORMATS",
    "ALERT_GENERATION_TEMPLATE",
    "SUMMARY_TEMPLATE",
    "build_report_prompt",
    "get_report_format",
    "build_alert_prompt",
]
