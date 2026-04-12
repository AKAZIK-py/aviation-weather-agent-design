"""
状态验证器 - WorkflowState的深度校验
职责：校验状态完整性、字段类型、枚举值有效性
"""
from typing import Dict, Any, List, Tuple, Optional
import json


class StateValidator:
    """工作流状态验证器"""

    # 必填字段
    REQUIRED_FIELDS = [
        "metar_raw",
    ]

    # 完整字段集（含可选的默认值字段）
    ALL_FIELDS = [
        "schema_version", "metar_raw", "user_query", "user_role",
        "metar_parsed", "parse_success", "parse_errors",
        "detected_role", "role_confidence", "role_keywords",
        "risk_level", "risk_factors", "risk_reasoning",
        "safety_check_passed", "safety_violations",
        "intervention_required", "intervention_reason",
        "explanation", "confidence_score", "reasoning_trace",
        "processing_time", "llm_calls", "token_usage",
        "current_node", "error",
    ]

    # 字段类型映射
    FIELD_TYPES = {
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
    }

    # 枚举值约束
    VALID_RISK_LEVELS = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
    VALID_ROLES = {"pilot", "dispatcher", "forecaster", "ground_crew"}

    def validate_state(self, state: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        全面校验状态字典

        Args:
            state: 待校验的状态字典

        Returns:
            (is_valid, errors): 校验结果和错误列表
        """
        errors: List[str] = []

        # 1. 必填字段检查
        errors.extend(self._check_required_fields(state))

        # 2. 字段类型检查
        errors.extend(self._check_field_types(state))

        # 3. 枚举值检查
        errors.extend(self._check_enums(state))

        # 4. 业务规则检查
        errors.extend(self._check_business_rules(state))

        return len(errors) == 0, errors

    def _check_required_fields(self, state: Dict[str, Any]) -> List[str]:
        """检查必填字段"""
        errors = []
        for field in self.REQUIRED_FIELDS:
            if field not in state:
                errors.append(f"缺少必填字段: {field}")
            elif state[field] is None:
                errors.append(f"必填字段'{field}'不能为None")
            elif isinstance(state[field], str) and not state[field].strip():
                errors.append(f"必填字段'{field}'不能为空字符串")
        return errors

    def _check_field_types(self, state: Dict[str, Any]) -> List[str]:
        """检查字段类型"""
        errors = []
        for field, expected_type in self.FIELD_TYPES.items():
            if field not in state:
                continue
            value = state[field]
            if not isinstance(value, expected_type):
                type_name = (
                    expected_type.__name__
                    if hasattr(expected_type, "__name__")
                    else str(expected_type)
                )
                errors.append(
                    f"字段'{field}'类型错误: 期望{type_name}, 实际{type(value).__name__}"
                )
        return errors

    def _check_enums(self, state: Dict[str, Any]) -> List[str]:
        """检查枚举值有效性"""
        errors = []

        # risk_level
        if "risk_level" in state:
            rl = state["risk_level"]
            if rl not in self.VALID_RISK_LEVELS:
                errors.append(
                    f"无效risk_level='{rl}'，可选: {sorted(self.VALID_RISK_LEVELS)}"
                )

        # detected_role
        if "detected_role" in state:
            dr = state["detected_role"]
            if dr is not None and dr not in self.VALID_ROLES:
                errors.append(
                    f"无效detected_role='{dr}'，可选: {sorted(self.VALID_ROLES)}"
                )

        # user_role
        if "user_role" in state:
            ur = state["user_role"]
            if ur is not None and ur not in self.VALID_ROLES:
                errors.append(
                    f"无效user_role='{ur}'，可选: {sorted(self.VALID_ROLES)}"
                )

        return errors

    def _check_business_rules(self, state: Dict[str, Any]) -> List[str]:
        """检查业务规则一致性"""
        errors = []

        # 解析成功时 metar_parsed 不能为空
        if state.get("parse_success") and state.get("metar_parsed") is None:
            errors.append("parse_success=True时metar_parsed不能为空")

        # 有detected_role时role_confidence应>0
        if state.get("detected_role") and state.get("role_confidence", 0) <= 0:
            errors.append("detected_role非空时role_confidence应大于0")

        # intervention_required为True时intervention_reason不能为空
        if state.get("intervention_required") and not state.get("intervention_reason"):
            errors.append("intervention_required=True时intervention_reason不能为空")

        return errors

    def validate_and_raise(self, state: Dict[str, Any]) -> None:
        """校验状态，失败时抛出异常"""
        is_valid, errors = self.validate_state(state)
        if not is_valid:
            raise StateValidationError(errors)

    def to_json_schema(self) -> Dict[str, Any]:
        """生成JSON Schema描述（用于API文档）"""
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "title": "WorkflowState",
            "type": "object",
            "required": self.REQUIRED_FIELDS,
            "properties": {
                "schema_version": {"type": "string", "const": "2.1.0"},
                "metar_raw": {"type": "string", "minLength": 1},
                "user_query": {"type": ["string", "null"]},
                "user_role": {"type": ["string", "null"], "enum": list(self.VALID_ROLES) + [None]},
                "metar_parsed": {"type": ["object", "null"]},
                "parse_success": {"type": "boolean"},
                "parse_errors": {"type": "array", "items": {"type": "string"}},
                "detected_role": {"type": ["string", "null"], "enum": list(self.VALID_ROLES) + [None]},
                "role_confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "role_keywords": {"type": "array", "items": {"type": "string"}},
                "risk_level": {"type": "string", "enum": list(self.VALID_RISK_LEVELS)},
                "risk_factors": {"type": "array", "items": {"type": "string"}},
                "risk_reasoning": {"type": "string"},
                "safety_check_passed": {"type": "boolean"},
                "safety_violations": {"type": "array", "items": {"type": "string"}},
                "intervention_required": {"type": "boolean"},
                "intervention_reason": {"type": ["string", "null"]},
                "explanation": {"type": ["string", "null"]},
                "confidence_score": {"type": "number", "minimum": 0, "maximum": 1},
                "reasoning_trace": {"type": "array", "items": {"type": "string"}},
                "processing_time": {"type": "number", "minimum": 0},
                "llm_calls": {"type": "integer", "minimum": 0},
                "token_usage": {"type": "object"},
                "current_node": {"type": "string"},
                "error": {"type": ["string", "null"]},
            },
        }


class StateValidationError(Exception):
    """状态校验异常"""

    def __init__(self, errors: List[str]):
        self.errors = errors
        super().__init__(f"状态校验失败: {'; '.join(errors)}")


# 模块级便捷实例
_validator = StateValidator()


def validate_state(state: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """模块级便捷校验函数"""
    return _validator.validate_state(state)


__all__ = [
    "StateValidator",
    "StateValidationError",
    "validate_state",
]
