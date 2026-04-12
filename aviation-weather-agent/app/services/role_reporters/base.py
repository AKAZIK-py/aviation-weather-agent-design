"""
BaseReporter - 角色报告生成器基类

定义了报告生成的模板方法和风险因素过滤接口。
各角色 Reporter 继承此类，实现各自的过滤逻辑和建议生成。
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.utils.visibility import format_visibility_range


class BaseReporter(ABC):
    """角色报告生成器抽象基类"""

    # 子类需定义：该角色允许的风险因素关键词集合
    ALLOWED_RISK_KEYWORDS: set = set()

    # 子类需定义：该角色需过滤掉的风险因素关键词集合
    FILTERED_RISK_KEYWORDS: set = set()

    # 角色中文名
    ROLE_CN: str = ""

    # 角色标识
    ROLE: str = ""

    def filter_risk_factors(
        self, risk_factors: List[str], role: str = None
    ) -> List[str]:
        """
        按角色过滤风险因素，只保留该角色关注的内容。

        过滤逻辑：
        1. 排除 FILTERED_RISK_KEYWORDS 中包含的关键词
        2. 仅保留 ALLOWED_RISK_KEYWORDS 中包含的关键词（如果集合非空）

        Args:
            risk_factors: 原始风险因素列表
            role: 角色标识（可选，用于日志）

        Returns:
            过滤后的风险因素列表
        """
        filtered = []
        for factor in risk_factors:
            factor_lower = factor.lower()

            # 检查是否包含需要过滤的关键词
            should_filter = False
            for keyword in self.FILTERED_RISK_KEYWORDS:
                if keyword.lower() in factor_lower:
                    should_filter = True
                    break

            if should_filter:
                continue

            # 如果定义了白名单，检查是否在允许范围内
            if self.ALLOWED_RISK_KEYWORDS:
                is_allowed = False
                for keyword in self.ALLOWED_RISK_KEYWORDS:
                    if keyword.lower() in factor_lower:
                        is_allowed = True
                        break
                if not is_allowed:
                    continue

            filtered.append(factor)

        return filtered

    def build_headlines(
        self, risk_factors: List[str], risk_level: str
    ) -> List[str]:
        """
        构建角色摘要的 headlines（精简短句）。

        Args:
            risk_factors: 已过滤的风险因素列表
            risk_level: 风险等级

        Returns:
            精简的 headline 列表（最多 3 条）
        """
        headlines = []
        for f in risk_factors[:3]:
            short = f.split("：")[0].split(":")[0].strip()
            if len(short) > 20:
                short = short[:20]
            if short:
                headlines.append(short)
        if not headlines:
            headlines = ["天气条件正常"]
        return headlines

    def build_role_summary(
        self, risk_level: str, risk_factors: List[str]
    ) -> Dict[str, str]:
        """
        根据 risk_level 和 risk_factors 动态生成角色摘要。

        Returns:
            {headlines: [str], decision: str, confidence: str}
        """
        headlines = self.build_headlines(risk_factors, risk_level)

        if risk_level in ("CRITICAL", "HIGH"):
            decision = "NO-GO"
        elif risk_level == "MEDIUM":
            decision = "CAUTION"
        else:
            decision = "GO"

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

    @abstractmethod
    def generate_advice(
        self,
        metar_data: Dict[str, Any],
        risk_factors: List[str],
        risk_level: str,
    ) -> str:
        """
        基于风险因素生成角色专属建议。

        Args:
            metar_data: 解析后的 METAR 数据
            risk_factors: 已过滤的风险因素列表
            risk_level: 风险等级

        Returns:
            格式化的建议文本
        """
        ...

    def get_extra_fields(
        self,
        metar_data: Dict[str, Any],
        risk_factors: List[str],
        risk_level: str,
    ) -> Dict[str, Any]:
        """
        获取角色特有的额外字段（子类可覆盖）。

        Returns:
            额外字段字典
        """
        return {}

    def build_report(
        self,
        metar_data: Dict[str, Any],
        risk_factors: List[str],
        risk_level: str,
    ) -> Dict[str, Any]:
        """
        模板方法：构建完整的角色报告。

        流程：filter → advice → summary → extra_fields

        Args:
            metar_data: 解析后的 METAR 数据
            risk_factors: 原始风险因素列表
            risk_level: 风险等级

        Returns:
            包含 report_text, role_summary, extra_fields 等的字典
        """
        # 1. 过滤风险因素
        filtered_factors = self.filter_risk_factors(risk_factors, self.ROLE)

        # 2. 生成角色专属建议
        advice = self.generate_advice(metar_data, filtered_factors, risk_level)

        # 3. 构建角色摘要
        role_summary = self.build_role_summary(risk_level, filtered_factors)

        # 4. 获取额外字段
        extra_fields = self.get_extra_fields(metar_data, filtered_factors, risk_level)

        # 5. 构建报告文本
        airport_icao = metar_data.get("icao_code", "UNKNOWN")
        observation_time = metar_data.get("observation_time", "N/A")

        vis_raw = metar_data.get("visibility")
        vis_display = format_visibility_range(vis_raw) if vis_raw is not None else "N/A"

        report_text = f"""【{self.ROLE_CN}天气分析报告】

机场：{airport_icao}
观测时间：{observation_time}
风险等级：{risk_level}

【天气概况】
- 风向风速：{metar_data.get('wind_direction', 'N/A')}°/{metar_data.get('wind_speed', 'N/A')} KT
- 能见度：{vis_display}
- 温度/露点：{metar_data.get('temperature', 'N/A')}/{metar_data.get('dewpoint', 'N/A')} °C
- 气压：{metar_data.get('altimeter', 'N/A')} hPa

【风险因素】
{chr(10).join(f'- {f}' for f in filtered_factors[:5]) if filtered_factors else '- 当前无显著风险因素'}

【建议】
{advice}"""

        return {
            "report_text": report_text,
            "role_summary": role_summary,
            "filtered_risk_factors": filtered_factors,
            **extra_fields,
        }
