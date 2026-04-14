"""
LangGraph工作流图定义
航空气象Agent主工作流：5节点流水线 + 条件路由
"""
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from app.core.workflow_state import WorkflowState
from app.nodes import (
    parse_metar_node,
    classify_role_node,
    assess_risk_node,
    check_safety_node,
    generate_explanation_node,
)


class GraphConfig(TypedDict):
    """工作流配置"""
    recursion_limit: int
    checkpoint_enabled: bool


def should_continue(state: WorkflowState) -> str:
    """
    条件路由：判断工作流是否继续
    - 解析失败 → 直接结束
    - 需要人工干预 → 跳转到解释生成
    - 正常流程 → 继续下一步
    """
    # 检查是否有错误
    if state.get("parse_error"):
        return "end"
    
    # 检查当前节点，决定下一步
    current = state.get("current_node", "")
    
    if current == "parse_metar_node":
        return "classify"
    elif current == "classify_role_node":
        return "assess"
    elif current == "assess_risk_node":
        return "check_safety"
    elif current == "check_safety_node":
        # 安全检查通过 → 生成解释
        # 安全检查未通过 → 仍然生成解释（带警告）
        return "generate"
    elif current == "generate_explanation_node":
        return "end"
    
    return "end"


def create_workflow_graph(config: GraphConfig = None) -> StateGraph:
    """
    创建LangGraph工作流图
    
    节点拓扑：
    START → parse_metar → classify_role → assess_risk → check_safety → generate_explanation → END
                ↓              ↓              ↓               ↓
              (失败)        (继续)         (继续)        (干预/继续)
                ↓              ↓              ↓               ↓
               END           继续           继续          生成解释
    """
    # 创建状态图
    workflow = StateGraph(WorkflowState)
    
    # 添加节点
    workflow.add_node("parse_metar", parse_metar_node)
    workflow.add_node("classify_role", classify_role_node)
    workflow.add_node("assess_risk", assess_risk_node)
    workflow.add_node("check_safety", check_safety_node)
    workflow.add_node("generate_explanation", generate_explanation_node)
    
    # 设置入口点
    workflow.set_entry_point("parse_metar")
    
    # 添加边 - 使用条件路由
    workflow.add_conditional_edges(
        "parse_metar",
        should_continue,
        {
            "classify": "classify_role",
            "end": END,
        }
    )
    
    workflow.add_conditional_edges(
        "classify_role",
        should_continue,
        {
            "assess": "assess_risk",
            "end": END,
        }
    )
    
    workflow.add_conditional_edges(
        "assess_risk",
        should_continue,
        {
            "check_safety": "check_safety",
            "end": END,
        }
    )
    
    workflow.add_conditional_edges(
        "check_safety",
        should_continue,
        {
            "generate": "generate_explanation",
            "end": END,
        }
    )
    
    workflow.add_edge("generate_explanation", END)
    
    return workflow


def compile_workflow(config: GraphConfig = None):
    """
    编译工作流为可执行应用
    
    Args:
        config: 工作流配置
        
    Returns:
        Compiled LangGraph application
    """
    graph = create_workflow_graph(config)
    
    # 配置检查点（可选）
    checkpointer = None
    if config and config.get("checkpoint_enabled"):
        checkpointer = MemorySaver()
    
    # 编译
    app = graph.compile(
        checkpointer=checkpointer,
        interrupt_before=[],  # 不在特定节点前中断
        interrupt_after=[],   # 不在特定节点后中断
    )
    
    return app


# 预编译的工作流应用（全局单例）
_workflow_app = None


def get_workflow_app():
    """获取工作流应用实例（单例模式）"""
    global _workflow_app

    if _workflow_app is None:
        config = GraphConfig(
            recursion_limit=500,
            checkpoint_enabled=False,
        )
        _workflow_app = compile_workflow(config)

    return _workflow_app


async def run_workflow(
    metar_raw: str,
    user_query: str = "",
    user_role: str = None,
    session_id: str = None,
) -> WorkflowState:
    """
    运行完整工作流
    
    Args:
        metar_raw: 原始METAR报文
        user_query: 用户问题（可选）
        user_role: 用户角色（可选，pilot/dispatcher/forecaster/ground_crew）
        session_id: 会话ID（可选，用于checkpoint）
        
    Returns:
        最终工作流状态
    """
    app = get_workflow_app()
    
    # 初始化状态
    initial_state = {
        "metar_raw": metar_raw,
        "user_query": user_query,
        "user_role": user_role,
        "session_id": session_id,
    }
    
    # 执行工作流
    result = await app.ainvoke(initial_state)
    
    return result


# 导出
__all__ = [
    "create_workflow_graph",
    "compile_workflow",
    "get_workflow_app",
    "run_workflow",
    "WorkflowState",
]
