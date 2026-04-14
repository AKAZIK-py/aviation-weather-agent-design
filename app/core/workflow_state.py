"""
LangGraph工作流状态定义
使用TypedDict定义状态结构，支持LangGraph的状态管理

schema_version: 2.1.0
"""
from typing import TypedDict, Optional, List, Dict, Any, Annotated, Tuple
from operator import add


# Schema版本常量
SCHEMA_VERSION = "2.1.0"

# 别名，方便导入
AgentState = None  # 将在类定义后设置

class WorkflowState(TypedDict):
    """
    LangGraph工作流状态
    
    使用Annotated支持状态累加（如reasoning_trace）
    Schema版本: 2.1.0
    """
    # ===== Schema版本 =====
    schema_version: str                         # 状态schema版本号

    # ===== 输入字段 =====
    metar_raw: str                              # 原始METAR报文
    user_query: Optional[str]                   # 用户自然语言查询
    user_role: Optional[str]                    # 用户角色（如果已知）
    
    # ===== 中间状态字段 =====
    # METAR解析结果
    metar_parsed: Optional[Dict[str, Any]]      # 解析后的METAR数据
    parse_success: bool                         # 解析是否成功
    parse_errors: List[str]                     # 解析错误信息
    
    # 角色识别
    detected_role: Optional[str]                # 检测到的用户角色
    role_confidence: float                      # 角色识别置信度
    role_keywords: List[str]                    # 角色关键词
    
    # 风险评估
    risk_level: str                             # 风险等级 (LOW/MEDIUM/HIGH/CRITICAL)
    risk_factors: List[str]                     # 风险因素列表
    risk_reasoning: str                         # 风险评估理由
    
    # 安全边界检查
    safety_check_passed: bool                   # 安全边界检查是否通过
    safety_violations: List[str]                # 安全违规列表
    intervention_required: bool                 # 是否需要人工干预
    intervention_reason: Optional[str]          # 干预原因
    
    # ===== 输出字段 =====
    explanation: Optional[str]                  # 生成的气象解释
    confidence_score: float                     # 置信度分数
    reasoning_trace: Annotated[List[str], add]  # 推理过程追踪（累加）
    
    # ===== 元数据字段 =====
    processing_time: float                      # 处理时间(秒)
    llm_calls: int                              # LLM调用次数
    token_usage: Dict[str, int]                 # Token使用统计
    current_node: str                           # 当前执行的节点名称
    error: Optional[str]                        # 错误信息


# Schema JSON描述（用于验证和文档）
WORKFLOW_STATE_SCHEMA = {
    "schema_version": SCHEMA_VERSION,
    "required_fields": [
        "schema_version", "metar_raw", "parse_success", "parse_errors",
        "role_confidence", "role_keywords", "risk_level", "risk_factors",
        "risk_reasoning", "safety_check_passed", "safety_violations",
        "intervention_required", "confidence_score", "reasoning_trace",
        "processing_time", "llm_calls", "token_usage", "current_node",
    ],
    "optional_fields": [
        "user_query", "user_role", "metar_parsed", "detected_role",
        "explanation", "intervention_reason", "error",
    ],
    "field_types": {
        "schema_version": str,
        "metar_raw": str,
        "user_query": (str, type(None)),
        "user_role": (str, type(None)),
        "metar_parsed": (dict, type(None)),
        "parse_success": bool,
        "parse_errors": list,
        "detected_role": (str, type(None)),
        "role_confidence": (int, float),
        "role_keywords": list,
        "risk_level": str,
        "risk_factors": list,
        "risk_reasoning": str,
        "safety_check_passed": bool,
        "safety_violations": list,
        "intervention_required": bool,
        "intervention_reason": (str, type(None)),
        "explanation": (str, type(None)),
        "confidence_score": (int, float),
        "reasoning_trace": list,
        "processing_time": (int, float),
        "llm_calls": int,
        "token_usage": dict,
        "current_node": str,
        "error": (str, type(None)),
    },
    "valid_risk_levels": ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
    "valid_roles": ["pilot", "dispatcher", "forecaster", "ground_crew", None],
}


def validate_state(state: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    校验WorkflowState字典的完整性

    Args:
        state: 待校验的状态字典

    Returns:
        (is_valid, errors): 是否有效 + 错误列表
    """
    errors: List[str] = []

    # 1. 检查必填字段
    for field in WORKFLOW_STATE_SCHEMA["required_fields"]:
        if field not in state:
            errors.append(f"缺少必填字段: {field}")

    # 2. 检查字段类型
    for field, expected_type in WORKFLOW_STATE_SCHEMA["field_types"].items():
        if field not in state:
            continue
        value = state[field]
        if not isinstance(value, expected_type):
            errors.append(
                f"字段'{field}'类型错误: 期望{expected_type}, 实际{type(value)}"
            )

    # 3. 检查枚举值
    if "risk_level" in state:
        if state["risk_level"] not in WORKFLOW_STATE_SCHEMA["valid_risk_levels"]:
            errors.append(
                f"无效risk_level='{state['risk_level']}'，"
                f"可选: {WORKFLOW_STATE_SCHEMA['valid_risk_levels']}"
            )

    if "detected_role" in state and state["detected_role"] is not None:
        if state["detected_role"] not in WORKFLOW_STATE_SCHEMA["valid_roles"]:
            errors.append(
                f"无效detected_role='{state['detected_role']}'，"
                f"可选: {WORKFLOW_STATE_SCHEMA['valid_roles']}"
            )

    # 4. 检查schema_version兼容性
    if "schema_version" in state:
        version = state["schema_version"]
        if not isinstance(version, str):
            errors.append(f"schema_version必须为字符串，实际: {type(version)}")
        elif not version.startswith("2."):
            errors.append(f"不兼容的schema版本: {version} (当前: {SCHEMA_VERSION})")

    return len(errors) == 0, errors


def state_to_dict(state: WorkflowState) -> Dict[str, Any]:
    """将WorkflowState转为普通字典（用于JSON序列化）"""
    return dict(state)


def dict_to_state(data: Dict[str, Any]) -> WorkflowState:
    """
    从字典恢复WorkflowState（用于JSON反序列化）
    自动注入缺失的schema_version
    """
    if "schema_version" not in data:
        data["schema_version"] = SCHEMA_VERSION
    return data  # TypedDict本质就是dict


# 初始状态工厂函数
def create_initial_state(
    metar_raw: str,
    user_query: Optional[str] = None,
    user_role: Optional[str] = None
) -> WorkflowState:
    """创建初始工作流状态"""
    return {
        # Schema版本
        "schema_version": SCHEMA_VERSION,

        # 输入
        "metar_raw": metar_raw,
        "user_query": user_query,
        "user_role": user_role,
        
        # METAR解析
        "metar_parsed": None,
        "parse_success": False,
        "parse_errors": [],
        
        # 角色识别
        "detected_role": None,
        "role_confidence": 0.0,
        "role_keywords": [],
        
        # 风险评估
        "risk_level": "LOW",
        "risk_factors": [],
        "risk_reasoning": "",
        
        # 安全检查
        "safety_check_passed": True,
        "safety_violations": [],
        "intervention_required": False,
        "intervention_reason": None,
        
        # 输出
        "explanation": None,
        "confidence_score": 0.0,
        "reasoning_trace": [],
        
        # 元数据
        "processing_time": 0.0,
        "llm_calls": 0,
        "token_usage": {},
        "current_node": "start",
        "error": None,
    }

# 别名，方便导入
AgentState = WorkflowState
