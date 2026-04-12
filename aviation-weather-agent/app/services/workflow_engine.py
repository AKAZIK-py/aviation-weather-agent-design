"""
工作流引擎服务 - 完整的8步METAR分析流水线
职责：协调各个节点，实现完整的分析流程

流程：
Step 1: 机场选择 (ICAO验证)
Step 2: METAR获取 (实时/模拟)
Step 3: METAR解析 (parse_metar_node)
Step 4: 角色分类 (classify_role_node)
Step 5: LLM分析 (generate_explanation_node with PE策略)
Step 6: 风险评估 (assess_risk_node)
Step 7: 生成报告 (report_generator)
Step 8: 返回结构化响应
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging
import uuid
import time

from app.services.metar_fetcher import fetch_metar_for_airport, MetarFetchError
from app.services.report_generator import get_report_generator
from app.nodes.parse_metar_node import parse_metar_node
from app.nodes.classify_role_node import classify_role_node
from app.nodes.assess_risk_node import assess_risk_node
from app.nodes.generate_explanation_node import generate_explanation_node
from app.prompts import build_analysis_prompt, get_system_prompt
from app.services.cache import get_cache_service
from app.core.observability import get_metrics, get_tracer


logger = logging.getLogger(__name__)


class WorkflowEngine:
    """工作流引擎 - 完整的分析流水线"""

    def __init__(self):
        self.report_generator = get_report_generator()
        self.cache = get_cache_service()
        self.metrics = get_metrics()
        self.tracer = get_tracer()

    async def run_full_workflow(
        self,
        airport_icao: Optional[str] = None,
        metar_raw: Optional[str] = None,
        user_query: Optional[str] = None,
        user_role: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        运行完整的8步工作流

        Args:
            airport_icao: 机场ICAO代码（与metar_raw二选一）
            metar_raw: 原始METAR报文（与airport_icao二选一）
            user_query: 用户查询
            user_role: 用户角色
            session_id: 会话ID

        Returns:
            完整的分析结果，包含报告和警报
        """
        # 生成会话ID
        if not session_id:
            session_id = str(uuid.uuid4())

        workflow_start_time = datetime.now()

        self.metrics.active_requests.inc()
        try:
            # ========== Step 1: 机场选择 & ICAO验证 ==========
            logger.info(f"[{session_id}] Step 1: 机场选择")
            if airport_icao:
                # 验证ICAO格式
                if not self._validate_icao(airport_icao):
                    raise ValueError(f"无效的ICAO代码: {airport_icao}")
                airport_icao = airport_icao.upper()

            # ========== Step 2: METAR获取 ==========
            logger.info(f"[{session_id}] Step 2: METAR获取")
            metar_metadata = None

            if airport_icao and not metar_raw:
                # 从机场ICAO获取实时METAR
                try:
                    metar_raw, metar_metadata = await fetch_metar_for_airport(airport_icao)
                    logger.info(f"[{session_id}] 获取到METAR: {metar_raw[:50]}...")
                    self.metrics.metar_fetch_total.labels(source="api", status="success").inc()
                except MetarFetchError as e:
                    logger.error(f"[{session_id}] METAR获取失败: {e}")
                    self.metrics.metar_fetch_total.labels(source="api", status="error").inc()
                    raise ValueError(f"无法获取机场 {airport_icao} 的METAR数据: {str(e)}")
            elif not metar_raw:
                raise ValueError("必须提供 airport_icao 或 metar_raw 参数")

            # ========== Step 3: METAR解析 ==========
            async with self.tracer.trace("parse_metar_node"):
                logger.info(f"[{session_id}] Step 3: METAR解析")
                state = {
                    "metar_raw": metar_raw,
                    "user_query": user_query or "",
                    "user_role": user_role,
                    "session_id": session_id,
                }

                parse_result = await parse_metar_node(state, None)
                state.update(parse_result)

                if state.get("parse_error"):
                    raise ValueError(f"METAR解析失败: {state['parse_error']}")

                metar_parsed = state.get("metar_parsed", {})

            # ========== Step 4: 角色分类 ==========
            async with self.tracer.trace("classify_role_node"):
                logger.info(f"[{session_id}] Step 4: 角色分类")
                classify_result = await classify_role_node(state, None)
                state.update(classify_result)

            detected_role = state.get("detected_role", "dispatcher")

            # ========== Step 4.5: 缓存检查 ==========
            # 在解析完成后、LLM分析前检查缓存
            cached_analysis = await self.cache.get_metar_cache(metar_raw, detected_role)
            if cached_analysis:
                logger.info(f"[{session_id}] Cache HIT for METAR analysis")
                self.metrics.record_cache_access("L1", hit=True)
                # 使用缓存的分析结果
                state.update({
                    "explanation": cached_analysis.get("explanation", ""),
                    "structured_output": cached_analysis.get("structured_output"),
                    "model_used": "cached",
                })
            else:
                self.metrics.record_cache_access("analysis", hit=False)
                
                # ========== Step 5: LLM分析 (with PE组合策略) ==========
                async with self.tracer.trace("generate_explanation_node"):
                    logger.info(f"[{session_id}] Step 5: LLM分析 (角色: {detected_role})")
                    llm_start = time.time()
                    explanation_result = await generate_explanation_node(state, None)
                    llm_duration = time.time() - llm_start
                    state.update(explanation_result)
                    
                    # 记录LLM调用指标
                    model_used = state.get("model_used", "unknown")
                    self.metrics.record_llm_call(
                        model=model_used,
                        node="generate_explanation",
                        duration=llm_duration,
                        status="success" if explanation_result.get("explanation") else "fallback",
                    )
                
                # 将分析结果写入缓存
                await self.cache.set_metar_cache(metar_raw, detected_role, {
                    "explanation": state.get("explanation", ""),
                    "structured_output": state.get("structured_output"),
                })

            # 获取结构化分析结果
            structured_analysis = state.get("structured_output", {})

            # ========== Step 6: 风险评估 ==========
            async with self.tracer.trace("assess_risk_node"):
                logger.info(f"[{session_id}] Step 6: 风险评估")
                risk_result = await assess_risk_node(state, None)
                state.update(risk_result)

            risk_level = state.get("risk_level", "LOW")
            risk_factors = state.get("risk_factors", [])

            # ========== Step 7: 生成角色报告 ==========
            logger.info(f"[{session_id}] Step 7: 生成{detected_role}报告")
            report = await self.report_generator.generate_role_report(
                role=detected_role,
                metar_data=metar_parsed,
                analysis_result=structured_analysis,
                risk_level=risk_level,
                risk_factors=risk_factors,
                raw_metar=metar_raw
            )

            # ========== Step 8: 构建最终响应 ==========
            logger.info(f"[{session_id}] Step 8: 构建响应")
            workflow_end_time = datetime.now()
            processing_time_ms = (workflow_end_time - workflow_start_time).total_seconds() * 1000

            final_response = {
                "success": True,
                "session_id": session_id,
                "airport_icao": metar_parsed.get("icao_code", airport_icao or "UNKNOWN"),
                "observation_time": metar_parsed.get("observation_time", ""),
                "raw_metar": metar_raw,

                # METAR解析结果
                "metar_parsed": metar_parsed,

                # 角色识别
                "detected_role": detected_role,
                "role_confidence": state.get("role_confidence", 0.0),

                # 风险评估
                "risk_level": risk_level,
                "risk_factors": risk_factors,

                # LLM分析结果
                "explanation": state.get("explanation", ""),
                "structured_analysis": structured_analysis,

                # 角色报告
                "role_report": report,

                # 元数据
                "metar_metadata": metar_metadata,
                "model_used": state.get("model_used", "unknown"),
                "llm_calls": state.get("llm_calls", 0),
                "processing_time_ms": processing_time_ms,
                "generated_at": workflow_end_time.isoformat(),

                # 推理追踪
                "reasoning_trace": state.get("reasoning_trace", []),
            }

            logger.info(
                f"[{session_id}] 工作流完成: "
                f"角色={detected_role}, 风险={risk_level}, "
                f"耗时={processing_time_ms:.2f}ms"
            )
            
            # 记录工作流和 METAR 分析指标
            self.metrics.record_workflow(
                duration=processing_time_ms / 1000.0,
                success=True,
            )
            flight_rules = metar_parsed.get("flight_rules", "UNKNOWN")
            self.metrics.record_metar_analysis(
                flight_rules=flight_rules,
                risk_level=risk_level,
            )
            
            # 记录安全干预（如果有高风险因素）
            if risk_level in ("HIGH", "CRITICAL"):
                for factor in risk_factors[:3]:
                    self.metrics.record_safety_intervention(
                        risk_type=str(factor)[:50],
                        action="alert",
                    )

            return final_response

        except Exception as e:
            logger.error(f"[{session_id}] 工作流失败: {e}", exc_info=True)

            workflow_end_time = datetime.now()
            processing_time_ms = (workflow_end_time - workflow_start_time).total_seconds() * 1000
            
            # 记录失败的工作流指标
            self.metrics.record_workflow(
                duration=processing_time_ms / 1000.0,
                success=False,
            )

            return {
                "success": False,
                "session_id": session_id,
                "error": str(e),
                "processing_time_ms": processing_time_ms,
                "generated_at": workflow_end_time.isoformat(),
            }
        finally:
            self.metrics.active_requests.dec()

    def _validate_icao(self, icao: str) -> bool:
        """
        验证ICAO代码格式

        Args:
            icao: ICAO代码

        Returns:
            是否有效
        """
        if not icao:
            return False

        # ICAO代码应为4个字母
        icao = icao.upper().strip()
        return len(icao) == 4 and icao.isalpha()

    async def get_metar_for_airport(self, icao: str) -> Dict[str, Any]:
        """
        获取指定机场的METAR数据（单独接口）

        Args:
            icao: 机场ICAO代码

        Returns:
            METAR数据
        """
        if not self._validate_icao(icao):
            raise ValueError(f"无效的ICAO代码: {icao}")

        icao = icao.upper()

        try:
            metar_raw, metar_metadata = await fetch_metar_for_airport(icao)

            # 解析METAR
            state = {"metar_raw": metar_raw}
            parse_result = await parse_metar_node(state, None)

            return {
                "success": True,
                "airport_icao": icao,
                "raw_metar": metar_raw,
                "metar_parsed": parse_result.get("metar_parsed"),
                "metar_metadata": metar_metadata,
                "fetched_at": datetime.now().isoformat(),
            }

        except MetarFetchError as e:
            logger.error(f"METAR获取失败: {e}")
            return {
                "success": False,
                "airport_icao": icao,
                "error": str(e),
            }

    async def get_role_specific_report(
        self,
        icao: str,
        role: str,
        user_query: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取指定机场和角色的专属报告

        Args:
            icao: 机场ICAO代码
            role: 角色 (pilot/dispatcher/forecaster/ground_crew)
            user_query: 用户查询

        Returns:
            角色专属报告
        """
        # 运行完整工作流，但指定角色
        result = await self.run_full_workflow(
            airport_icao=icao,
            user_query=user_query,
            user_role=role
        )

        if result.get("success"):
            return {
                "success": True,
                "role_report": result.get("role_report"),
                "metar_parsed": result.get("metar_parsed"),
                "risk_level": result.get("risk_level"),
            }
        else:
            return result


# 单例实例
_workflow_engine: Optional[WorkflowEngine] = None


def get_workflow_engine() -> WorkflowEngine:
    """获取工作流引擎实例（单例模式）"""
    global _workflow_engine
    if _workflow_engine is None:
        _workflow_engine = WorkflowEngine()
    return _workflow_engine


# 导出
__all__ = ["WorkflowEngine", "get_workflow_engine"]
