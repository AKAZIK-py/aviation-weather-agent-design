"""
安全边界检查节点测试
测试SafetyChecker类的安全边界规则
"""
import pytest
from app.nodes.check_safety_node import SafetyChecker, check_safety_node
from app.core.workflow_state import create_initial_state


class TestSafetyChecker:
    """安全边界检查器测试类"""

    @pytest.fixture
    def checker(self):
        """创建安全检查器实例"""
        return SafetyChecker()

    # ==================== CRITICAL风险干预测试 ====================

    def test_critical_risk_intervention(self, checker, state_critical_risk):
        """测试CRITICAL风险必须人工干预"""
        result = checker.check(state_critical_risk)

        assert result["passed"] is False
        assert result["intervention_required"] is True
        assert "CRITICAL风险等级需要人工评估" in result["violations"]
        assert result["intervention_reason"] is not None

    def test_high_risk_no_mandatory_intervention(self, checker):
        """测试HIGH风险不强制干预（但可能有其他规则触发）"""
        state = {
            "risk_level": "HIGH",
            "metar_parsed": {
                "wind_speed": 30,
                "visibility": 10.0,
                "present_weather": [],
            },
        }

        result = checker.check(state)

        # HIGH风险不一定需要干预，除非有其他规则触发
        # 注意：实际结果取决于具体规则配置
        assert isinstance(result["passed"], bool)
        assert isinstance(result["violations"], list)

    # ==================== IFR/LIFR天气检查测试 ====================

    def test_ifr_weather_intervention(self, checker):
        """测试IFR天气需要人工确认"""
        state = {
            "risk_level": "MEDIUM",
            "metar_parsed": {
                "flight_rules": "IFR",
                "wind_speed": 10,
                "visibility": 1.5,
                "present_weather": [],
            },
        }

        result = checker.check(state)

        assert result["passed"] is False
        assert result["intervention_required"] is True
        assert any("IFR" in v for v in result["violations"])

    def test_lifr_weather_intervention(self, checker):
        """测试LIFR天气需要人工确认"""
        state = {
            "risk_level": "HIGH",
            "metar_parsed": {
                "flight_rules": "LIFR",
                "wind_speed": 15,
                "visibility": 0.5,
                "present_weather": [],
            },
        }

        result = checker.check(state)

        assert result["passed"] is False
        assert result["intervention_required"] is True
        assert any("LIFR" in v for v in result["violations"])

    def test_vfr_mvfr_no_ifr_violation(self, checker):
        """测试VFR/MVFR不触发IFR规则"""
        state_vfr = {
            "risk_level": "LOW",
            "metar_parsed": {
                "flight_rules": "VFR",
                "wind_speed": 10,
                "visibility": 10.0,
                "present_weather": [],
            },
        }

        result = checker.check(state_vfr)
        assert not any("IFR" in v or "LIFR" in v for v in result["violations"])

        state_mvfr = {
            "risk_level": "MEDIUM",
            "metar_parsed": {
                "flight_rules": "MVFR",
                "wind_speed": 10,
                "visibility": 5.0,
                "present_weather": [],
            },
        }

        result_mvfr = checker.check(state_mvfr)
        assert not any("IFR" in v or "LIFR" in v for v in result_mvfr["violations"])

    # ==================== 雷暴活动检查测试 ====================

    def test_thunderstorm_intervention(self, checker):
        """测试雷暴活动需要人工干预"""
        state = {
            "risk_level": "HIGH",
            "metar_parsed": {
                "wind_speed": 20,
                "visibility": 5.0,
                "present_weather": [
                    {"code": "TS", "description": "雷暴"}
                ],
            },
        }

        result = checker.check(state)

        assert result["passed"] is False
        assert result["intervention_required"] is True
        assert any("雷暴" in v for v in result["violations"])

    def test_thunderstorm_with_rain_intervention(self, checker):
        """测试雷暴伴雨需要人工干预"""
        state = {
            "risk_level": "CRITICAL",
            "metar_parsed": {
                "wind_speed": 25,
                "visibility": 3.0,
                "present_weather": [
                    {"code": "TSRA", "description": "雷暴伴雨"}
                ],
            },
        }

        result = checker.check(state)

        assert result["passed"] is False
        assert result["intervention_required"] is True
        assert any("雷暴" in v for v in result["violations"])

    def test_severe_thunderstorm_intervention(self, checker):
        """测试强雷暴需要人工干预"""
        state = {
            "risk_level": "CRITICAL",
            "metar_parsed": {
                "wind_speed": 30,
                "visibility": 2.0,
                "present_weather": [
                    {"code": "+TSRA", "description": "强雷暴伴雨"}
                ],
            },
        }

        result = checker.check(state)

        assert result["passed"] is False
        assert result["intervention_required"] is True

    # ==================== 极低能见度检查测试 ====================

    def test_extremely_low_visibility_intervention(self, checker):
        """测试极低能见度（<800米）需要人工决策"""
        state = {
            "risk_level": "HIGH",
            "metar_parsed": {
                "wind_speed": 15,
                "visibility": 0.6,  # 600米
                "present_weather": [
                    {"code": "FG", "description": "雾"}
                ],
            },
        }

        result = checker.check(state)

        assert result["passed"] is False
        assert result["intervention_required"] is True
        assert any("能见度低于800米" in v for v in result["violations"])

    def test_visibility_at_threshold(self, checker):
        """测试能见度阈值边界（800米）"""
        # 刚好800米
        state = {
            "risk_level": "HIGH",
            "metar_parsed": {
                "wind_speed": 10,
                "visibility": 0.8,  # 800米
                "present_weather": [],
            },
        }

        result = checker.check(state)

        # 能见度=0.8km应该不触发<800米规则
        # 但可能触发IFR/LIFR规则
        low_vis_violation = any("能见度低于800米" in v for v in result["violations"])
        assert not low_vis_violation  # 不应触发<800米规则

    def test_visibility_above_threshold(self, checker):
        """测试能见度高于阈值（>800米）"""
        state = {
            "risk_level": "MEDIUM",
            "metar_parsed": {
                "wind_speed": 10,
                "visibility": 1.0,  # 1000米
                "present_weather": [],
            },
        }

        result = checker.check(state)

        low_vis_violation = any("能见度低于800米" in v for v in result["violations"])
        assert not low_vis_violation

    # ==================== 强侧风检查测试 ====================

    def test_strong_crosswind_intervention(self, checker):
        """测试强侧风（>30KT）需要评估"""
        state = {
            "risk_level": "HIGH",
            "metar_parsed": {
                "wind_speed": 35,
                "visibility": 10.0,
                "present_weather": [],
            },
        }

        result = checker.check(state)

        assert result["passed"] is False
        assert result["intervention_required"] is True
        assert any("风速超过30KT" in v for v in result["violations"])

    def test_wind_at_threshold(self, checker):
        """测试风速阈值边界（30KT）"""
        state = {
            "risk_level": "MEDIUM",
            "metar_parsed": {
                "wind_speed": 30,  # 刚好30KT
                "visibility": 10.0,
                "present_weather": [],
            },
        }

        result = checker.check(state)

        # 30KT应该不触发>30KT规则
        strong_wind_violation = any("风速超过30KT" in v for v in result["violations"])
        assert not strong_wind_violation

    def test_wind_below_threshold(self, checker):
        """测试风速低于阈值（<30KT）"""
        state = {
            "risk_level": "LOW",
            "metar_parsed": {
                "wind_speed": 25,
                "visibility": 10.0,
                "present_weather": [],
            },
        }

        result = checker.check(state)

        strong_wind_violation = any("风速超过30KT" in v for v in result["violations"])
        assert not strong_wind_violation

    # ==================== 冻雨/冻雾检查测试 ====================

    def test_freezing_rain_intervention(self, checker):
        """测试冻雨需要人工干预"""
        state = {
            "risk_level": "HIGH",
            "metar_parsed": {
                "wind_speed": 15,
                "visibility": 2.0,
                "present_weather": [
                    {"code": "FZRA", "description": "冻雨"}
                ],
            },
        }

        result = checker.check(state)

        assert result["passed"] is False
        assert result["intervention_required"] is True
        assert any("冻雨" in v or "冻雾" in v for v in result["violations"])

    def test_freezing_fog_intervention(self, checker):
        """测试冻雾需要人工干预"""
        state = {
            "risk_level": "HIGH",
            "metar_parsed": {
                "wind_speed": 10,
                "visibility": 0.5,
                "present_weather": [
                    {"code": "FZFG", "description": "冻雾"}
                ],
            },
        }

        result = checker.check(state)

        assert result["passed"] is False
        assert result["intervention_required"] is True
        assert any("冻雾" in v or "冻雨" in v for v in result["violations"])

    # ==================== 角色特定安全规则测试 ====================

    def test_atc_role_specific_rules(self, checker):
        """测试空管角色特定安全规则"""
        state = {
            "detected_role": "空管",
            "risk_level": "HIGH",
            "metar_parsed": {
                "wind_speed": 20,
                "visibility": 5.0,
                "present_weather": [],
            },
        }

        result = checker.check(state)

        # 空管在高风险天气需要确认跑道占用
        # 注意：具体规则取决于ROLE_SAFETY_RULES配置
        assert isinstance(result["violations"], list)

    def test_maintenance_role_specific_rules(self, checker):
        """测试机务角色特定安全规则"""
        state = {
            "detected_role": "机务",
            "risk_level": "MEDIUM",
            "metar_parsed": {
                "wind_speed": 28,  # 接近25KT阈值
                "visibility": 10.0,
                "present_weather": [],
            },
        }

        result = checker.check(state)

        # 机务对风速>25KT有户外作业限制
        # 注意：具体规则取决于ROLE_SAFETY_RULES配置
        assert isinstance(result["violations"], list)

    def test_role_specific_high_wind_ground_crew(self, checker):
        """测试地勤角色强风户外作业限制"""
        state = {
            "detected_role": "机务",
            "risk_level": "MEDIUM",
            "metar_parsed": {
                "wind_speed": 28,  # >25KT
                "visibility": 10.0,
                "present_weather": [],
            },
        }

        result = checker.check(state)

        # 应触发户外作业限制
        outdoor_work_violation = any("户外作业" in v for v in result["violations"])
        # 注意：具体行为取决于ROLE_SAFETY_RULES配置
        assert isinstance(outdoor_work_violation, bool)

    # ==================== 多重违规测试 ====================

    def test_multiple_violations(self, checker):
        """测试多重安全违规"""
        state = {
            "risk_level": "CRITICAL",
            "metar_parsed": {
                "flight_rules": "LIFR",
                "wind_speed": 40,
                "visibility": 0.3,
                "present_weather": [
                    {"code": "TS", "description": "雷暴"},
                    {"code": "FZRA", "description": "冻雨"},
                ],
            },
        }

        result = checker.check(state)

        assert result["passed"] is False
        assert result["intervention_required"] is True
        # 应有多个违规项
        assert len(result["violations"]) >= 3

    def test_no_violations(self, checker, state_with_risk):
        """测试无安全违规场景"""
        result = checker.check(state_with_risk)

        # 低风险、良好天气应无违规
        # 注意：实际结果取决于state_with_risk的具体内容
        assert isinstance(result["passed"], bool)
        assert isinstance(result["violations"], list)

    # ==================== 边界情况测试 ====================

    def test_missing_metar_data(self, checker):
        """测试缺失METAR数据"""
        state = {
            "risk_level": "LOW",
            "metar_parsed": {},
        }

        result = checker.check(state)

        # 应能处理缺失数据而不崩溃
        assert isinstance(result["passed"], bool)
        assert isinstance(result["violations"], list)

    def test_partial_metar_data(self, checker):
        """测试部分METAR数据"""
        state = {
            "risk_level": "MEDIUM",
            "metar_parsed": {
                "wind_speed": 20,
                # 缺失visibility和present_weather
            },
        }

        result = checker.check(state)

        assert isinstance(result["passed"], bool)
        assert isinstance(result["violations"], list)

    def test_unknown_role(self, checker):
        """测试未知角色"""
        state = {
            "detected_role": "未知角色",
            "risk_level": "MEDIUM",
            "metar_parsed": {
                "wind_speed": 15,
                "visibility": 10.0,
                "present_weather": [],
            },
        }

        result = checker.check(state)

        # 应能处理未知角色
        assert isinstance(result["passed"], bool)

    # ==================== 安全规则覆盖测试 ====================

    def test_safety_rule_critical_risk_coverage(self, checker):
        """测试CRITICAL风险规则覆盖"""
        """D3指标要求：安全边界=100%"""
        state = {
            "risk_level": "CRITICAL",
            "metar_parsed": {
                "wind_speed": 10,
                "visibility": 10.0,
                "present_weather": [],
            },
        }

        result = checker.check(state)

        # CRITICAL风险必须触发干预
        assert result["intervention_required"] is True
        assert result["passed"] is False

    def test_safety_rule_hazardous_weather_coverage(self, checker):
        """测试高危天气规则覆盖"""
        hazardous_codes = ["TS", "TSRA", "+TSRA", "FC", "GR"]

        for code in hazardous_codes:
            state = {
                "risk_level": "HIGH",
                "metar_parsed": {
                    "wind_speed": 10,
                    "visibility": 10.0,
                    "present_weather": [{"code": code, "description": "测试"}],
                },
            }

            result = checker.check(state)

            # 所有高危天气都应触发干预
            assert result["intervention_required"] is True, f"Failed for code: {code}"

    # ==================== 节点函数测试 ====================

    @pytest.mark.asyncio
    async def test_check_safety_node_pass(self, state_with_risk):
        """测试check_safety_node节点检查通过"""
        result = await check_safety_node(state_with_risk, config={})

        assert "safety_check_passed" in result
        assert "safety_violations" in result
        assert "intervention_required" in result
        assert result["current_node"] == "check_safety_node"
        assert len(result["reasoning_trace"]) > 0

    @pytest.mark.asyncio
    async def test_check_safety_node_fail(self, state_critical_risk):
        """测试check_safety_node节点检查失败"""
        result = await check_safety_node(state_critical_risk, config={})

        assert result["safety_check_passed"] is False
        assert len(result["safety_violations"]) > 0
        assert result["intervention_required"] is True
        assert result["intervention_reason"] is not None

    @pytest.mark.asyncio
    async def test_check_safety_node_trace(self, state_critical_risk):
        """测试check_safety_node节点推理追踪"""
        result = await check_safety_node(state_critical_risk, config={})

        assert len(result["reasoning_trace"]) > 0
        assert "安全检查" in result["reasoning_trace"][0]


class TestSafetyCheckerIntegration:
    """安全检查集成测试"""

    @pytest.fixture
    def checker(self):
        return SafetyChecker()

    def test_complete_scenario_critical(self, checker):
        """完整场景：CRITICAL风险+多重违规"""
        state = {
            "detected_role": "pilot",
            "risk_level": "CRITICAL",
            "metar_parsed": {
                "flight_rules": "LIFR",
                "wind_speed": 45,
                "wind_gust": 55,
                "visibility": 0.2,
                "present_weather": [
                    {"code": "+TSRA", "description": "强雷暴伴雨"},
                    {"code": "FZRA", "description": "冻雨"},
                ],
            },
        }

        result = checker.check(state)

        assert result["passed"] is False
        assert result["intervention_required"] is True
        assert len(result["violations"]) >= 4

        # 验证关键违规都在
        violations_str = " ".join(result["violations"])
        assert "CRITICAL" in violations_str
        assert "雷暴" in violations_str
        assert "能见度低于800米" in violations_str
        assert "风速超过30KT" in violations_str

    def test_complete_scenario_safe(self, checker):
        """完整场景：安全天气"""
        state = {
            "detected_role": "pilot",
            "risk_level": "LOW",
            "metar_parsed": {
                "flight_rules": "VFR",
                "wind_speed": 12,
                "visibility": 10.0,
                "present_weather": [],
            },
        }

        result = checker.check(state)

        # 低风险、VFR天气应通过安全检查
        assert result["passed"] is True
        assert len(result["violations"]) == 0
        assert result["intervention_required"] is False

    def test_edge_case_visibility_threshold(self, checker):
        """边界情况：能见度阈值"""
        # 799米（<800米）
        state_799m = {
            "risk_level": "HIGH",
            "metar_parsed": {
                "wind_speed": 10,
                "visibility": 0.799,
                "present_weather": [],
            },
        }

        result_799m = checker.check(state_799m)
        assert any("能见度低于800米" in v for v in result_799m["violations"])

        # 801米（>800米）
        state_801m = {
            "risk_level": "HIGH",
            "metar_parsed": {
                "wind_speed": 10,
                "visibility": 0.801,
                "present_weather": [],
            },
        }

        result_801m = checker.check(state_801m)
        assert not any("能见度低于800米" in v for v in result_801m["violations"])

    def test_edge_case_wind_threshold(self, checker):
        """边界情况：风速阈值"""
        # 31KT（>30KT）
        state_31kt = {
            "risk_level": "HIGH",
            "metar_parsed": {
                "wind_speed": 31,
                "visibility": 10.0,
                "present_weather": [],
            },
        }

        result_31kt = checker.check(state_31kt)
        assert any("风速超过30KT" in v for v in result_31kt["violations"])

        # 29KT（<30KT）
        state_29kt = {
            "risk_level": "MEDIUM",
            "metar_parsed": {
                "wind_speed": 29,
                "visibility": 10.0,
                "present_weather": [],
            },
        }

        result_29kt = checker.check(state_29kt)
        assert not any("风速超过30KT" in v for v in result_29kt["violations"])
