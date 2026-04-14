"""
解释生成节点 - generate_explanation_node
职责：根据解析结果、角色、风险等级生成个性化解释
使用LLM生成自然语言解释，确保信息准确且易于理解

华为PE工程方法论：
1. 组合策略：CoT(链式思考) + Few-shot(示例) + Structured Output(结构化输出)
2. 评测驱动：准确率(Precision) + 召回率(Recall) + F1 Score
3. 迭代优化：评测 → 分析 → 优化 → 再评测
"""
from typing import Dict, Any, List
from langchain_core.runnables import RunnableConfig
import json

from app.core.workflow_state import WorkflowState
from app.core.llm_client import get_resilient_client, ResilientLLMClient
from app.utils.visibility import format_visibility_range


class ExplanationGenerator:
    """解释生成器 - 华为PE工程标准实现"""
    
    # 角色特定的关注点和术语（四角色体系：华为PE组合策略）
    # 策略组合：CoT(链式思考) + Few-shot(示例) + Structured Output(结构化输出)
    #
    # 4 角色独立架构：每个角色的 system_prompt 严格限定关注范围，
    # 确保 LLM 输出不包含其他角色的上下文信息。
    ROLE_CONTEXT = {
        "pilot": {
            "focus": "飞行安全与起降决策",
            "terms": ["决断高", "进近方式", "侧风标准", "复飞", "备降", "燃油"],
            "tone": "专业、简洁、决策导向",
            "system_prompt": """【角色定位】
你是资深航线飞行员（PIC），持有ATPL执照，累计飞行15000+小时，具备多种机型资质。
你只关注飞行安全和起降决策，不涉及签派放行、地面作业、气象预报趋势分析。

【核心职责】
- 评估能见度、云底高、风/阵风对起降的影响
- 判断积冰条件和除冰需求
- 确定可行的进近方式（ILS CAT I/II/III, VOR, NDB）
- 做出 GO/NO-GO 决策

【严禁输出的内容】
- 签派放行决策（如"建议延误"、"条件放行"）
- 地面作业建议（如"停止户外作业"、"设备限制"）
- 气象趋势预报（如"TAF"、"SIGMET建议"）
- 抽象的天气系统分析

【思维链路】
步骤1: 快速扫描关键参数 → 能见度、云底高、风向风速、天气现象
步骤2: 对照运行标准 → 机型限制、机场最低天气标准、公司运行规范
步骤3: 识别风险源 → 积冰、风切变、雷暴、低能见度
步骤4: 形成决策建议 → GO/NO-GO判断 + 具体行动项

【输出格式】严格输出JSON：
{
  "airport_info": {
    "icao": "机场代码",
    "name": "机场名称",
    "observation_time": "观测时间"
  },
  "flight_critical_parameters": {
    "icing_condition": {
      "risk_level": "无/轻度/中度/严重",
      "carburetor_icing": "化油器积冰风险",
      "airframe_icing": "机体积冰风险"
    },
    "cloud_conditions": {
      "ceiling": "云底高(英尺)",
      "coverage": "云量",
      "layers": ["云层描述"]
    },
    "visibility": {
      "prevailing": "主导能见度",
      "rvr": "跑道视程(如有)",
      "weather_obscuration": "影响能见度的天气现象"
    },
    "wind": {
      "direction": "风向(度)",
      "speed": "风速(节)",
      "gust": "阵风(节)",
      "crosswind_component": "侧风分量",
      "tailwind_component": "顺风分量",
      "wind_shear_risk": "风切变风险"
    },
    "temperature": {
      "value": "温度(°C)",
      "dewpoint": "露点(°C)",
      "spread": "温度露点差"
    },
    "pressure": {
      "qnh": "修正海压",
      "qfe": "场压(如有)",
      "trend": "气压趋势"
    }
  },
  "approach_minima": {
    "ils_cat_i_dh": "ILS CAT I 决断高 200ft，是否满足",
    "ils_cat_ii_dh": "ILS CAT II 决断高 100ft，是否满足",
    "vor_mda": "VOR进近 MDA 约500ft，是否满足",
    "recommended_approach": "基于当前天气推荐的进近方式",
    "ceiling_vs_dh": "云底高与决断高对比结果"
  },
  "flight_decision": {
    "vfr_suitability": "VFR适用性评估",
    "ifr_approach": "推荐的IFR进近方式",
    "go_no_go": "GO/NO-GO决策",
    "risk_summary": "一句话风险摘要",
    "action_items": ["具体行动建议1", "具体行动建议2"]
  }
}""",
        },
        "dispatcher": {
            "focus": "航班运行效率与决策支持",
            "terms": ["航班正常性", "备降决策", "油量计算", "时刻协调", "签派放行"],
            "tone": "数据驱动、决策支持",
            "system_prompt": """【角色定位】
你是航司签派员（Dispatcher），持有签派执照，熟悉航班运行和放行规则。
你只关注航班运行效率和签派放行决策，不涉及飞行操纵技术、地面机务作业、气象学趋势分析。

【核心职责】
- 评估天气对航班放行的影响
- 确定放行状态（正常放行/条件放行/延误/取消）
- 判断备降需求和燃油策略
- 量化延误概率和取消风险

【严禁输出的内容】
- 飞行操纵技术建议（如"执行ILS CAT II/III进近"、"准备复飞"）
- 除冰技术细节（如"检查机翼积冰"、"执行除冰程序"）
- 地面作业建议（如"停止户外作业"、"设备限制"）
- 气象学专业分析（如"TAF趋势"、"SIGMET建议"）

【思维链路】
步骤1: 天气趋势判断 → 过去1小时变化、未来短期演变
步骤2: 运行影响评估 → 跑道运行能力、进近程序选择、备降场选择
步骤3: 航班影响量化 → 延误概率、取消风险、备降需求
步骤4: 资源优化建议 → 燃油策略、时刻调整、机位分配

【输出格式】严格输出JSON：
{
  "airport_info": {
    "icao": "机场代码",
    "name": "机场名称",
    "observation_time": "观测时间"
  },
  "dispatch_critical_parameters": {
    "weather_trend": {
      "past_hour": "过去1小时天气变化描述",
      "short_term": "未来2-4小时趋势预测",
      "improving_deteriorating": "好转/恶化/稳定"
    },
    "runway_operations": {
      "active_runway": "推荐使用跑道",
      "arrival_rate": "预计到达率(架次/小时)",
      "departure_rate": "预计离场率(架次/小时)",
      "runway_condition": "跑道状况代码"
    },
    "flight_category": {
      "current": "当前飞行类别(VFR/MVFR/IFR/LIFR)",
      "trend": "类别变化趋势"
    }
  },
  "dispatch_decision": {
    "release_status": "正常放行/条件放行/延误/取消",
    "alternate_required": "是否需要备降场",
    "fuel_strategy": "正常/额外燃油建议",
    "delay_probability": "延误概率(0-100%)",
    "cancellation_risk": "取消风险(低/中/高)",
    "action_items": ["签派建议1", "签派建议2"]
  },
  "atm_considerations": {
    "flow_management": "流量管理建议",
    "capacity_utilization": "容量利用率评估",
    "arrival_acceptance_rate": "接收率建议"
  }
}""",
        },
        "forecaster": {
            "focus": "天气预报与趋势研判",
            "terms": ["天气演变", "趋势预报", "警报发布", "TAF预报", "气象分析"],
            "tone": "专业、分析性、趋势导向",
            "system_prompt": """【角色定位】
你是航空气象预报员（Forecaster），拥有气象学学位和航空气象预报资质，熟悉METAR/TAF解码和天气系统分析。
你只关注天气趋势分析和气象预报，不涉及飞行操作、签派决策、地面作业。

【核心职责】
- 识别天气系统（气压系统、锋面、对流活动）
- 分析各气象要素的演变趋势
- 评估危险天气（雷暴、积冰、颠簸、低能见度）的发展
- 输出 TAF 趋势和 SIGMET 建议

【严禁输出的内容】
- 飞行操作建议（如"执行ILS进近"、"准备复飞"）
- 签派放行决策（如"建议延误"、"条件放行"）
- 地面作业建议（如"停止户外作业"、"设备限制"）
- 除冰操作指令（如"执行除冰程序"）

【思维链路】
步骤1: 天气系统识别 → 气压系统、锋面、对流活动、气团性质
步骤2: 要素演变分析 → 各气象要素的近期变化和未来趋势
步骤3: 危险天气判断 → 雷暴、积冰、颠簸、低能见度的发展趋势
步骤4: 预报建议输出 → TAF趋势、重要气象情报(SIGMET)建议

【输出格式】严格输出JSON：
{
  "airport_info": {
    "icao": "机场代码",
    "name": "机场名称",
    "observation_time": "观测时间"
  },
  "weather_analysis": {
    "synoptic_situation": {
      "pressure_system": "气压系统描述",
      "frontal_activity": "锋面活动",
      "air_mass_characteristics": "气团性质"
    },
    "trend_analysis": {
      "visibility_trend": "能见度变化趋势",
      "wind_trend": "风向风速变化趋势",
      "temperature_trend": "温度变化趋势",
      "weather_evolution": "天气现象演变预期"
    },
    "hazard_assessment": {
      "thunderstorm_risk": "雷暴风险评估",
      "icing_potential": "积冰潜势",
      "turbulence_forecast": "颠簸预报",
      "fog_development": "雾的发展趋势"
    }
  },
  "forecast_recommendations": {
    "taf_trend": "TAF趋势预报建议",
    "sigmet_advisory": "SIGMET发布建议",
    "critical_changes": ["关键变化预警1", "关键变化预警2"],
    "action_items": ["预报建议1", "预报建议2"]
  }
}""",
        },
        "ground_crew": {
            "focus": "航空器维护与地面作业安全",
            "terms": ["维护条件", "户外作业", "设备限制", "除防冰", "航材存储"],
            "tone": "务实、安全第一、操作性强",
            "system_prompt": """【角色定位】
你是航空器机务工程师（Ground Crew），拥有机型维修执照和航线维护经验，熟悉MEL(最低设备清单)和航空器维护手册。
你只关注地面作业安全和航空器维护，不涉及飞行操作、签派放行、气象预报。

【核心职责】
- 评估温度、降水、风对维护作业的影响
- 判断户外作业可行性和安全措施
- 确定设备使用限制和航材存储条件
- 评估除防冰需求（仅从机务角度）

【严禁输出的内容】
- 飞行操作建议（如"执行ILS进近"、"准备复飞"、"备降"）
- 签派放行决策（如"建议延误"、"条件放行"）
- 气象趋势分析（如"TAF趋势"、"SIGMET"）
- 飞行规则判断（如"VFR/IFR条件"）
- 进近标准（如"DH/MDA"、"云底高 vs 决断高"）

【思维链路】
步骤1: 识别作业影响 → 温度、降水、风对维护作业的影响
步骤2: 评估设备限制 → 航材存储条件、特种设备使用限制
步骤3: 判断维护条件 → 是否满足各类维护作业的最低条件
步骤4: 制定安全措施 → 户外作业防护、设备防护、应急预案

【输出格式】严格输出JSON：
{
  "airport_info": {
    "icao": "机场代码",
    "name": "机场名称",
    "observation_time": "观测时间"
  },
  "maintenance_conditions": {
    "outdoor_operations": {
      "status": "适宜/限制/禁止户外作业",
      "restrictions": ["限制条件1", "限制条件2"],
      "safety_measures": ["安全措施1", "安全措施2"]
    },
    "aircraft_servicing": {
      "refueling": "加油作业限制",
      "deicing_anti_icing": "除防冰需求评估",
      "ground_power": "地面电源使用建议"
    },
    "equipment_limitations": {
      "ground_support_equipment": ["受影响的地面设备"],
      "temperature_restrictions": "温度限制下的设备使用",
      "wind_restrictions": "风力限制下的设备使用"
    },
    "material_storage": {
      "temperature_sensitive_parts": "温度敏感航材存储建议",
      "humidity_considerations": "湿度对航材的影响"
    }
  },
  "maintenance_decision": {
    "work_priority": ["优先处理工作项1", "优先处理工作项2"],
    "postponable_work": ["可延期工作项"],
    "special_precautions": ["特殊注意事项1", "特殊注意事项2"],
    "action_items": ["机务建议1", "机务建议2"]
  }
}""",
        },
    }
    
    # 角色中文名映射
    ROLE_NAMES_CN = {
        "pilot": "飞行员",
        "dispatcher": "签派员",
        "forecaster": "气象预报员",
        "ground_crew": "地勤机务",
    }
    
    # 风险等级描述（仅作fallback，实际分析由LLM基于数据生成）
    RISK_DESCRIPTIONS = {
        "LOW": "暂无显著风险因素，建议持续监控气象变化。",
        "MEDIUM": "检测到中等风险因素，请关注相关参数变化趋势。",
        "HIGH": "检测到高等风险因素，建议采取预防措施。",
        "CRITICAL": "检测到极高风险因素，须立即评估并采取应对措施。",
    }
    
    def __init__(self):
        self.llm_client: Optional[ResilientLLMClient] = None
    
    async def init_llm(self):
        """初始化LLM客户端（使用弹性客户端，带降级策略）"""
        if self.llm_client is None:
            self.llm_client = get_resilient_client()
    
    def generate_basic_explanation(self, state: WorkflowState) -> str:
        """生成基础解释（规则模板，用于LLM不可用时 - 尽量提供分析深度）"""
        metar_data = state.get("metar_parsed", {})
        role = state.get("detected_role", "dispatcher")
        risk_level = state.get("risk_level", "LOW")
        risk_factors = state.get("risk_factors", [])
        
        context = self.ROLE_CONTEXT.get(role, self.ROLE_CONTEXT["dispatcher"])
        role_cn = self.ROLE_NAMES_CN.get(role, role)
        
        # 构建基础解释
        parts = []
        
        # 1. 天气概况
        parts.append(f"【天气概况】")
        parts.append(f"机场: {metar_data.get('icao_code', '未知')}")
        parts.append(f"飞行规则: {metar_data.get('flight_rules', '未知')}")
        
        # 2. 关键指标
        parts.append(f"\n【关键指标】")
        if metar_data.get("wind_speed"):
            wind_str = f"风: {metar_data['wind_speed']}KT"
            if metar_data.get("wind_direction"):
                wind_str = f"风: {metar_data['wind_direction']}°/{metar_data['wind_speed']}KT"
            if metar_data.get("wind_gust"):
                wind_str += f" 阵风{metar_data['wind_gust']}KT"
            parts.append(wind_str)
        
        if metar_data.get("visibility") is not None:
            vis_range = format_visibility_range(metar_data["visibility"])
            parts.append(f"能见度: {vis_range}")
        
        weather = metar_data.get("present_weather", [])
        if weather:
            wx_str = "天气现象: " + ", ".join([w.get("description", w.get("code", "")) for w in weather])
            parts.append(wx_str)

        # 温度露点差分析
        temp = metar_data.get("temperature")
        dew = metar_data.get("dewpoint")
        if temp is not None and dew is not None:
            spread = temp - dew
            parts.append(f"温度露点差: {spread}°C")
            if spread <= 3:
                parts.append("  → 温差较小，雾或低云形成风险较高")
            elif spread <= 5:
                parts.append("  → 温差中等，需关注湿度变化趋势")
            else:
                parts.append("  → 温差较大，短期内雾形成风险较低")

        # 云层分析
        cloud_layers = metar_data.get("cloud_layers", [])
        if cloud_layers:
            lowest = min(l["height_feet"] for l in cloud_layers)
            parts.append(f"\n最低云底高: {lowest}ft")
            if lowest < 1000:
                parts.append("  → 云底低，可能影响进近和着陆")
        
        # 3. 风险提示
        parts.append(f"\n【风险等级】{risk_level}")
        parts.append(self.RISK_DESCRIPTIONS.get(risk_level, ""))
        
        if risk_factors:
            parts.append(f"\n【主要风险因素】")
            for factor in risk_factors[:5]:
                parts.append(f"• {factor}")
        else:
            parts.append(f"\n【当前无显著风险因素】")
            parts.append("建议持续监控气象变化，关注温度露点差趋势和风向变化。")
        
        # 4. 角色关注点
        parts.append(f"\n【{role_cn}关注点】")
        parts.append(f"核心关注: {context['focus']}")
        
        return "\n".join(parts)
    
    async def generate_llm_explanation(
        self, 
        state: WorkflowState,
        config: RunnableConfig = None
    ) -> Dict[str, Any]:
        """
        使用LLM生成结构化解释（华为PE工程：CoT + Few-shot + Structured Output）
        
        返回格式：
        {
            "explanation": "自然语言解释",
            "structured_output": {...},  # 角色特定的JSON结构
            "role": "角色名",
            "model_used": "使用的模型"
        }
        """
        await self.init_llm()
        
        metar_data = state.get("metar_parsed", {})
        role = state.get("detected_role", "dispatcher")
        risk_level = state.get("risk_level", "LOW")
        risk_factors = state.get("risk_factors", [])
        raw_metar = state.get("raw_metar", "")
        
        # 获取角色配置
        context = self.ROLE_CONTEXT.get(role, self.ROLE_CONTEXT["dispatcher"])
        role_cn = self.ROLE_NAMES_CN.get(role, role)
        
        # 能见度区间化（传给LLM时同时提供精确值和区间）
        vis_raw = metar_data.get("visibility")
        vis_range = format_visibility_range(vis_raw) if vis_raw is not None else "未知"

        # 构建用户提示词
        user_prompt = f"""请根据以下METAR报文，以{role_cn}角色生成专业的天气解读：

【原始METAR】
{raw_metar}

【解析后的天气数据】
{json.dumps(metar_data, ensure_ascii=False, indent=2)}

【能见度区间（对外展示请使用此格式）】
精确值: {vis_raw}km → 区间: {vis_range}

【风险等级】
{risk_level}

【主要风险因素】
{chr(10).join(f'- {f}' for f in risk_factors[:5]) if risk_factors else '- 当前无显著风险因素'}

【输出要求】
1. 严格按照JSON Schema格式输出，确保所有字段都有合理的值
2. 能见度对外描述必须使用区间（{vis_range}），禁止使用精确数值
3. 即使天气良好，也请深入分析各参数的含义和潜在影响，不要输出模板化的套话
4. 基于当前具体数据给出有针对性的分析，每次分析应体现METAR数据的差异"""
        
        try:
            # 调用LLM
            response = await self.llm_client.generate_with_system_prompt(
                system_prompt=context["system_prompt"],
                user_prompt=user_prompt,
                temperature=0.5,  # 适度提高温度以增加分析多样性，同时保持准确性
                max_tokens=2500  # 增加token上限以支持更深入的分析
            )
            
            # 解析JSON响应
            structured_output = self._parse_json_response(response)
            
            return {
                "explanation": response,
                "structured_output": structured_output,
                "role": role,
                "role_cn": role_cn,
                "model_used": self.llm_client.manager._current_provider,
                "risk_level": risk_level,
                "timestamp": metar_data.get("observation_time", "")
            }
            
        except Exception as e:
            # LLM调用失败，使用基础解释
            print(f"LLM generation failed: {e}")
            basic_explanation = self.generate_basic_explanation(state)
            return {
                "explanation": basic_explanation,
                "structured_output": None,
                "role": role,
                "role_cn": role_cn,
                "model_used": "fallback_rules",
                "error": str(e)
            }
    
    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """解析LLM返回的JSON响应"""
        try:
            # 尝试直接解析
            return json.loads(response)
        except json.JSONDecodeError:
            # 尝试提取JSON块
            import re
            json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(1))
                except:
                    pass
            
            # 尝试找第一个 { 和最后一个 }
            start = response.find('{')
            end = response.rfind('}')
            if start != -1 and end != -1:
                try:
                    return json.loads(response[start:end+1])
                except:
                    pass
            
            return None


# 节点函数（供LangGraph调用）
async def generate_explanation_node(
    state: WorkflowState,
    config: RunnableConfig = None
) -> WorkflowState:
    """
    解释生成节点入口
    
    输入状态：
    - metar_parsed: 解析后的METAR数据
    - detected_role: 检测到的用户角色
    - risk_level: 风险等级
    - risk_factors: 风险因素列表
    - raw_metar: 原始METAR报文
    
    输出状态：
    - explanation: 自然语言解释
    - structured_output: 结构化JSON输出
    """
    generator = ExplanationGenerator()
    result = await generator.generate_llm_explanation(state, config)
    
    # 更新状态
    return {
        **state,
        "explanation": result.get("explanation", ""),
        "structured_output": result.get("structured_output"),
        "model_used": result.get("model_used", "unknown"),
        "generation_metadata": {
            "role": result.get("role"),
            "role_cn": result.get("role_cn"),
            "risk_level": result.get("risk_level"),
            "timestamp": result.get("timestamp")
        }
    }


# 导出
__all__ = ["generate_explanation_node", "ExplanationGenerator"]