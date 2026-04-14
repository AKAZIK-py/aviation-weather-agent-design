"""
角色独立报告生成器模块

4 个独立的角色报告生成器，彻底分离上下文污染：
- PilotReporter: 飞行员视角，关注飞行安全与起降决策
- DispatcherReporter: 签派员视角，关注航班运行效率
- ForecasterReporter: 预报员视角，关注天气趋势研判
- GroundCrewReporter: 地勤机务视角，关注地面作业安全
"""

from app.services.role_reporters.base import BaseReporter
from app.services.role_reporters.pilot import PilotReporter
from app.services.role_reporters.dispatcher import DispatcherReporter
from app.services.role_reporters.forecaster import ForecasterReporter
from app.services.role_reporters.ground_crew import GroundCrewReporter


# 角色到报告生成器的映射
_REPORTER_REGISTRY = {
    "pilot": PilotReporter,
    "dispatcher": DispatcherReporter,
    "forecaster": ForecasterReporter,
    "ground_crew": GroundCrewReporter,
}


def get_reporter(role: str) -> BaseReporter:
    """
    工厂函数：根据角色获取对应的报告生成器实例

    Args:
        role: 角色标识 (pilot/dispatcher/forecaster/ground_crew)

    Returns:
        对应角色的报告生成器实例

    Raises:
        ValueError: 未知角色
    """
    reporter_cls = _REPORTER_REGISTRY.get(role)
    if reporter_cls is None:
        # 默认使用 dispatcher
        reporter_cls = DispatcherReporter
    return reporter_cls()


__all__ = [
    "BaseReporter",
    "PilotReporter",
    "DispatcherReporter",
    "ForecasterReporter",
    "GroundCrewReporter",
    "get_reporter",
]
