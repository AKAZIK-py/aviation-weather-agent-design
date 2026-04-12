"""
报告生成服务 - 角色特定的天气分析报告生成
职责：基于分析结果生成结构化的角色专属报告和警报

使用 4 个独立的角色报告生成器（role_reporters），彻底分离上下文污染。
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
import json
import logging

from app.core.llm_client import get_llm_client
from app.prompts import (
    get_system_prompt,
    build_report_prompt,
    build_alert_prompt,
    get_role_name_cn,
)
from app.services.personalization import PersonalizationEngine
from app.services.role_reporters import get_reporter
from app.utils.visibility import format_visibility_range
from app.utils.approach import format_decision_info


logger = logging.getLogger(__name__)


# 固定能力边界免责声明（独立字段，不嵌入 report_text）
SYSTEM_DISCLAIMER = "本系统遵循 ICAO Annex 3 标准。METAR 解析由 AI 独立完成，飞行规则需签派/飞行员复核，进近 DH/MDA 仅供参考，签派放行为法定人工决策。"


def _build_role_summary(
    risk_level: str,
    risk_factors: List[str],
    role: Optional[str] = None,
) -> Dict[str, str]:
    """
    根据 risk_level 和 risk_factors 动态生成角色摘要。

    如果提供了 role，则使用对应 Reporter 过滤风险因素后再生成 headlines，
    确保摘要内容只包含该角色关注的信息。

    Returns:
        {headlines: [str], decision: str, confidence: str}
    """
    # 如果指定了角色，使用 reporter 过滤风险因素
    if role:
        reporter = get_reporter(role)
        risk_factors = reporter.filter_risk_factors(risk_factors, role)

    # headlines: 取最关键的 3 条，精简为短句
    headlines = []
    for f in risk_factors[:3]:
        # 精简为短句：取冒号前或前20字
        short = f.split("：")[0].split(":")[0].strip()
        if len(short) > 20:
            short = short[:20]
        if short:
            headlines.append(short)
    if not headlines:
        headlines = ["天气条件正常"]

    # decision: 根据风险等级
    if risk_level in ("CRITICAL", "HIGH"):
        decision = "NO-GO"
    elif risk_level == "MEDIUM":
        decision = "CAUTION"
    else:
        decision = "GO"

    # confidence: 风险因素越多越确定
    if len(risk_factors) >= 3:
        confidence = "HIGH"
    elif len(risk_factors) >= 1:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    return {
        "headlines": headlines,
        "decision": decision,
        "confidence": confidence,
    }


class ReportGenerator:
    """报告生成器 - 角色特定的报告生成"""

    def __init__(self):
        self.llm_client = None

    async def init_llm(self):
        """初始化LLM客户端"""
        if self.llm_client is None:
            self.llm_client = get_llm_client()

    async def generate_role_report(
        self,
        role: str,
        metar_data: Dict[str, Any],
        analysis_result: Dict[str, Any],
        risk_level: str,
        risk_factors: List[str],
        raw_metar: str,
        flight_phase: Optional[str] = None,
        aircraft_type: Optional[str] = None,
        urgency: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        生成角色特定的天气分析报告

        Args:
            role: 角色 (pilot/dispatcher/forecaster/ground_crew)
            metar_data: 解析后的METAR数据
            analysis_result: LLM分析结果
            risk_level: 风险等级
            risk_factors: 风险因素列表
            raw_metar: 原始METAR报文

        Returns:
            包含报告和警报的字典
        """
        await self.init_llm()

        # 获取机场信息和观测时间
        airport_icao = metar_data.get("icao_code", "UNKNOWN")
        observation_time = metar_data.get("observation_time", datetime.now().isoformat())

        # 构建系统提示词（使用新的PE组合策略）
        system_prompt = get_system_prompt(role)

        # 多维度个性化增强（可选）
        personalization_context = PersonalizationEngine.build_personalized_prompt(
            metar=raw_metar,
            role=role,
            flight_phase=flight_phase,
            aircraft_type=aircraft_type,
            urgency=urgency,
        )

        # 构建报告生成提示词
        report_prompt = build_report_prompt(
            role=role,
            airport_icao=airport_icao,
            observation_time=observation_time,
            raw_metar=raw_metar,
            analysis_result=analysis_result
        )

        # 注入多维度个性化上下文（增强角色提示，不替换）
        report_prompt = personalization_context + "\n\n" + report_prompt

        # 飞行员角色：注入DH/MDA信息
        if role == "pilot":
            cloud_layers = metar_data.get("cloud_layers", [])
            lowest_cloud = min((l["height_feet"] for l in cloud_layers), default=None)
            dh_info = format_decision_info(cloud_ceiling_ft=lowest_cloud)
            report_prompt += f"\n\n{dh_info}"

        # 低风险时添加深度分析指令
        if risk_level == "LOW":
            report_prompt += """

【低风险深度分析要求】
当前检测为低风险，但这不意味着可以简单带过。请深入分析：
1. 温度露点差分析：当前温差对积冰/雾形成的潜在影响是什么？
2. 风向稳定性：风向是否稳定？变化趋势如何？对进近有何影响？
3. 气压系统含义：当前气压值暗示什么天气系统？未来几小时趋势如何？
4. 季节性风险：结合当前月份，有哪些季节性天气风险需要关注？
5. 边际条件：哪些参数接近风险阈值？如果进一步恶化会怎样？

请给出有深度的分析，而不是"天气良好，正常运行"这样的套话。"""

        try:
            # 调用LLM生成报告
            response = await self.llm_client.ainvoke(
                prompt=report_prompt,
                system_prompt=system_prompt,
                provider="qianfan"  # 使用百度千帆
            )

            report_text = response.content

            # 生成警报（如有）
            alerts = await self._generate_alerts(role, risk_level, risk_factors)

            # 构建角色摘要和免责声明（独立字段，使用角色过滤）
            role_summary = _build_role_summary(risk_level, risk_factors, role)

            # 构建完整报告
            role_cn = get_role_name_cn(role)
            full_report = {
                "role": role,
                "role_cn": role_cn,
                "airport_icao": airport_icao,
                "observation_time": observation_time,
                "risk_level": risk_level,
                "report_text": report_text,
                "role_summary": role_summary,
                "disclaimer": SYSTEM_DISCLAIMER,
                "structured_analysis": analysis_result,
                "alerts": alerts,
                "generated_at": datetime.now().isoformat(),
                "model_used": response.provider,
            }

            return full_report

        except Exception as e:
            logger.error(f"Report generation failed: {e}", exc_info=True)
            # 降级到基础报告
            return self._generate_fallback_report(
                role, metar_data, risk_level, risk_factors, raw_metar
            )

    async def _generate_alerts(
        self,
        role: str,
        risk_level: str,
        risk_factors: List[str]
    ) -> List[Dict[str, Any]]:
        """
        生成警报信息

        Args:
            role: 角色
            risk_level: 风险等级
            risk_factors: 风险因素列表

        Returns:
            警报列表
        """
        alerts = []

        # 根据风险等级生成警报
        if risk_level in ["HIGH", "CRITICAL"]:
            alert_prompt = build_alert_prompt(risk_level, risk_factors)

            try:
                await self.init_llm()
                response = await self.llm_client.ainvoke(
                    prompt=alert_prompt,
                    system_prompt="你是航空气象警报专家，负责生成清晰、准确的气象警报。"
                )

                alert = {
                    "level": risk_level,
                    "icon": self._get_alert_icon(risk_level),
                    "content": response.content,
                    "factors": risk_factors,
                    "timestamp": datetime.now().isoformat(),
                }
                alerts.append(alert)

            except Exception as e:
                logger.error(f"Alert generation failed: {e}")
                # 使用基础警报
                alerts.append(self._generate_basic_alert(risk_level, risk_factors))

        return alerts

    def _generate_basic_alert(
        self,
        risk_level: str,
        risk_factors: List[str]
    ) -> Dict[str, Any]:
        """生成基础警报（LLM失败时的降级方案）"""
        icon = self._get_alert_icon(risk_level)
        content = f"检测到{risk_level}级别风险，请注意以下因素：\n" + \
                 "\n".join(f"- {f}" for f in risk_factors[:5])

        return {
            "level": risk_level,
            "icon": icon,
            "content": content,
            "factors": risk_factors,
            "timestamp": datetime.now().isoformat(),
        }

    def _get_alert_icon(self, risk_level: str) -> str:
        """获取警报图标"""
        icons = {
            "CRITICAL": "⛔",
            "HIGH": "⚠️",
            "MEDIUM": "⚡",
            "LOW": "ℹ️",
        }
        return icons.get(risk_level, "ℹ️")

    def _generate_fallback_report(
        self,
        role: str,
        metar_data: Dict[str, Any],
        risk_level: str,
        risk_factors: List[str],
        raw_metar: str
    ) -> Dict[str, Any]:
        """
        生成降级报告（LLM失败时）

        使用角色专属的 Reporter 生成建议，确保上下文隔离。
        """
        role_cn = get_role_name_cn(role)

        # 获取角色专属的 reporter
        reporter = get_reporter(role)

        # 使用 reporter 构建报告（包含过滤风险因素、生成建议、额外字段）
        report_data = reporter.build_report(metar_data, risk_factors, risk_level)

        # 为飞行员角色附加 DH/MDA 信息到报告文本
        report_text = report_data["report_text"]
        dh_info = report_data.get("dh_mda_info")
        if dh_info:
            report_text += f"\n\n{dh_info}"

        alerts = []
        if risk_level in ["HIGH", "CRITICAL"]:
            alerts.append(self._generate_basic_alert(risk_level, report_data["filtered_risk_factors"]))

        # 构建完整报告
        return {
            "role": role,
            "role_cn": role_cn,
            "airport_icao": metar_data.get("icao_code", "UNKNOWN"),
            "observation_time": metar_data.get("observation_time", "N/A"),
            "risk_level": risk_level,
            "report_text": report_text,
            "role_summary": report_data["role_summary"],
            "disclaimer": SYSTEM_DISCLAIMER,
            "structured_analysis": None,
            "alerts": alerts,
            "generated_at": datetime.now().isoformat(),
            "model_used": "fallback",
            # 角色专属额外字段
            **{k: v for k, v in report_data.items()
               if k not in ("report_text", "role_summary", "filtered_risk_factors")},
        }


# 单例实例
_report_generator: Optional[ReportGenerator] = None


def get_report_generator() -> ReportGenerator:
    """获取报告生成器实例（单例模式）"""
    global _report_generator
    if _report_generator is None:
        _report_generator = ReportGenerator()
    return _report_generator


# 导出
__all__ = ["ReportGenerator", "get_report_generator", "SYSTEM_DISCLAIMER"]
