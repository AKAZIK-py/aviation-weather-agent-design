"""
安全边界检查节点 - check_safety_node
职责：检查是否需要人工干预，确保安全边界
D3指标要求：安全边界=100%
"""
from typing import Dict, Any, List
from langchain_core.runnables import RunnableConfig

from app.core.workflow_state import WorkflowState


class SafetyChecker:
    """安全边界检查器"""
    
    # 安全边界规则
    SAFETY_RULES = {
        # CRITICAL风险必须人工干预
        "critical_risk": {
            "condition": lambda state: state.get("risk_level") == "CRITICAL",
            "violation": "CRITICAL风险等级需要人工评估",
            "requires_intervention": True,
        },
        
        # IFR/LIFR天气需要人工确认
        "ifr_weather": {
            "condition": lambda state: state.get("metar_parsed", {}).get("flight_rules") in ["IFR", "LIFR"],
            "violation": "IFR/LIFR天气条件，需要人工确认运行计划",
            "requires_intervention": True,
        },
        
        # 雷暴活动需要人工干预
        "thunderstorm": {
            "condition": lambda state: any(
                "TS" in w.get("code", "") 
                for w in state.get("metar_parsed", {}).get("present_weather", [])
            ),
            "violation": "雷暴活动需要人工评估飞行安全",
            "requires_intervention": True,
        },
        
        # 极低能见度需要人工干预
        "low_visibility": {
            "condition": lambda state: state.get("metar_parsed", {}).get("visibility", 10) < 0.8,
            "violation": "能见度低于800米，需要人工决策",
            "requires_intervention": True,
        },
        
        # 强侧风需要人工确认
        "strong_crosswind": {
            "condition": lambda state: state.get("metar_parsed", {}).get("wind_speed", 0) > 30,
            "violation": "风速超过30KT，需要评估侧风限制",
            "requires_intervention": True,
        },
        
        # 冻雨/冻雾需要人工干预
        "freezing_conditions": {
            "condition": lambda state: any(
                "FZ" in w.get("code", "") 
                for w in state.get("metar_parsed", {}).get("present_weather", [])
            ),
            "violation": "冻雨/冻雾条件，需要评估除冰需求",
            "requires_intervention": True,
        },
    }
    
    # 角色特定安全规则
    ROLE_SAFETY_RULES = {
        "空管": [
            {
                "name": "跑道占用确认",
                "condition": lambda state: state.get("risk_level") in ["HIGH", "CRITICAL"],
                "violation": "高风险天气，需要确认跑道占用情况",
            },
        ],
        "机务": [
            {
                "name": "户外作业限制",
                "condition": lambda state: state.get("metar_parsed", {}).get("wind_speed", 0) > 25,
                "violation": "风速超过25KT，需要评估户外作业安全",
            },
        ],
    }
    
    def check(self, state: WorkflowState) -> Dict[str, Any]:
        """
        执行安全边界检查
        
        Returns:
            {
                "passed": bool,
                "violations": List[str],
                "intervention_required": bool,
                "intervention_reason": str
            }
        """
        violations = []
        intervention_required = False
        intervention_reasons = []
        
        # 检查通用安全规则
        for rule_name, rule in self.SAFETY_RULES.items():
            try:
                if rule["condition"](state):
                    violations.append(rule["violation"])
                    if rule["requires_intervention"]:
                        intervention_required = True
                        intervention_reasons.append(rule["violation"])
            except Exception as e:
                # 规则检查失败，记录但继续
                violations.append(f"规则检查异常[{rule_name}]: {str(e)}")
        
        # 检查角色特定规则
        role = state.get("detected_role", "运控")
        role_rules = self.ROLE_SAFETY_RULES.get(role, [])
        
        for rule in role_rules:
            try:
                if rule["condition"](state):
                    violations.append(rule["violation"])
                    intervention_reasons.append(rule["violation"])
            except Exception:
                pass
        
        # 如果有违规，默认需要干预
        if violations and not intervention_required:
            intervention_required = True
            intervention_reasons = violations[:1]  # 至少记录一个原因
        
        return {
            "passed": len(violations) == 0,
            "violations": violations,
            "intervention_required": intervention_required,
            "intervention_reason": "；".join(intervention_reasons) if intervention_reasons else None,
        }


async def check_safety_node(
    state: WorkflowState, 
    config: RunnableConfig
) -> Dict[str, Any]:
    """安全边界检查节点"""
    checker = SafetyChecker()
    result = checker.check(state)
    
    updates = {
        "safety_check_passed": result["passed"],
        "safety_violations": result["violations"],
        "intervention_required": result["intervention_required"],
        "intervention_reason": result["intervention_reason"],
        "current_node": "check_safety_node",
    }
    
    trace_msg = f"[check_safety_node] 安全检查{'通过' if result['passed'] else '未通过'}"
    if result["violations"]:
        trace_msg += f"，违规: {len(result['violations'])}项"
    
    updates["reasoning_trace"] = [trace_msg]
    
    return updates