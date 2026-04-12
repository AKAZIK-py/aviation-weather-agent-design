"""
M-06 边界 case 专项测试

至少 30 个边界 case，覆盖:
1. VV 优先级 (VV + 普通能见度共存) - 5 cases
2. 能见度边界值 (恰好 1600m/4800m/8000m) - 5 cases
3. 仅 FEW/SCT (无 ceiling) - 3 cases
4. 负温度解析 (M05/-05) - 3 cases
5. 风切变 + 低能见度组合 - 3 cases
6. BECMG/TEMPO 趋势 - 3 cases
7. 多层云叠加 - 2 cases
8. 自动站 AO1/AO2 - 2 cases
9. 截断/异常 METAR - 4 cases
10. CAVOK - 2 cases
"""
import pytest
from app.nodes.parse_metar_node import METARParser


@pytest.fixture
def parser():
    return METARParser()


class TestVVPriority:
    """1. VV 优先级 (VV + 普通能见度共存) - 5 cases"""

    def test_vv_with_low_visibility_lifr(self, parser):
        """VV001 + 能见度50m → LIFR"""
        metar = "ZBAA 110800Z 00000KT 0050 FG VV001 02/01 Q1023"
        data, success, errors = parser.parse(metar)
        assert success
        assert data["vertical_visibility"] == 100
        assert data["flight_rules"] == "LIFR"
        assert data["visibility"] == 0.05

    def test_vv_with_medium_visibility(self, parser):
        """VV003 + 能见度800m → IFR (VV优先，取ceiling=VV)"""
        metar = "ZSPD 110900Z 24005KT 0800 FG VV003 06/05 Q1020"
        data, success, errors = parser.parse(metar)
        assert success
        assert data["vertical_visibility"] == 300
        # VV=300ft < 500ft → ceiling 类为 LIFR
        # vis=0.8km < 1SM → LIFR
        # 取较差 → LIFR
        assert data["flight_rules"] == "LIFR"

    def test_vv_high_with_good_visibility(self, parser):
        """VV010 + 能见度5km → MVFR/IFR取决于VV ceiling"""
        metar = "ZUUU 111000Z 06008KT 5000 BR VV010 12/11 Q1015"
        data, success, errors = parser.parse(metar)
        assert success
        assert data["vertical_visibility"] == 1000
        # VV=1000ft → ceiling: MVFR
        # vis=5km ≈ 3.1SM → MVFR
        assert data["flight_rules"] == "MVFR"

    def test_vv_000_extreme(self, parser):
        """VV000 (垂直能见度0) → LIFR"""
        metar = "ZBAA 111100Z 00000KT 0000 FG VV000 01/01 Q1025"
        data, success, errors = parser.parse(metar)
        assert success
        # VV=0ft < 500ft → LIFR ceiling
        # vis=0km < 1SM → LIFR vis
        assert data["flight_rules"] == "LIFR"

    def test_vv_with_rvr(self, parser):
        """VV + RVR 共存"""
        metar = "ZSSS 111200Z 00000KT 0100 R18/0200V0400N FG VV001 03/02 Q1022"
        data, success, errors = parser.parse(metar)
        assert success
        assert data["vertical_visibility"] == 100
        assert data["visibility"] == 0.1
        assert len(data["rvr"]) > 0
        assert data["flight_rules"] == "LIFR"


class TestVisibilityBoundary:
    """2. 能见度边界值 (恰好 1600m/4800m/8000m) - 5 cases"""

    def test_visibility_exactly_1600m(self, parser):
        """能见度恰好1600m → IFR/LIFR边界"""
        metar = "ZBAA 110800Z 18008KT 1600 HZ SCT040 25/18 Q1012"
        data, success, errors = parser.parse(metar)
        assert success
        assert data["visibility"] == 1.6
        # 1600m = 0.994 SM < 1 SM → LIFR (严格ICAO标准)
        assert data["flight_rules"] == "LIFR"

    def test_visibility_exactly_4800m(self, parser):
        """能见度恰好4800m → MVFR/IFR边界"""
        metar = "ZGGG 110900Z 18010KT 4800 HZ SCT050 28/20 Q1010"
        data, success, errors = parser.parse(metar)
        assert success
        assert data["visibility"] == 4.8
        # 4800m = 2.98 SM < 3 SM → IFR (严格ICAO标准)
        assert data["flight_rules"] == "IFR"

    def test_visibility_exactly_8000m(self, parser):
        """能见度恰好8000m → VFR/MVFR边界"""
        metar = "ZUUU 111000Z 06005KT 8000 BR FEW040 18/16 Q1015"
        data, success, errors = parser.parse(metar)
        assert success
        assert data["visibility"] == 8.0
        # 8000m = 4.97 SM < 5 SM → MVFR (严格ICAO标准)
        assert data["flight_rules"] == "MVFR"

    def test_visibility_1500m(self, parser):
        """能见度1500m → IFR"""
        metar = "ZLXY 111100Z 28008KT 1500 FG OVC003 08/07 Q1018"
        data, success, errors = parser.parse(metar)
        assert success
        assert data["visibility"] == 1.5
        # 1500m = 0.93 SM < 1 SM → LIFR by vis
        # OVC003 = 300ft < 500ft → LIFR by ceiling
        assert data["flight_rules"] == "LIFR"

    def test_visibility_9999_to_10km(self, parser):
        """能见度9999 → 应转换为约10km"""
        metar = "ZBAA 111200Z 36006KT 9999 FEW040 22/15 Q1015 NOSIG"
        data, success, errors = parser.parse(metar)
        assert success
        assert data["visibility"] == 9.999
        assert data["flight_rules"] == "VFR"


class TestOnlyFewSct:
    """3. 仅 FEW/SCT (无 ceiling) - 3 cases"""

    def test_only_few_cloud_vfr(self, parser):
        """仅FEW云 → 无ceiling → VFR"""
        metar = "ZBAA 110800Z 36006KT 9999 FEW040 22/15 Q1015"
        data, success, errors = parser.parse(metar)
        assert success
        assert data["flight_rules"] == "VFR"
        # FEW 不算 ceiling
        layers = data["cloud_layers"]
        assert all(l["type"] == "FEW" for l in layers)

    def test_only_sct_cloud_vfr(self, parser):
        """仅SCT云 → 无ceiling → VFR"""
        metar = "ZSPD 110900Z 24010KT 9999 SCT040 28/22 Q1008"
        data, success, errors = parser.parse(metar)
        assert success
        assert data["flight_rules"] == "VFR"
        # SCT 不算 ceiling
        layers = data["cloud_layers"]
        assert all(l["type"] == "SCT" for l in layers)

    def test_few_sct_low_no_ceiling(self, parser):
        """FEW010 + SCT020 低位但无ceiling → 视能见度决定"""
        metar = "ZUUU 111000Z 06005KT 5000 FEW010 SCT020 18/16 Q1015"
        data, success, errors = parser.parse(metar)
        assert success
        # 无 BKN/OVC → ceiling = 10000ft (默认)
        # vis=5km ≈ 3.1SM → MVFR
        assert data["flight_rules"] == "MVFR"


class TestNegativeTemperature:
    """4. 负温度解析 (M05/-05) - 3 cases"""

    def test_m_prefix_negative(self, parser):
        """M05 前缀 → -5°C"""
        metar = "ZUUU 111200Z 36010KT 8000 SN BKN010 OVC020 M05/M07 Q1030"
        data, success, errors = parser.parse(metar)
        assert success
        assert data["temperature"] == -5
        assert data["dewpoint"] == -7

    def test_dash_prefix_negative(self, parser):
        """-05 前缀 → -5°C"""
        metar = "ZYHB 111200Z 27008KT 9999 SCT015 BKN030 -05/-10 Q1035"
        data, success, errors = parser.parse(metar)
        assert success
        assert data["temperature"] == -5
        assert data["dewpoint"] == -10

    def test_extreme_negative(self, parser):
        """M20 → -20°C 极寒"""
        metar = "ZYHB 111400Z 32015KT 9999 FEW040 M20/M25 Q1040"
        data, success, errors = parser.parse(metar)
        assert success
        assert data["temperature"] == -20
        assert data["dewpoint"] == -25


class TestWindShearLowVis:
    """5. 风切变 + 低能见度组合 - 3 cases"""

    def test_windshear_with_fog(self, parser):
        """风切变 + 雾 → HIGH/CRITICAL 风险"""
        metar = "ZSPD 110800Z 24015G25KT 0800 FG VV002 06/05 Q1020 WS R17 28030KT"
        data, success, errors = parser.parse(metar)
        assert success
        assert data["wind_shear"] is not None
        assert data["visibility"] == 0.8
        assert data["flight_rules"] == "LIFR"

    def test_windshear_with_rain(self, parser):
        """风切变 + 低能见度雨"""
        metar = "ZSAM 110900Z 32020G30KT 3000 RA BKN008 15/14 Q1010 WS R05 18025KT"
        data, success, errors = parser.parse(metar)
        assert success
        assert data["wind_shear"] is not None
        assert data["visibility"] == 3.0

    def test_windshear_good_visibility(self, parser):
        """风切变 + 好能见度 → VFR但有风切变风险"""
        metar = "ZSAM 111000Z 32028G38KT 9999 SCT040 12/M03 Q1018 WS R23 28040KT"
        data, success, errors = parser.parse(metar)
        assert success
        assert data["wind_shear"] is not None
        assert data["visibility"] == 9.999
        assert data["flight_rules"] == "VFR"


class TestTrendGroups:
    """6. BECMG/TEMPO 趋势 - 3 cases"""

    def test_becmg_trend(self, parser):
        """BECMG 趋势组识别"""
        metar = "ZBAA 110800Z 18010KT 5000 HZ SCT040 20/15 Q1015 BECMG 3000"
        data, success, errors = parser.parse(metar)
        assert success
        assert data["has_trend"] is True
        assert data["trend_type"] == "BECMG"

    def test_tempo_trend(self, parser):
        """TEMPO 趋势组识别"""
        metar = "VHHH 110800Z 09015G25KT 6000 RA BKN020 25/24 Q1008 TEMPO 3000 TSRA"
        data, success, errors = parser.parse(metar)
        assert success
        assert data["has_trend"] is True
        assert data["trend_type"] == "TEMPO"

    def test_nosig_trend(self, parser):
        """NOSIG 趋势组识别"""
        metar = "ZBAA 110900Z 36006KT 9999 FEW040 22/15 Q1015 NOSIG"
        data, success, errors = parser.parse(metar)
        assert success
        assert data["has_trend"] is True
        assert data["trend_type"] == "NOSIG"


class TestMultiLayerClouds:
    """7. 多层云叠加 - 2 cases"""

    def test_three_layer_clouds(self, parser):
        """三层云叠加"""
        metar = "ZGGG 110800Z 18008KT 4000 FEW020 SCT040 BKN080 OVC120 22/20 Q1010"
        data, success, errors = parser.parse(metar)
        assert success
        layers = data["cloud_layers"]
        assert len(layers) == 4
        types = [l["type"] for l in layers]
        assert "FEW" in types
        assert "SCT" in types
        assert "BKN" in types
        assert "OVC" in types

    def test_bkn_ovc_ceiling_determination(self, parser):
        """BKN005 + OVC020 → ceiling应取BKN005"""
        metar = "ZUUU 111000Z 06008KT 3000 RA BKN005 OVC020 15/14 Q1012"
        data, success, errors = parser.parse(metar)
        assert success
        layers = data["cloud_layers"]
        # BKN005 = 500ft → 应作为ceiling
        bkn_layer = [l for l in layers if l["type"] == "BKN"][0]
        assert bkn_layer["height_feet"] == 500
        # ceiling = 500ft → IFR
        assert data["flight_rules"] == "IFR"


class TestAutoStation:
    """8. 自动站 AO1/AO2 - 2 cases"""

    def test_ao1_station(self, parser):
        """AO1 自动站标识"""
        metar = "KLAX 110800Z AO1 24005KT 10SM FEW015 18/12 A3000"
        data, success, errors = parser.parse(metar)
        assert success
        assert data["station_type"] == "AO1"

    def test_ao2_station(self, parser):
        """AO2 自动站标识"""
        metar = "KLAX 110900Z AO2 24008KT 10SM SCT025 20/14 A3002"
        data, success, errors = parser.parse(metar)
        assert success
        assert data["station_type"] == "AO2"


class TestTruncatedAbnormal:
    """9. 截断/异常 METAR - 4 cases"""

    def test_empty_metar(self, parser):
        """空 METAR"""
        data, success, errors = parser.parse("")
        assert not success
        assert len(errors) > 0

    def test_too_short_metar(self, parser):
        """过短 METAR"""
        data, success, errors = parser.parse("AB")
        assert not success
        assert len(errors) > 0

    def test_no_icao_code(self, parser):
        """无 ICAO 代码"""
        data, success, errors = parser.parse("110800Z 24005KT 9999 FEW040 22/15 Q1015")
        assert not success

    def test_truncated_mid_metar(self, parser):
        """截断的 METAR（仅ICAO+时间）"""
        metar = "ZBAA 110800Z"
        data, success, errors = parser.parse(metar)
        # 截断的METAR可能解析失败，但ICAO应该能提取
        assert data["icao_code"] == "ZBAA"


class TestCAVOK:
    """10. CAVOK - 2 cases"""

    def test_cavok_basic(self, parser):
        """基本 CAVOK"""
        metar = "ZSSS 111030Z 35006KT CAVOK 22/15 Q1022"
        data, success, errors = parser.parse(metar)
        assert success
        assert data["is_cavok"] is True
        assert data["visibility"] == 10.0
        assert data["cloud_layers"] == []
        assert data["flight_rules"] == "VFR"

    def test_cavok_with_wind(self, parser):
        """CAVOK + 强风"""
        metar = "ZJHK 111500Z 20022G32KT CAVOK 32/25 Q1008"
        data, success, errors = parser.parse(metar)
        assert success
        assert data["is_cavok"] is True
        assert data["visibility"] == 10.0
        assert data["wind_speed"] == 22
        assert data["wind_gust"] == 32
        assert data["flight_rules"] == "VFR"


class TestSKC_NSC:
    """附赠: SKC/NSC 边界测试"""

    def test_skc_no_clouds(self, parser):
        """SKC 晴空"""
        metar = "ZBAA 110800Z 18005KT 9999 SKC 25/12 Q1015"
        data, success, errors = parser.parse(metar)
        assert success
        assert data["is_skc_nsc"] is True
        assert data["cloud_layers"] == []
        assert data["flight_rules"] == "VFR"

    def test_nsc_no_clouds(self, parser):
        """NSC 无显著云"""
        metar = "ZGGG 110800Z 36010KT 8000 NSC 28/18 Q1012"
        data, success, errors = parser.parse(metar)
        assert success
        assert data["is_skc_nsc"] is True
        assert data["cloud_layers"] == []
        # 8000m = 4.97 SM < 5 SM → MVFR
        assert data["flight_rules"] == "MVFR"


class TestSMVisibility:
    """附赠: SM(英里)能见度测试"""

    def test_sm_integer(self, parser):
        """10SM 能见度"""
        metar = "KLAX 110800Z AO2 24005KT 10SM FEW015 18/12 A3000"
        data, success, errors = parser.parse(metar)
        assert success
        assert data["visibility"] == pytest.approx(16.09, abs=0.1)

    def test_sm_fraction(self, parser):
        """1/2SM 能见度"""
        metar = "KLAX 110900Z AO2 24008KT 1/2SM FG OVC002 12/11 A2990"
        data, success, errors = parser.parse(metar)
        assert success
        assert data["visibility"] == pytest.approx(0.8, abs=0.1)

    def test_sm_mixed(self, parser):
        """1 1/2SM 能见度"""
        metar = "KLAX 111000Z AO2 24005KT 1 1/2SM BR BKN008 15/14 A2995"
        data, success, errors = parser.parse(metar)
        assert success
        assert data["visibility"] == pytest.approx(2.41, abs=0.1)

    def test_m_prefix_sm(self, parser):
        """M1/4SM 能见度 (小于)"""
        metar = "KLAX 111100Z AO2 00000KT M1/4SM FG VV001 10/10 A2980"
        data, success, errors = parser.parse(metar)
        assert success
        assert data["visibility"] == pytest.approx(0.4, abs=0.1)


class TestMPSWindUnit:
    """附赠: MPS 风速单位测试"""

    def test_mps_conversion(self, parser):
        """MPS → KT 转换"""
        metar = "ZSPD 111000Z 24008MPS 9999 FEW030 30/25 Q1010"
        data, success, errors = parser.parse(metar)
        assert success
        # 8 MPS ≈ 15.55 kt → int = 15
        assert data["wind_speed"] == 15

    def test_mps_gust_conversion(self, parser):
        """MPS + G 转换"""
        metar = "ZSPD 111000Z 24010G20MPS 9999 SCT040 28/22 Q1008"
        data, success, errors = parser.parse(metar)
        assert success
        # 10 MPS ≈ 19.4 kt
        assert data["wind_speed"] == 19
        # 20 MPS ≈ 38.9 kt
        assert data["wind_gust"] == 38
