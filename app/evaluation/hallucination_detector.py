"""
M-03 三层幻觉检测模块

Layer 1 (数值幻觉): 报告中数字是否与 METAR 一致
Layer 2 (现象幻觉): 报告提及的天气现象是否存在于 METAR
Layer 3 (因果幻觉): 报告中的因果推断是否合理
"""

import re
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field


@dataclass
class HallucinationItem:
    """单个幻觉项"""

    layer: int
    layer_name: str
    description: str
    severity: str  # "low", "medium", "high"
    reported_value: Optional[str] = None
    actual_value: Optional[str] = None
    statement: str = ""


@dataclass
class HallucinationReport:
    """幻觉检测报告"""

    total_statements: int = 0
    layer1_numerical: List[HallucinationItem] = field(default_factory=list)
    layer2_phenomenon: List[HallucinationItem] = field(default_factory=list)
    layer3_causal: List[HallucinationItem] = field(default_factory=list)

    @property
    def l1_count(self) -> int:
        return len(self.layer1_numerical)

    @property
    def l2_count(self) -> int:
        return len(self.layer2_phenomenon)

    @property
    def l3_count(self) -> int:
        return len(self.layer3_causal)

    @property
    def total_hallucinations(self) -> int:
        return self.l1_count + self.l2_count + self.l3_count

    @property
    def weighted_hallucination_rate(self) -> float:
        """综合幻觉率 = (L1*0.2 + L2*0.3 + L3*0.5) / 总陈述数"""
        if self.total_statements == 0:
            return 0.0
        weighted = self.l1_count * 0.2 + self.l2_count * 0.3 + self.l3_count * 0.5
        return weighted / self.total_statements

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_statements": self.total_statements,
            "layer1_count": self.l1_count,
            "layer2_count": self.l2_count,
            "layer3_count": self.l3_count,
            "total_hallucinations": self.total_hallucinations,
            "weighted_hallucination_rate": self.weighted_hallucination_rate,
            "layer1_items": [
                {
                    "description": i.description,
                    "severity": i.severity,
                    "reported": i.reported_value,
                    "actual": i.actual_value,
                    "statement": i.statement,
                }
                for i in self.layer1_numerical
            ],
            "layer2_items": [
                {
                    "description": i.description,
                    "severity": i.severity,
                    "reported": i.reported_value,
                    "actual": i.actual_value,
                    "statement": i.statement,
                }
                for i in self.layer2_phenomenon
            ],
            "layer3_items": [
                {
                    "description": i.description,
                    "severity": i.severity,
                    "reported": i.reported_value,
                    "actual": i.actual_value,
                    "statement": i.statement,
                }
                for i in self.layer3_causal
            ],
        }


class HallucinationDetector:
    """三层幻觉检测器"""

    # 数值提取正则：带单位的数值
    VALUE_WITH_UNIT_PATTERN = re.compile(
        r"(\d+(?:\.\d+)?)\s*(kt|节|km|公里|m|米|ft|英尺|°C|度|kt|knots|节|SM|海里)",
        re.IGNORECASE,
    )

    # 纯数字模式：用于匹配报告中上下文明确的数值
    CONTEXTUAL_NUMBER_PATTERN = re.compile(
        r"(?:能见度|visibility|风速|wind|阵风|gust|温度|temperature|云底|ceiling|高度|height)"
        r"[\s:：]*(\d+(?:\.\d+)?)",
        re.IGNORECASE,
    )

    # 天气现象关键词
    WEATHER_KEYWORDS_CN = {
        "雷暴": ["TS", "TSRA", "+TSRA", "-TSRA", "TSGR", "TSGS"],
        "暴雷": ["TS", "TSRA"],
        "雾": ["FG", "FZFG", "BR"],
        "大雾": ["FG", "FZFG"],
        "冻雾": ["FZFG"],
        "雪": ["SN", "+SN", "-SN", "SHSN", "SG"],
        "大雪": ["+SN"],
        "小雪": ["-SN"],
        "阵雪": ["SHSN"],
        "雨": ["RA", "+RA", "-RA", "SHRA", "DZ"],
        "大雨": ["+RA"],
        "小雨": ["-RA"],
        "阵雨": ["SHRA"],
        "冻雨": ["FZRA", "FZDZ"],
        "冰雹": ["GR", "GS"],
        "沙尘": ["DU", "SA", "SS", "DS"],
        "沙暴": ["SS"],
        "尘暴": ["DS"],
        "霾": ["HZ"],
        "轻雾": ["BR"],
        "毛毛雨": ["DZ"],
        "CB": ["CB"],
        "积雨云": ["CB"],
        "TCU": ["TCU"],
        "浓积云": ["TCU"],
        "火山灰": ["VA"],
        "飑": ["SQ"],
        "漏斗云": ["FC"],
    }

    # 因果模式
    CAUSAL_PATTERNS = [
        re.compile(r"因为.{1,50}所以", re.IGNORECASE),
        re.compile(r"由于.{1,50}(?:导致|造成|引起)", re.IGNORECASE),
        re.compile(r"建议.{1,50}(?:避免|防止|注意)", re.IGNORECASE),
        re.compile(r"因此.{1,50}(?:不适|建议|需要)", re.IGNORECASE),
        re.compile(r"可能会导致", re.IGNORECASE),
        re.compile(r"容易产生", re.IGNORECASE),
        re.compile(r"容易引发", re.IGNORECASE),
        re.compile(r"存在.{1,20}风险", re.IGNORECASE),
        re.compile(r"不适合.{1,20}(?:飞行|起降|起飞|着陆)", re.IGNORECASE),
        re.compile(r"不适(?:飞|航)", re.IGNORECASE),
        re.compile(r"颠簸", re.IGNORECASE),
        re.compile(r"积冰", re.IGNORECASE),
        re.compile(r"风切变", re.IGNORECASE),
    ]

    # 颠簸推断规则：风速阈值
    TURBULENCE_WIND_THRESHOLD = 15  # kt

    # 不适航推断规则：能见度阈值
    UNFLYABLE_VIS_THRESHOLD = 3.0  # km

    def __init__(self, tolerance: float = 0.15):
        """
        Args:
            tolerance: 数值比较容差比例 (默认 15%)
        """
        self.tolerance = tolerance

    def detect_all_layers(
        self,
        report: str,
        metar_data: Dict[str, Any],
        risk_assessment: Optional[Dict[str, Any]] = None,
    ) -> HallucinationReport:
        """
        执行三层幻觉检测

        Args:
            report: LLM 生成的分析报告文本
            metar_data: METAR 解析后的结构化数据
            risk_assessment: 风险评估结果 (可选)

        Returns:
            HallucinationReport
        """
        result = HallucinationReport()

        if not report:
            return result

        # 统计陈述数（按句号/换行分割）
        statements = self._split_statements(report)
        result.total_statements = max(len(statements), 1)

        # Layer 1: 数值幻觉检测
        result.layer1_numerical = self._detect_numerical_hallucination(
            report, metar_data, statements
        )

        # Layer 2: 现象幻觉检测
        result.layer2_phenomenon = self._detect_phenomenon_hallucination(
            report, metar_data, statements
        )

        # Layer 3: 因果幻觉检测
        result.layer3_causal = self._detect_causal_hallucination(
            report, metar_data, risk_assessment, statements
        )

        return result

    def _split_statements(self, text: str) -> List[str]:
        """将文本拆分为陈述句"""
        # 按句号、分号、换行分割
        parts = re.split(r"[。\n；;]", text)
        return [p.strip() for p in parts if p.strip() and len(p.strip()) > 3]

    def _detect_numerical_hallucination(
        self,
        report: str,
        metar_data: Dict[str, Any],
        statements: List[str],
    ) -> List[HallucinationItem]:
        """Layer 1: 数值幻觉检测"""
        items = []

        # 提取 METAR 中的关键数值
        metar_values = {
            "visibility": metar_data.get("visibility"),
            "wind_speed": metar_data.get("wind_speed"),
            "wind_gust": metar_data.get("wind_gust"),
            "temperature": metar_data.get("temperature"),
            "dewpoint": metar_data.get("dewpoint"),
            "vertical_visibility": metar_data.get("vertical_visibility"),
        }

        # 提取报告中所有带单位的数值
        for match in self.VALUE_WITH_UNIT_PATTERN.finditer(report):
            value_str = match.group(1)
            unit = match.group(2).lower()
            reported_val = float(value_str)

            # 根据单位判断数值类型并对比
            if unit in ("kt", "节", "knots"):
                self._check_wind_value(
                    items, reported_val, metar_data, match.group(0), report
                )
            elif unit in ("km", "公里"):
                self._check_vis_value(
                    items, reported_val, metar_data, match.group(0), report
                )
            elif unit in ("m", "米"):
                self._check_vis_meters_value(
                    items, reported_val, metar_data, match.group(0), report
                )
            elif unit in ("ft", "英尺"):
                self._check_height_value(
                    items, reported_val, metar_data, match.group(0), report
                )
            elif unit in ("°c", "度"):
                self._check_temp_value(
                    items, reported_val, metar_data, match.group(0), report
                )

        # 提取上下文明确的数值
        for match in self.CONTEXTUAL_NUMBER_PATTERN.finditer(report):
            full_match = match.group(0)
            value = float(match.group(1))
            context = full_match.lower()

            if "能见度" in context or "visibility" in context:
                vis = metar_data.get("visibility")
                if vis is not None and not self._is_within_tolerance(value, vis):
                    # 检查是否是米制
                    if value > 100:
                        vis_m = vis * 1000
                        if not self._is_within_tolerance(value, vis_m):
                            items.append(
                                HallucinationItem(
                                    layer=1,
                                    layer_name="数值幻觉",
                                    description="能见度数值不一致",
                                    severity="high",
                                    reported_value=f"{value}",
                                    actual_value=f"{vis}km ({vis_m:.0f}m)",
                                    statement=full_match,
                                )
                            )
                    else:
                        items.append(
                            HallucinationItem(
                                layer=1,
                                layer_name="数值幻觉",
                                description="能见度数值不一致",
                                severity="high",
                                reported_value=f"{value}km",
                                actual_value=f"{vis}km",
                                statement=full_match,
                            )
                        )

            elif "风速" in context or "wind" in context:
                ws = metar_data.get("wind_speed")
                if ws is not None and not self._is_within_tolerance(value, ws):
                    items.append(
                        HallucinationItem(
                            layer=1,
                            layer_name="数值幻觉",
                            description="风速数值不一致",
                            severity="high",
                            reported_value=f"{value}kt",
                            actual_value=f"{ws}kt",
                            statement=full_match,
                        )
                    )

            elif "温度" in context or "temperature" in context:
                temp = metar_data.get("temperature")
                if temp is not None and abs(value - temp) > 2:
                    items.append(
                        HallucinationItem(
                            layer=1,
                            layer_name="数值幻觉",
                            description="温度数值不一致",
                            severity="medium",
                            reported_value=f"{value}°C",
                            actual_value=f"{temp}°C",
                            statement=full_match,
                        )
                    )

        return items

    def _check_wind_value(
        self,
        items: List[HallucinationItem],
        reported: float,
        metar_data: Dict[str, Any],
        match_text: str,
        report: str,
    ):
        """检查风速数值"""
        ws = metar_data.get("wind_speed")
        wg = metar_data.get("wind_gust")

        # 检查是否是阵风描述
        context_start = max(0, report.find(match_text) - 20)
        context = report[context_start : report.find(match_text) + len(match_text) + 10]

        is_gust = any(k in context for k in ["阵风", "gust", "Gust"])

        if is_gust and wg is not None:
            if not self._is_within_tolerance(reported, wg):
                items.append(
                    HallucinationItem(
                        layer=1,
                        layer_name="数值幻觉",
                        description="阵风数值不一致",
                        severity="high",
                        reported_value=f"{reported}kt",
                        actual_value=f"{wg}kt",
                        statement=match_text,
                    )
                )
        elif ws is not None and not self._is_within_tolerance(reported, ws):
            # 排除阵风值干扰
            if wg is None or abs(reported - ws) < abs(reported - wg):
                items.append(
                    HallucinationItem(
                        layer=1,
                        layer_name="数值幻觉",
                        description="风速数值不一致",
                        severity="high",
                        reported_value=f"{reported}kt",
                        actual_value=f"{ws}kt",
                        statement=match_text,
                    )
                )

    def _check_vis_value(
        self,
        items: List[HallucinationItem],
        reported: float,
        metar_data: Dict[str, Any],
        match_text: str,
        report: str,
    ):
        """检查能见度(km)数值"""
        vis = metar_data.get("visibility")
        if vis is not None and not self._is_within_tolerance(reported, vis):
            items.append(
                HallucinationItem(
                    layer=1,
                    layer_name="数值幻觉",
                    description="能见度(km)数值不一致",
                    severity="high",
                    reported_value=f"{reported}km",
                    actual_value=f"{vis}km",
                    statement=match_text,
                )
            )

    def _check_vis_meters_value(
        self,
        items: List[HallucinationItem],
        reported: float,
        metar_data: Dict[str, Any],
        match_text: str,
        report: str,
    ):
        """检查能见度(m)数值"""
        vis = metar_data.get("visibility")
        if vis is not None:
            vis_m = vis * 1000
            if not self._is_within_tolerance(reported, vis_m):
                items.append(
                    HallucinationItem(
                        layer=1,
                        layer_name="数值幻觉",
                        description="能见度(m)数值不一致",
                        severity="high",
                        reported_value=f"{reported:.0f}m",
                        actual_value=f"{vis_m:.0f}m ({vis}km)",
                        statement=match_text,
                    )
                )

    def _check_height_value(
        self,
        items: List[HallucinationItem],
        reported: float,
        metar_data: Dict[str, Any],
        match_text: str,
        report: str,
    ):
        """检查高度(ft)数值"""
        layers = metar_data.get("cloud_layers", [])
        vv = metar_data.get("vertical_visibility")

        # 检查是否匹配任何云层高度
        all_heights = [l.get("height_feet") for l in layers if l.get("height_feet")]
        if vv is not None:
            all_heights.append(vv)

        if all_heights:
            closest = min(all_heights, key=lambda h: abs(h - reported))
            if not self._is_within_tolerance(reported, closest):
                items.append(
                    HallucinationItem(
                        layer=1,
                        layer_name="数值幻觉",
                        description="高度数值不一致",
                        severity="medium",
                        reported_value=f"{reported:.0f}ft",
                        actual_value=f"最接近的值: {closest:.0f}ft",
                        statement=match_text,
                    )
                )

    def _check_temp_value(
        self,
        items: List[HallucinationItem],
        reported: float,
        metar_data: Dict[str, Any],
        match_text: str,
        report: str,
    ):
        """检查温度数值"""
        temp = metar_data.get("temperature")
        if temp is not None and abs(reported - temp) > 2:
            items.append(
                HallucinationItem(
                    layer=1,
                    layer_name="数值幻觉",
                    description="温度数值不一致",
                    severity="medium",
                    reported_value=f"{reported}°C",
                    actual_value=f"{temp}°C",
                    statement=match_text,
                )
            )

    def _detect_phenomenon_hallucination(
        self,
        report: str,
        metar_data: Dict[str, Any],
        statements: List[str],
    ) -> List[HallucinationItem]:
        """Layer 2: 现象幻觉检测"""
        items = []

        # 获取 METAR 中实际存在的天气代码
        metar_weather_codes = set()
        for w in metar_data.get("present_weather", []):
            code = w.get("code", "")
            metar_weather_codes.add(code)

        # 获取 METAR 原文用于交叉验证
        metar_raw = metar_data.get("raw_text", "").upper()

        # 检查报告中提到的天气关键词
        for keyword, codes in self.WEATHER_KEYWORDS_CN.items():
            if keyword in report:
                # 检查 METAR 中是否有对应的天气代码
                has_match = any(c in metar_weather_codes for c in codes)
                # 额外检查 METAR 原文
                has_in_raw = any(c in metar_raw for c in codes)

                if not has_match and not has_in_raw:
                    # 找到包含该关键词的陈述
                    stmt = next((s for s in statements if keyword in s), keyword)
                    items.append(
                        HallucinationItem(
                            layer=2,
                            layer_name="现象幻觉",
                            description=f"报告提及'{keyword}'但METAR中不存在对应天气现象",
                            severity="high",
                            reported_value=keyword,
                            actual_value=f"METAR天气: {list(metar_weather_codes) or '无'}",
                            statement=stmt,
                        )
                    )

        # 检查 CB/TCU 云类型
        report_upper = report.upper()
        cloud_types_in_metar = {
            l.get("tower_type")
            for l in metar_data.get("cloud_layers", [])
            if l.get("tower_type")
        }

        for special_cloud in ["CB", "TCU"]:
            if (
                special_cloud in report_upper
                and special_cloud not in cloud_types_in_metar
            ):
                if special_cloud not in metar_raw:
                    items.append(
                        HallucinationItem(
                            layer=2,
                            layer_name="现象幻觉",
                            description=f"报告提及{special_cloud}但METAR中不存在",
                            severity="high",
                            reported_value=special_cloud,
                            actual_value=f"云层: {[l.get('type') for l in metar_data.get('cloud_layers', [])]}",
                            statement=f"报告中提到了{special_cloud}云",
                        )
                    )

        return items

    def _detect_causal_hallucination(
        self,
        report: str,
        metar_data: Dict[str, Any],
        risk_assessment: Optional[Dict[str, Any]],
        statements: List[str],
    ) -> List[HallucinationItem]:
        """Layer 3: 因果幻觉检测"""
        items = []

        wind_speed = metar_data.get("wind_speed") or 0
        wind_gust = metar_data.get("wind_gust")
        visibility = metar_data.get("visibility")
        temperature = metar_data.get("temperature")

        max_wind = max(wind_speed, wind_gust or 0)

        # 规则1: 风速 < 15kt 不应推断颠簸
        if max_wind < self.TURBULENCE_WIND_THRESHOLD:
            turb_keywords = ["颠簸", "turbulence", "湍流", "不稳"]
            for kw in turb_keywords:
                if kw in report:
                    stmt = next((s for s in statements if kw in s), kw)
                    items.append(
                        HallucinationItem(
                            layer=3,
                            layer_name="因果幻觉",
                            description=f"风速{max_wind}kt(<{self.TURBULENCE_WIND_THRESHOLD}kt)不应推断颠簸",
                            severity="high",
                            reported_value=f"报告提及'{kw}'",
                            actual_value=f"风速{max_wind}kt",
                            statement=stmt,
                        )
                    )
                    break  # 只报告一次

        # 规则2: 能见度 >= 3km 不应说不适航
        if visibility is not None and visibility >= self.UNFLYABLE_VIS_THRESHOLD:
            unflyable_patterns = [
                "不适飞",
                "不适航",
                "不适合飞行",
                "不适合起降",
                "不能飞",
                "无法飞行",
                "禁止飞行",
                "grounded",
            ]
            for pattern in unflyable_patterns:
                if pattern in report:
                    stmt = next((s for s in statements if pattern in s), pattern)
                    items.append(
                        HallucinationItem(
                            layer=3,
                            layer_name="因果幻觉",
                            description=f"能见度{visibility}km(>={self.UNFLYABLE_VIS_THRESHOLD}km)不应说不适航",
                            severity="high",
                            reported_value=f"报告提及'{pattern}'",
                            actual_value=f"能见度{visibility}km",
                            statement=stmt,
                        )
                    )
                    break

        # 规则3: 无积冰条件不应推断积冰
        if temperature is not None and temperature > 0:
            icing_keywords = ["积冰", "结冰", "icing", "冻雨", "覆冰"]
            for kw in icing_keywords:
                if kw in report:
                    # 检查是否有 FZFG/FZRA/FZDZ
                    weather_codes = {
                        w.get("code", "") for w in metar_data.get("present_weather", [])
                    }
                    has_freezing = any(c.startswith("FZ") for c in weather_codes)
                    if not has_freezing:
                        stmt = next((s for s in statements if kw in s), kw)
                        items.append(
                            HallucinationItem(
                                layer=3,
                                layer_name="因果幻觉",
                                description=f"温度{temperature}°C(>0°C)且无冻天气不应推断积冰",
                                severity="medium",
                                reported_value=f"报告提及'{kw}'",
                                actual_value=f"温度{temperature}°C, 天气: {weather_codes}",
                                statement=stmt,
                            )
                        )
                    break

        # 规则4: CAVOK 不应说能见度差
        if metar_data.get("is_cavok"):
            poor_vis_keywords = [
                "能见度差",
                "低能见度",
                "能见度低",
                "能见度不良",
                "poor visibility",
            ]
            for kw in poor_vis_keywords:
                if kw in report:
                    stmt = next((s for s in statements if kw in s), kw)
                    items.append(
                        HallucinationItem(
                            layer=3,
                            layer_name="因果幻觉",
                            description="CAVOK条件不应说能见度差",
                            severity="high",
                            reported_value=f"报告提及'{kw}'",
                            actual_value="CAVOK (能见度>10km)",
                            statement=stmt,
                        )
                    )
                    break

        # 规则5: 无雷暴不应说雷暴相关风险
        weather_codes = {
            w.get("code", "") for w in metar_data.get("present_weather", [])
        }
        has_ts = any("TS" in c for c in weather_codes)
        if not has_ts:
            ts_keywords = ["雷暴", "thunderstorm", "雷电", "闪电"]
            for kw in ts_keywords:
                if kw in report:
                    metar_raw = metar_data.get("raw_text", "").upper()
                    if "TS" not in metar_raw:
                        stmt = next((s for s in statements if kw in s), kw)
                        items.append(
                            HallucinationItem(
                                layer=3,
                                layer_name="因果幻觉",
                                description="METAR中无雷暴不应提及雷暴风险",
                                severity="high",
                                reported_value=f"报告提及'{kw}'",
                                actual_value=f"天气: {weather_codes or '无'}",
                                statement=stmt,
                            )
                        )
                    break

        return items

    def _is_within_tolerance(self, val1: float, val2: float) -> bool:
        """检查两值是否在容差范围内"""
        if val1 == val2:
            return True
        max_val = max(abs(val1), abs(val2))
        if max_val == 0:
            return True
        return abs(val1 - val2) <= max_val * self.tolerance


def detect_hallucinations(
    report: str,
    metar_data: Dict[str, Any],
    risk_assessment: Optional[Dict[str, Any]] = None,
    tolerance: float = 0.15,
) -> HallucinationReport:
    """便捷函数：执行三层幻觉检测"""
    detector = HallucinationDetector(tolerance=tolerance)
    return detector.detect_all_layers(report, metar_data, risk_assessment)
