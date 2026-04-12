"""
综合评测套件 (97 用例)

G1: 普通 METAR (12个)
G2: 极端天气 (15个)
G3: 边界 case (13个)
G4: 复合现象 (10个)
额外: 单元测试 (wind_score / temp_score / weights / ceiling zones / flight_rules)
"""
import sys
import os
import pytest

# 确保能导入 app 模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.utils.dynamic_risk_engine import (
    DynamicRiskEngine,
    normalize_temp_score,
    _map_to_flight_rules,
)
from app.utils.wind_assessment import normalize_wind_score
from app.utils.dynamic_weights import get_weight_for_phenomena
from app.utils.ceiling_zones import classify as classify_ceiling, normalize_ceiling_score


# ======================================================================
# 工具函数
# ======================================================================

engine = DynamicRiskEngine()


def make_metar(
    icao="ZSPD",
    wind_dir=180,
    wind_speed=8,
    gust=None,
    vis=9999,
    clouds=None,
    temp=20,
    dewpoint=15,
    phenomena=None,
    altimeter=1013,
):
    """构造简化的 METAR 数据字典"""
    metar = {
        "icao_code": icao,
        "wind_direction": wind_dir,
        "wind_speed": wind_speed,
        "wind_gust": gust,
        "visibility": vis if vis != 9999 else 10.0,
        "temperature": temp,
        "dewpoint": dewpoint,
        "altimeter": altimeter,
        "cloud_layers": clouds or [],
        "present_weather": [],
    }
    if phenomena:
        metar["present_weather"] = [
            {"code": p} if isinstance(p, str) else p for p in phenomena
        ]
    return metar


def run_risk(metar_data, phenomena=None):
    """运行风险引擎并返回报告"""
    return engine.calculate(metar_data, phenomena=phenomena)


# ======================================================================
# G1: 普通 METAR (12个)
# ======================================================================

class TestG1NormalMetar:
    """G1 普通 METAR 测试"""

    def test_g1_01_clear_vfr(self):
        """G1-01: ZSPD 18008KT 9999 FEW040 26/16 -> VFR, LOW"""
        m = make_metar(temp=26, dewpoint=16, vis=10.0,
                       clouds=[{"type": "FEW", "height_feet": 4000}])
        r = run_risk(m)
        assert r.flight_rules == "VFR"
        assert r.overall_risk in ("NONE", "LOW")

    def test_g1_02_mvfr_br(self):
        """G1-02: ZSSS 14012KT 4000 BR SCT030 -> MVFR, LOW"""
        m = make_metar(icao="ZSSS", wind_dir=140, wind_speed=12, vis=4.0,
                       clouds=[{"type": "SCT", "height_feet": 3000}],
                       phenomena=["BR"])
        r = run_risk(m)
        assert r.flight_rules == "MVFR"
        assert r.overall_risk in ("LOW", "MEDIUM")

    def test_g1_03_ifr_ovc(self):
        """G1-03: ZBAA 36015KT 2500 OVC008 -> IFR"""
        m = make_metar(icao="ZBAA", wind_dir=360, wind_speed=15, vis=2.5,
                       clouds=[{"type": "OVC", "height_feet": 800}])
        r = run_risk(m)
        assert r.flight_rules == "IFR"
        assert r.overall_risk in ("LOW", "MEDIUM", "HIGH")

    def test_g1_04_ifr_fg(self):
        """G1-04: ZSNJ 09010KT 1500 FG BKN005 -> IFR"""
        m = make_metar(icao="ZSNJ", wind_dir=90, wind_speed=10, vis=1.5,
                       clouds=[{"type": "BKN", "height_feet": 500}],
                       phenomena=["FG"])
        r = run_risk(m)
        assert r.flight_rules == "IFR"
        assert r.overall_risk in ("MEDIUM", "HIGH", "CRITICAL")

    def test_g1_05_ifr_gust(self):
        """G1-05: ZSCN 27020G30KT 2000 RA OVC006 -> IFR"""
        m = make_metar(icao="ZSCN", wind_dir=270, wind_speed=20, gust=30,
                       vis=2.0, clouds=[{"type": "OVC", "height_feet": 600}],
                       phenomena=["RA"])
        r = run_risk(m)
        assert r.flight_rules == "IFR"
        assert r.overall_risk in ("MEDIUM", "HIGH", "CRITICAL")

    def test_g1_06_lifr_fg_vv(self):
        """G1-06: ZSSS 14012KT 0800 FG VV005 -> LIFR"""
        m = make_metar(icao="ZSSS", wind_dir=140, wind_speed=12, vis=0.8,
                       clouds=[{"type": "VV", "height_feet": 500}],
                       phenomena=["FG"])
        r = run_risk(m)
        assert r.flight_rules == "LIFR"
        assert r.overall_risk in ("HIGH", "CRITICAL")

    def test_g1_07_vfr_clear(self):
        """G1-07: ZSPD 35005KT 9999 SCT040 15/08 -> VFR"""
        m = make_metar(wind_dir=350, wind_speed=5, vis=10.0,
                       clouds=[{"type": "SCT", "height_feet": 4000}],
                       temp=15, dewpoint=8)
        r = run_risk(m)
        assert r.flight_rules == "VFR"
        assert r.overall_risk in ("NONE", "LOW")

    def test_g1_08_mvfr_hz(self):
        """G1-08: ZBAA 18008KT 4500 HZ SCT030 -> MVFR"""
        m = make_metar(icao="ZBAA", vis=4.5,
                       clouds=[{"type": "SCT", "height_feet": 3000}],
                       phenomena=["HZ"])
        r = run_risk(m)
        assert r.flight_rules == "MVFR"
        assert r.overall_risk in ("LOW", "MEDIUM")

    def test_g1_09_vfr_high_wind(self):
        """G1-09: ZWWW 24025G35KT 9999 SCT050 -> VFR, wind elevated"""
        m = make_metar(icao="ZWWW", wind_dir=240, wind_speed=25, gust=35,
                       vis=10.0, clouds=[{"type": "SCT", "height_feet": 5000}])
        r = run_risk(m)
        assert r.flight_rules == "VFR"
        # wind_score should be significant (gust 35 -> base ~61 + penalty 10)
        assert r.wind_score > 50

    def test_g1_10_vfr_cold(self):
        """G1-10: ZLLL 36010KT 9999 NSC M08/M12 -> VFR"""
        m = make_metar(icao="ZLLL", wind_dir=360, wind_speed=10, vis=10.0,
                       temp=-8, dewpoint=-12)
        r = run_risk(m)
        assert r.flight_rules == "VFR"
        assert r.temp_score > 0

    def test_g1_11_mvfr_tcu(self):
        """G1-11: ZGGG 12008KT 4000 SCT025TCU -> MVFR"""
        m = make_metar(icao="ZGGG", wind_dir=120, wind_speed=8, vis=4.0,
                       clouds=[{"type": "SCT", "height_feet": 2500}])
        r = run_risk(m)
        assert r.flight_rules == "MVFR"
        assert r.overall_risk in ("LOW", "MEDIUM")

    def test_g1_12_lifr_fog(self):
        """G1-12: ZUUU 00000KT 0400 FG VV001 -> LIFR"""
        m = make_metar(icao="ZUUU", wind_dir=0, wind_speed=0, vis=0.4,
                       clouds=[{"type": "VV", "height_feet": 100}],
                       phenomena=["FG"])
        r = run_risk(m)
        assert r.flight_rules == "LIFR"
        assert r.overall_risk in ("HIGH", "CRITICAL")


# ======================================================================
# G2: 极端天气 (15个)
# ======================================================================

class TestG2ExtremeWeather:
    """G2 极端天气测试"""

    def test_g2_01_fzra(self):
        """G2-01: FZRA VV002 M01/M03 -> LIFR, CRITICAL, FZRA-01"""
        m = make_metar(vis=2.0,
                       clouds=[{"type": "VV", "height_feet": 200}],
                       temp=-1, dewpoint=-3, phenomena=["FZRA"])
        r = run_risk(m)
        assert r.flight_rules == "LIFR"
        assert r.overall_risk == "CRITICAL"
        assert any("FZRA-01" in o for o in r.override_reasons)

    def test_g2_02_tsra(self):
        """G2-02: +TSRA BKN010CB 25kt -> CRITICAL"""
        m = make_metar(wind_speed=25, vis=5.0,
                       clouds=[{"type": "BKN", "height_feet": 1000}],
                       phenomena=["+TSRA"])
        r = run_risk(m)
        assert r.overall_risk == "CRITICAL"

    def test_g2_03_ss(self):
        """G2-03: SS 24030G45KT 0500 -> HIGH/CRITICAL"""
        m = make_metar(wind_dir=240, wind_speed=30, gust=45, vis=0.5,
                       phenomena=["SS"])
        r = run_risk(m)
        assert r.overall_risk in ("HIGH", "CRITICAL")

    def test_g2_04_tsra_gust(self):
        """G2-04: +TSRA CB005 40G60KT -> IFR/LIFR, CRITICAL"""
        m = make_metar(wind_speed=40, gust=60, vis=3.0,
                       clouds=[{"type": "BKN", "height_feet": 500}],
                       phenomena=["+TSRA"])
        r = run_risk(m)
        assert r.flight_rules in ("IFR", "LIFR")
        assert r.overall_risk == "CRITICAL"

    def test_g2_05_ws(self):
        """G2-05: WS R18/28030KT 9999 -> CRITICAL, W-02"""
        m = make_metar(wind_speed=10, vis=10.0, phenomena=["WS"])
        r = run_risk(m)
        assert r.overall_risk == "CRITICAL"
        assert any("W-02" in o for o in r.override_reasons)

    def test_g2_06_fzfg(self):
        """G2-06: FZFG OVC003 M02/M04 -> LIFR, CRITICAL"""
        m = make_metar(vis=0.5,
                       clouds=[{"type": "OVC", "height_feet": 300}],
                       temp=-2, dewpoint=-4, phenomena=["FZFG"])
        r = run_risk(m)
        assert r.flight_rules == "LIFR"
        assert r.overall_risk == "CRITICAL"

    def test_g2_07_heavy_snow(self):
        """G2-07: +SN VV002 M05/M07 -> LIFR"""
        m = make_metar(vis=1.0,
                       clouds=[{"type": "VV", "height_feet": 200}],
                       temp=-5, dewpoint=-7, phenomena=["+SN"])
        r = run_risk(m)
        assert r.flight_rules == "LIFR"
        assert r.overall_risk in ("HIGH", "CRITICAL")

    def test_g2_08_fc(self):
        """G2-08: FC 9999 SCT050 -> CRITICAL"""
        m = make_metar(vis=10.0,
                       clouds=[{"type": "SCT", "height_feet": 5000}],
                       phenomena=["FC"])
        r = run_risk(m)
        assert r.overall_risk == "CRITICAL"

    def test_g2_09_heavy_ra_gust(self):
        """G2-09: +RA BKN015 45G58KT -> CRITICAL"""
        m = make_metar(wind_speed=45, gust=58, vis=3.0,
                       clouds=[{"type": "BKN", "height_feet": 1500}],
                       phenomena=["+RA"])
        r = run_risk(m)
        assert r.overall_risk == "CRITICAL"

    def test_g2_10_va(self):
        """G2-10: VA OVC020 -> MVFR, MEDIUM/HIGH"""
        m = make_metar(vis=5.0,
                       clouds=[{"type": "OVC", "height_feet": 2000}],
                       phenomena=["VA"])
        r = run_risk(m)
        assert r.overall_risk in ("LOW", "MEDIUM", "HIGH")
        assert r.flight_rules == "MVFR"

    def test_g2_11_gr_ts(self):
        """G2-11: GR TSRA BKN008CB -> CRITICAL"""
        m = make_metar(vis=3.0,
                       clouds=[{"type": "BKN", "height_feet": 800}],
                       phenomena=["GR", "TSRA"])
        r = run_risk(m)
        assert r.overall_risk == "CRITICAL"

    def test_g2_12_fzdz(self):
        """G2-12: FZDZ VV003 M01/M02 -> LIFR, CRITICAL, FZRA-01"""
        m = make_metar(vis=2.0,
                       clouds=[{"type": "VV", "height_feet": 300}],
                       temp=-1, dewpoint=-2, phenomena=["FZDZ"])
        r = run_risk(m)
        assert r.flight_rules == "LIFR"
        assert r.overall_risk == "CRITICAL"
        assert any("FZRA" in o for o in r.override_reasons)

    def test_g2_13_ds(self):
        """G2-13: DS 24040KT 0300 -> LIFR, CRITICAL"""
        m = make_metar(wind_dir=240, wind_speed=40, vis=0.3,
                       phenomena=["DS"])
        r = run_risk(m)
        assert r.flight_rules == "LIFR"
        assert r.overall_risk == "CRITICAL"

    def test_g2_14_blsn(self):
        """G2-14: BLSN VV005 M12/M15 -> IFR/LIFR"""
        m = make_metar(vis=2.0,
                       clouds=[{"type": "VV", "height_feet": 500}],
                       temp=-12, dewpoint=-15, phenomena=["BLSN"])
        r = run_risk(m)
        assert r.flight_rules in ("IFR", "LIFR")
        assert r.overall_risk in ("MEDIUM", "HIGH", "CRITICAL")

    def test_g2_15_tsgr(self):
        """G2-15: TSGR BKN010CB 30G45KT -> CRITICAL"""
        m = make_metar(wind_speed=30, gust=45, vis=4.0,
                       clouds=[{"type": "BKN", "height_feet": 1000}],
                       phenomena=["TSGR"])
        r = run_risk(m)
        assert r.overall_risk == "CRITICAL"


# ======================================================================
# G3: 边界 case (13个)
# ======================================================================

class TestG3BoundaryCases:
    """G3 边界 case 测试"""

    def test_g3_01_vis_4800m(self):
        """G3-01: 能见度 4800m -> MVFR"""
        m = make_metar(vis=4.8)
        r = run_risk(m)
        assert r.flight_rules == "MVFR"

    def test_g3_02_vis_5000m(self):
        """G3-02: 能见度 5000m -> VFR (exact boundary)"""
        m = make_metar(vis=5.0)
        r = run_risk(m)
        # 5.0 is >= 5, so vis_rules = VFR
        assert r.flight_rules == "VFR"

    def test_g3_03_vis_8000m(self):
        """G3-03: 能见度 8000m -> VFR"""
        m = make_metar(vis=8.0)
        r = run_risk(m)
        assert r.flight_rules == "VFR"

    def test_g3_04_ceil_300ft(self):
        """G3-04: 云底高 300ft -> LIFR"""
        m = make_metar(clouds=[{"type": "BKN", "height_feet": 300}])
        r = run_risk(m)
        assert r.flight_rules == "LIFR"

    def test_g3_05_ceil_500ft(self):
        """G3-05: 云底高 500ft -> IFR/LIFR (boundary)"""
        m = make_metar(clouds=[{"type": "BKN", "height_feet": 500}])
        r = run_risk(m)
        assert r.flight_rules in ("IFR", "LIFR")

    def test_g3_06_ceil_1000ft(self):
        """G3-06: 云底高 1000ft -> MVFR/IFR (boundary)"""
        m = make_metar(clouds=[{"type": "BKN", "height_feet": 1000}])
        r = run_risk(m)
        assert r.flight_rules in ("MVFR", "IFR")

    def test_g3_07_wind_19ms(self):
        """G3-07: 风速 ~19m/s (37kt) -> 不触发 W-01"""
        m = make_metar(wind_speed=37, vis=10.0)
        r = run_risk(m)
        assert not any("W-01" in o for o in r.override_reasons)

    def test_g3_08_wind_20ms(self):
        """G3-08: 风速 ~20m/s (39kt) -> 触发 W-01"""
        m = make_metar(wind_speed=39, vis=10.0)
        r = run_risk(m)
        assert any("W-01" in o for o in r.override_reasons)

    def test_g3_09_ice_temp_minus1(self):
        """G3-09: 温度 -1°C -> 积冰高风险"""
        score = normalize_temp_score(-1)
        # -1 -> 60 + 25*1/5 = 65
        assert 60 <= score <= 75

    def test_g3_10_ice_temp_0(self):
        """G3-10: 温度 0°C -> 积冰临界"""
        score = normalize_temp_score(0)
        assert score == 60.0

    def test_g3_11_fzra_typical(self):
        """G3-11: FZRA 典型条件 (T=-2, VIS=1, DPD=1) -> FZRA-01"""
        m = make_metar(temp=-2, dewpoint=-3, vis=1.0, phenomena=["FZRA"])
        r = run_risk(m)
        assert any("FZRA-01" in o for o in r.override_reasons)

    def test_g3_12_fzra_atypical(self):
        """G3-12: FZRA 非典型条件 (T=5, VIS=10) -> FZRA-WARN"""
        m = make_metar(temp=5, dewpoint=0, vis=10.0, phenomena=["FZRA"])
        r = run_risk(m)
        assert any("FZRA-WARN" in o for o in r.override_reasons)
        assert not any("FZRA-01" in o for o in r.override_reasons)

    def test_g3_13_high_wind_good_weather(self):
        """G3-13: 大风+好天气 (40kt + 8000m + SCT050) -> HIGH/CRITICAL"""
        m = make_metar(wind_speed=40, vis=8.0,
                       clouds=[{"type": "SCT", "height_feet": 5000}])
        r = run_risk(m)
        assert r.overall_risk in ("HIGH", "CRITICAL")


# ======================================================================
# G4: 复合现象 (10个)
# ======================================================================

class TestG4CompoundPhenomena:
    """G4 复合现象测试"""

    def test_g4_01_fg_sn(self):
        """G4-01: FG+SN+BKN005 -> LIFR"""
        m = make_metar(vis=0.5,
                       clouds=[{"type": "BKN", "height_feet": 500}],
                       temp=-3, dewpoint=-4, phenomena=["FG", "SN"])
        r = run_risk(m)
        assert r.flight_rules == "LIFR"
        assert r.overall_risk in ("HIGH", "CRITICAL")

    def test_g4_02_tsra_cb(self):
        """G4-02: +TSRA -> CRITICAL"""
        m = make_metar(vis=4.0,
                       clouds=[{"type": "BKN", "height_feet": 1500}],
                       phenomena=["+TSRA"])
        r = run_risk(m)
        assert r.overall_risk == "CRITICAL"

    def test_g4_03_fzra_fg(self):
        """G4-03: FZRA+FG -> LIFR, CRITICAL"""
        m = make_metar(vis=0.5,
                       clouds=[{"type": "VV", "height_feet": 200}],
                       temp=-1, dewpoint=-2, phenomena=["FZRA", "FG"])
        r = run_risk(m)
        assert r.flight_rules == "LIFR"
        assert r.overall_risk == "CRITICAL"

    def test_g4_04_tsra_gr_gust(self):
        """G4-04: +TSRA+GR 40kt -> CRITICAL"""
        m = make_metar(wind_speed=40, vis=2.0,
                       clouds=[{"type": "BKN", "height_feet": 800}],
                       phenomena=["+TSRA", "GR"])
        r = run_risk(m)
        assert r.overall_risk == "CRITICAL"

    def test_g4_05_fg_br(self):
        """G4-05: FG+BR -> IFR/LIFR"""
        m = make_metar(vis=0.8,
                       clouds=[{"type": "SCT", "height_feet": 3000}],
                       phenomena=["FG", "BR"])
        r = run_risk(m)
        assert r.flight_rules in ("IFR", "LIFR")

    def test_g4_06_ra_sn(self):
        """G4-06: RA+SN -> elevated risk"""
        m = make_metar(vis=3.0,
                       clouds=[{"type": "BKN", "height_feet": 2000}],
                       temp=0, dewpoint=-1, phenomena=["RA", "SN"])
        r = run_risk(m)
        assert r.overall_risk in ("MEDIUM", "HIGH", "CRITICAL")

    def test_g4_07_hz_fg(self):
        """G4-07: HZ+FG -> IFR/LIFR"""
        m = make_metar(vis=1.0,
                       clouds=[{"type": "SCT", "height_feet": 4000}],
                       phenomena=["HZ", "FG"])
        r = run_risk(m)
        assert r.flight_rules in ("IFR", "LIFR")

    def test_g4_08_ss_ts(self):
        """G4-08: SS+TS -> CRITICAL"""
        m = make_metar(wind_speed=35, vis=0.5,
                       phenomena=["SS", "TS"])
        r = run_risk(m)
        assert r.overall_risk == "CRITICAL"

    def test_g4_09_fzfg_sn(self):
        """G4-09: FZFG+SN -> LIFR, CRITICAL"""
        m = make_metar(vis=0.3,
                       clouds=[{"type": "OVC", "height_feet": 300}],
                       temp=-5, dewpoint=-6, phenomena=["FZFG", "SN"])
        r = run_risk(m)
        assert r.flight_rules == "LIFR"
        assert r.overall_risk == "CRITICAL"

    def test_g4_10_va_hz(self):
        """G4-10: VA+HZ -> MVFR"""
        m = make_metar(vis=3.0,
                       clouds=[{"type": "OVC", "height_feet": 2000}],
                       phenomena=["VA", "HZ"])
        r = run_risk(m)
        assert r.flight_rules == "MVFR"
        assert r.overall_risk in ("LOW", "MEDIUM", "HIGH")


# ======================================================================
# 单元测试: wind_score
# ======================================================================

class TestWindScore:
    """wind_score 归一化测试 (不能超过100)"""

    def test_wind_0(self):
        assert normalize_wind_score(0) == 0.0

    def test_wind_10(self):
        assert normalize_wind_score(10) == 0.0

    def test_wind_20(self):
        assert normalize_wind_score(20) == 20.0

    def test_wind_30(self):
        assert normalize_wind_score(30) == 40.0

    def test_wind_50(self):
        assert normalize_wind_score(50) == 85.0

    def test_wind_80(self):
        assert normalize_wind_score(80) == 100.0

    def test_wind_50_gust_70(self):
        """wind_score(50, 70) should be <= 100"""
        score = normalize_wind_score(50, 70)
        assert score <= 100.0

    def test_wind_60_gust_75(self):
        """wind_score(60, 75) should be <= 100"""
        score = normalize_wind_score(60, 75)
        assert score <= 100.0

    def test_wind_100(self):
        """Extreme wind should cap at 100"""
        assert normalize_wind_score(100) == 100.0

    def test_gust_penalty_applied(self):
        """Gust penalty should increase score"""
        base = normalize_wind_score(30, None)  # 40.0
        with_gust = normalize_wind_score(25, 45)  # speed=45, base=77.5, penalty=15
        assert with_gust > base

    def test_no_score_exceeds_100(self):
        """For any input, score must be <= 100"""
        for speed in [0, 10, 20, 30, 40, 50, 60, 80, 100, 200]:
            for gust in [None, speed + 5, speed + 10, speed + 20, speed + 30]:
                s = normalize_wind_score(speed, gust)
                assert s <= 100.0, f"wind_score({speed}, {gust}) = {s} > 100"
                assert s >= 0.0, f"wind_score({speed}, {gust}) = {s} < 0"


# ======================================================================
# 单元测试: temp_score
# ======================================================================

class TestTempScore:
    """temp_score 6档连续映射测试"""

    def test_temp_none(self):
        assert normalize_temp_score(None) == 0.0

    def test_temp_10(self):
        """10°C > 5°C -> 0"""
        assert normalize_temp_score(10) == 0.0

    def test_temp_5(self):
        """5°C -> 20"""
        assert normalize_temp_score(5) == 20.0

    def test_temp_2(self):
        """2°C -> 40"""
        assert normalize_temp_score(2) == 40.0

    def test_temp_0(self):
        """0°C -> 60"""
        assert normalize_temp_score(0) == 60.0

    def test_temp_minus1(self):
        """-1°C -> 65"""
        assert normalize_temp_score(-1) == 65.0

    def test_temp_minus5(self):
        """-5°C -> 85"""
        assert normalize_temp_score(-5) == 85.0

    def test_temp_minus8(self):
        """-8°C -> 89.5"""
        score = normalize_temp_score(-8)
        assert 85 < score < 95

    def test_temp_minus10(self):
        """-10°C -> 92.5"""
        score = normalize_temp_score(-10)
        assert score == 92.5

    def test_temp_minus15(self):
        """-15°C -> 60 (risk drops in extreme cold)"""
        assert normalize_temp_score(-15) == 60.0

    def test_temp_minus20(self):
        """-20°C -> 72.5"""
        score = normalize_temp_score(-20)
        assert score == 72.5

    def test_temp_minus25(self):
        """-25°C -> 85"""
        assert normalize_temp_score(-25) == 85.0

    def test_temp_minus30(self):
        """-30°C < -25 -> 0"""
        assert normalize_temp_score(-30) == 0.0

    def test_continuity(self):
        """Verify score continuity at internal boundaries (except -15 which has a designed step)"""
        # Internal boundaries should be continuous
        for t in [2, 0, -5]:
            left = normalize_temp_score(t + 0.01)
            right = normalize_temp_score(t - 0.01)
            assert abs(left - right) < 2.0, f"Discontinuity at {t}: {left} vs {right}"


# ======================================================================
# 单元测试: weights 归一化
# ======================================================================

class TestWeightsNormalization:
    """权重归一化测试: sum(weights) == 1.0"""

    def test_empty(self):
        w = get_weight_for_phenomena([])
        assert abs(sum(w.values()) - 1.0) < 0.01

    def test_fg(self):
        w = get_weight_for_phenomena(["FG"])
        assert abs(sum(w.values()) - 1.0) < 0.01

    def test_fg_ss(self):
        """FG(0.70) + SS(0.75) -> need normalization"""
        w = get_weight_for_phenomena(["FG", "SS"])
        assert abs(sum(w.values()) - 1.0) < 0.01

    def test_tsra_gr(self):
        w = get_weight_for_phenomena(["+TSRA", "GR"])
        assert abs(sum(w.values()) - 1.0) < 0.01

    def test_fzra(self):
        w = get_weight_for_phenomena(["FZRA"])
        assert abs(sum(w.values()) - 1.0) < 0.01

    def test_multiple_extreme(self):
        w = get_weight_for_phenomena(["FZRA", "TS", "SS", "WS"])
        assert abs(sum(w.values()) - 1.0) < 0.01

    def test_all_phenomena(self):
        """Test normalization for every known phenomenon"""
        from app.utils.dynamic_weights import WEIGHT_MATRIX
        for code in WEIGHT_MATRIX:
            if code.startswith("_"):
                continue
            w = get_weight_for_phenomena([code])
            assert abs(sum(w.values()) - 1.0) < 0.01, f"Failed for {code}: sum={sum(w.values())}"


# ======================================================================
# 单元测试: ceiling zones (6 zones)
# ======================================================================

class TestCeilingZones:
    """6级云底高区间测试"""

    def test_none_ceiling(self):
        z = classify_ceiling(None)
        assert z.zone == 1

    def test_5000ft(self):
        z = classify_ceiling(5000)
        assert z.zone == 1

    def test_3000ft(self):
        z = classify_ceiling(3000)
        assert z.zone == 2

    def test_2000ft(self):
        z = classify_ceiling(2000)
        assert z.zone == 3  # MVFR

    def test_800ft(self):
        z = classify_ceiling(800)
        assert z.zone == 4  # IFR

    def test_400ft(self):
        z = classify_ceiling(400)
        assert z.zone == 5  # LIFR

    def test_200ft(self):
        z = classify_ceiling(200)
        assert z.zone == 6  # UNAIR

    def test_normalize_5000(self):
        assert normalize_ceiling_score(5000) == 0.0

    def test_normalize_4000(self):
        assert normalize_ceiling_score(4000) == 0.0

    def test_normalize_2500(self):
        assert normalize_ceiling_score(2500) == 15.0

    def test_normalize_1000(self):
        assert normalize_ceiling_score(1000) == 35.0

    def test_normalize_500(self):
        assert normalize_ceiling_score(500) == 60.0

    def test_normalize_300(self):
        assert normalize_ceiling_score(300) == 80.0

    def test_normalize_0(self):
        assert normalize_ceiling_score(0) == 100.0


# ======================================================================
# 单元测试: flight rules mapping
# ======================================================================

class TestFlightRulesMapping:
    """飞行规则映射测试"""

    def test_vfr(self):
        assert _map_to_flight_rules(20, 10, 0, 10.0, 5000) == "VFR"

    def test_mvfr_vis(self):
        assert _map_to_flight_rules(30, 40, 0, 4.0, 5000) == "MVFR"

    def test_ifr_ceil(self):
        assert _map_to_flight_rules(50, 10, 40, 10.0, 800) == "IFR"

    def test_lifr_vis(self):
        assert _map_to_flight_rules(90, 95, 10, 0.5, 5000) == "LIFR"

    def test_strictest_wins(self):
        """取最严格: vis=VFR, ceil=IFR -> IFR"""
        assert _map_to_flight_rules(20, 10, 40, 10.0, 800) == "IFR"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
