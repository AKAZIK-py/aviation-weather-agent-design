"""
航空天气AI系统 - Golden Set生成器
生成用于评测的边界天气测试案例集
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from enum import Enum


class TestType(Enum):
    """测试类型"""
    BOUNDARY_WEATHER = "boundary_weather"
    NORMAL_WEATHER = "normal_weather"
    EDGE_CASE = "edge_case"


class WeatherCategory(Enum):
    """天气类别"""
    VISIBILITY = "visibility"
    CEILING = "ceiling"
    WIND = "wind"
    WEATHER = "weather"
    COMPLEX = "complex"
    NORMAL = "normal"


@dataclass
class TestCase:
    """测试案例数据结构"""
    test_id: str
    description: str
    test_type: TestType
    category: WeatherCategory
    raw_metar: str
    raw_taf: str
    expected_results: Dict[str, Any]
    severity: str  # critical, warning, normal
    notes: Optional[str] = None


class GoldenSetGenerator:
    """Golden Set生成器"""
    
    def __init__(self):
        self.test_cases: List[TestCase] = []
    
    def generate_boundary_weather_cases(self) -> List[TestCase]:
        """生成边界天气测试案例"""
        
        cases = [
            # BOUNDARY_001: 能见度边界 - 临界值测试
            TestCase(
                test_id="BOUNDARY_001",
                description="能见度边界测试 - 1500米（接近1600米临界值）",
                test_type=TestType.BOUNDARY_WEATHER,
                category=WeatherCategory.VISIBILITY,
                raw_metar="ZBAA 091200Z 24008MPS 1500 BR FEW010 10/09 Q1013",
                raw_taf="TAF ZBAA 091100Z 0912/1006 24008MPS 1500 BR FEW010 TEMPO 0915/0918 0800 FG",
                expected_results={
                    "visibility": {
                        "value": 1500,
                        "unit": "meters",
                        "boundary_flag": True,
                        "critical_threshold": 1600
                    },
                    "is_boundary_weather": True,
                    "weather_phenomena": ["BR", "FG"],
                    "risk_level": "high"
                },
                severity="critical",
                notes="能见度接近临界值，需触发边界天气告警"
            ),
            
            # BOUNDARY_002: 能见度边界 - 低于标准
            TestCase(
                test_id="BOUNDARY_002",
                description="能见度边界测试 - 800米（低于1600米标准）",
                test_type=TestType.BOUNDARY_WEATHER,
                category=WeatherCategory.VISIBILITY,
                raw_metar="ZBAA 091500Z 35012MPS 0800 FG OVC003 08/07 Q1008",
                raw_taf="TAF ZBAA 091400Z 0915/1006 35012MPS 0800 FG OVC003 BECMG 0918/0920 5000 BR BKN010",
                expected_results={
                    "visibility": {
                        "value": 800,
                        "unit": "meters",
                        "boundary_flag": True,
                        "critical_threshold": 1600
                    },
                    "is_boundary_weather": True,
                    "weather_phenomena": ["FG", "BR"],
                    "risk_level": "critical"
                },
                severity="critical",
                notes="能见度严重低于标准，需紧急告警"
            ),
            
            # BOUNDARY_003: 云底高边界 - 临界值测试
            TestCase(
                test_id="BOUNDARY_003",
                description="云底高边界测试 - 90米（接近100米临界值）",
                test_type=TestType.BOUNDARY_WEATHER,
                category=WeatherCategory.CEILING,
                raw_metar="ZBAA 091800Z 27006MPS 3000 BR SCT009 OVC015 12/11 Q1015",
                raw_taf="TAF ZBAA 091700Z 0918/1006 27006MPS 3000 BR SCT009 OVC015 TEMPO 0921/0924 6000 BKN020",
                expected_results={
                    "ceiling": {
                        "height": 900,
                        "unit": "feet",
                        "boundary_flag": True,
                        "critical_threshold": 1000
                    },
                    "is_boundary_weather": True,
                    "risk_level": "high"
                },
                severity="critical",
                notes="云底高接近临界值，需触发边界天气告警"
            ),
            
            # BOUNDARY_004: 云底高边界 - 低于标准
            TestCase(
                test_id="BOUNDARY_004",
                description="云底高边界测试 - 60米（低于100米标准）",
                test_type=TestType.BOUNDARY_WEATHER,
                category=WeatherCategory.CEILING,
                raw_metar="ZBAA 092100Z 31005MPS 1500 FG VV006 07/06 Q1010",
                raw_taf="TAF ZBAA 092000Z 0921/1006 31005MPS 1500 FG VV006 TEMPO 1003/1006 0300 FG VV002",
                expected_results={
                    "ceiling": {
                        "height": 600,
                        "unit": "feet",
                        "boundary_flag": True,
                        "critical_threshold": 1000
                    },
                    "visibility": {
                        "value": 1500,
                        "unit": "meters",
                        "boundary_flag": True
                    },
                    "is_boundary_weather": True,
                    "risk_level": "critical"
                },
                severity="critical",
                notes="云底高和能见度双低，极端边界天气"
            ),
            
            # BOUNDARY_005: 风速边界 - 临界值测试
            TestCase(
                test_id="BOUNDARY_005",
                description="风速边界测试 - 15m/s（接近17m/s临界值）",
                test_type=TestType.BOUNDARY_WEATHER,
                category=WeatherCategory.WIND,
                raw_metar="ZBAA 091300Z 26015G22MPS 9999 SCT030 18/08 Q1012",
                raw_taf="TAF ZBAA 091200Z 0912/1006 26015G22MPS 9999 SCT030 TEMPO 0915/0918 26018G28MPS",
                expected_results={
                    "wind": {
                        "speed": 15,
                        "gust": 22,
                        "unit": "m/s",
                        "boundary_flag": True,
                        "critical_threshold": 17
                    },
                    "is_boundary_weather": True,
                    "risk_level": "high"
                },
                severity="warning",
                notes="风速接近临界值，阵风超标"
            ),
            
            # BOUNDARY_006: 风速边界 - 超过标准
            TestCase(
                test_id="BOUNDARY_006",
                description="风速边界测试 - 20m/s（超过17m/s标准）",
                test_type=TestType.BOUNDARY_WEATHER,
                category=WeatherCategory.WIND,
                raw_metar="ZBAA 091600Z 32020G32MPS 9999 BKN040 14/02 Q1007",
                raw_taf="TAF ZBAA 091500Z 0916/1006 32020G32MPS 9999 BKN040 TEMPO 0918/0921 32025G38MPS",
                expected_results={
                    "wind": {
                        "speed": 20,
                        "gust": 32,
                        "unit": "m/s",
                        "boundary_flag": True,
                        "critical_threshold": 17
                    },
                    "is_boundary_weather": True,
                    "risk_level": "critical"
                },
                severity="critical",
                notes="风速和阵风均超过标准，需告警"
            ),
            
            # BOUNDARY_007: 天气现象 - 雷暴
            TestCase(
                test_id="BOUNDARY_007",
                description="天气现象边界测试 - 雷暴",
                test_type=TestType.BOUNDARY_WEATHER,
                category=WeatherCategory.WEATHER,
                raw_metar="ZBAA 091400Z 18010MPS 6000 TSRA SCT030CB BKN040 16/14 Q1009",
                raw_taf="TAF ZBAA 091300Z 0914/1006 18010MPS 6000 TSRA SCT030CB BKN040 TEMPO 0916/0919 3000 +TSRA BKN025CB",
                expected_results={
                    "weather_phenomena": ["TS", "TSRA", "+TSRA"],
                    "cloud_type": ["CB"],
                    "is_boundary_weather": True,
                    "risk_level": "critical"
                },
                severity="critical",
                notes="雷暴天气，严重影响飞行安全"
            ),
            
            # BOUNDARY_008: 天气现象 - 强降水
            # 注：能见度2000m > 1600m阈值，不应触发能见度边界
            # 但+SHRA（强阵雨）属于危险天气现象，应触发整体边界天气
            TestCase(
                test_id="BOUNDARY_008",
                description="天气现象边界测试 - 强降水",
                test_type=TestType.BOUNDARY_WEATHER,
                category=WeatherCategory.WEATHER,
                raw_metar="ZBAA 091700Z 22008MPS 2000 +SHRA OVC015 13/12 Q1010",
                raw_taf="TAF ZBAA 091600Z 0917/1006 22008MPS 2000 +SHRA OVC015 BECMG 0920/0922 6000 -SHRA BKN020",
                expected_results={
                    "weather_phenomena": ["+SHRA", "-SHRA"],
                    "visibility": {
                        "value": 2000,
                        "unit": "meters",
                        "boundary_flag": False  # 能见度2000m > 1600m，不触发能见度边界
                    },
                    "is_boundary_weather": True,  # +SHRA强降水触发整体边界天气
                    "boundary_reason": "hazardous_weather",  # 边界原因：危险天气现象
                    "risk_level": "high"
                },
                severity="warning",
                notes="强降水影响能见度，+SHRA触发边界天气"
            ),
            
            # BOUNDARY_009: 复杂边界天气 - 低能见度+低云底高
            TestCase(
                test_id="BOUNDARY_009",
                description="复杂边界天气 - 低能见度+低云底高",
                test_type=TestType.BOUNDARY_WEATHER,
                category=WeatherCategory.COMPLEX,
                raw_metar="ZBAA 091900Z 04005MPS 1200 FG VV008 06/05 Q1018",
                raw_taf="TAF ZBAA 091800Z 0919/1006 04005MPS 1200 FG VV008 TEMPO 1001/1004 0200 +FG VV002",
                expected_results={
                    "visibility": {
                        "value": 1200,
                        "unit": "meters",
                        "boundary_flag": True,
                        "critical_threshold": 1600
                    },
                    "ceiling": {
                        "height": 800,
                        "unit": "feet",
                        "boundary_flag": True,
                        "critical_threshold": 1000
                    },
                    "weather_phenomena": ["FG", "+FG"],
                    "is_boundary_weather": True,
                    "risk_level": "critical"
                },
                severity="critical",
                notes="双重边界条件，极端天气场景"
            ),
            
            # BOUNDARY_010: 复杂边界天气 - 强风+雷暴
            TestCase(
                test_id="BOUNDARY_010",
                description="复杂边界天气 - 强风+雷暴",
                test_type=TestType.BOUNDARY_WEATHER,
                category=WeatherCategory.COMPLEX,
                raw_metar="ZBAA 092000Z 29018G30MPS 4000 TSRA SCT025CB BKN035 19/12 Q1002",
                raw_taf="TAF ZBAA 091900Z 0920/1006 29018G30MPS 4000 TSRA SCT025CB BKN035 TEMPO 0922/1002 28025G40MPS 1500 +TSRA BKN015CB",
                expected_results={
                    "wind": {
                        "speed": 18,
                        "gust": 30,
                        "unit": "m/s",
                        "boundary_flag": True,
                        "critical_threshold": 17
                    },
                    "weather_phenomena": ["TS", "TSRA", "+TSRA"],
                    "cloud_type": ["CB"],
                    "visibility": {
                        "value": 4000,
                        "unit": "meters",
                        "boundary_flag": False
                    },
                    "is_boundary_weather": True,
                    "risk_level": "critical"
                },
                severity="critical",
                notes="雷暴伴强风，极端天气组合"
            ),
            
            # BOUNDARY_011: 能见度边界 - CAVOK转差
            TestCase(
                test_id="BOUNDARY_011",
                description="能见度边界测试 - CAVOK转边界天气",
                test_type=TestType.BOUNDARY_WEATHER,
                category=WeatherCategory.VISIBILITY,
                raw_metar="ZBAA 092200Z 18004MPS 1400 HZ FEW020 22/15 Q1010",
                raw_taf="TAF ZBAA 092100Z 0922/1006 18004MPS CAVOK BECMG 1003/1005 18004MPS 1400 HZ FEW020",
                expected_results={
                    "visibility": {
                        "value": 1400,
                        "unit": "meters",
                        "boundary_flag": True,
                        "critical_threshold": 1600
                    },
                    "is_boundary_weather": True,
                    "weather_phenomena": ["HZ"],
                    "risk_level": "high"
                },
                severity="warning",
                notes="能见度从CAVOK降至边界值"
            ),
            
            # BOUNDARY_012: 风向突变
            TestCase(
                test_id="BOUNDARY_012",
                description="风向突变边界测试",
                test_type=TestType.BOUNDARY_WEATHER,
                category=WeatherCategory.WIND,
                raw_metar="ZBAA 092300Z 08010MPS 9999 SCT040 15/08 Q1016",
                raw_taf="TAF ZBAA 092200Z 0923/1006 32008MPS 9999 SCT040 TEMPO 0924/1003 08015G25MPS",
                expected_results={
                    "wind": {
                        "direction_change": True,
                        "from_direction": 320,
                        "to_direction": 80,
                        "speed": 15,
                        "gust": 25,
                        "unit": "m/s",
                        "boundary_flag": True
                    },
                    "is_boundary_weather": True,
                    "risk_level": "high"
                },
                severity="warning",
                notes="风向突变伴随风速增大"
            ),
            
            # BOUNDARY_013: 降水伴随低能见度
            TestCase(
                test_id="BOUNDARY_013",
                description="降水伴随低能见度边界测试",
                test_type=TestType.BOUNDARY_WEATHER,
                category=WeatherCategory.COMPLEX,
                raw_metar="ZBAA 092400Z 15012MPS 1700 -RASN BR OVC008 03/01 Q1012",
                raw_taf="TAF ZBAA 092300Z 0924/1006 15012MPS 1700 -RASN BR OVC008 TEMPO 1002/1006 0800 RASN FG VV004",
                expected_results={
                    "visibility": {
                        "value": 1700,
                        "unit": "meters",
                        "boundary_flag": False,  # 1700m > 1600m阈值，不触发边界
                        "critical_threshold": 1600
                    },
                    "ceiling": {
                        "height": 800,
                        "unit": "feet",
                        "boundary_flag": True,
                        "critical_threshold": 1000
                    },
                    "weather_phenomena": ["-RASN", "RASN", "BR", "FG"],
                    "is_boundary_weather": True,
                    "risk_level": "critical"
                },
                severity="critical",
                notes="雨夹雪伴随低能见度和低云底高"
            ),
            
            # BOUNDARY_014: 夜间辐射雾
            TestCase(
                test_id="BOUNDARY_014",
                description="夜间辐射雾边界测试",
                test_type=TestType.BOUNDARY_WEATHER,
                category=WeatherCategory.WEATHER,
                raw_metar="ZBAA 100200Z 00000KT 0500 FG VV001 05/05 Q1020 NOSIG",
                raw_taf="TAF ZBAA 100100Z 1002/1006 00000KT 0500 FG VV001 TEMPO 1003/1006 0200 FG VV001",
                expected_results={
                    "visibility": {
                        "value": 500,
                        "unit": "meters",
                        "boundary_flag": True,
                        "critical_threshold": 1600
                    },
                    "ceiling": {
                        "height": 100,
                        "unit": "feet",
                        "boundary_flag": True,
                        "critical_threshold": 1000
                    },
                    "weather_phenomena": ["FG"],
                    "is_boundary_weather": True,
                    "risk_level": "critical"
                },
                severity="critical",
                notes="极端夜间辐射雾"
            )
        ]
        
        return cases
    
    def generate_normal_weather_cases(self) -> List[TestCase]:
        """生成正常天气测试案例"""
        
        cases = [
            # NORMAL_001: CAVOK天气
            TestCase(
                test_id="NORMAL_001",
                description="正常天气 - CAVOK",
                test_type=TestType.NORMAL_WEATHER,
                category=WeatherCategory.NORMAL,
                raw_metar="ZBAA 091000Z 27008MPS CAVOK 20/08 Q1018",
                raw_taf="TAF ZBAA 090900Z 0910/1006 27008MPS CAVOK TEMPO 0912/0915 27010G15MPS",
                expected_results={
                    "visibility": {
                        "value": 10000,
                        "unit": "meters",
                        "boundary_flag": False
                    },
                    "ceiling": {
                        "height": 5000,
                        "unit": "feet",
                        "boundary_flag": False
                    },
                    "wind": {
                        "speed": 8,
                        "gust": 15,
                        "unit": "m/s",
                        "boundary_flag": False
                    },
                    "is_boundary_weather": False,
                    "risk_level": "normal"
                },
                severity="normal",
                notes="理想飞行天气"
            ),
            
            # NORMAL_002: 正常能见度
            TestCase(
                test_id="NORMAL_002",
                description="正常天气 - 能见度良好",
                test_type=TestType.NORMAL_WEATHER,
                category=WeatherCategory.NORMAL,
                raw_metar="ZBAA 091100Z 30006MPS 8000 FEW025 18/10 Q1015",
                raw_taf="TAF ZBAA 091000Z 0911/1006 30006MPS 8000 FEW025 BECMG 0914/0916 9999 SCT030",
                expected_results={
                    "visibility": {
                        "value": 8000,
                        "unit": "meters",
                        "boundary_flag": False
                    },
                    "ceiling": {
                        "height": 2500,
                        "unit": "feet",
                        "boundary_flag": False
                    },
                    "is_boundary_weather": False,
                    "risk_level": "normal"
                },
                severity="normal",
                notes="能见度良好"
            ),
            
            # NORMAL_003: 正常风速
            TestCase(
                test_id="NORMAL_003",
                description="正常天气 - 风速在标准范围内",
                test_type=TestType.NORMAL_WEATHER,
                category=WeatherCategory.NORMAL,
                raw_metar="ZBAA 090800Z 24010MPS 9999 BKN030 16/09 Q1012",
                raw_taf="TAF ZBAA 090700Z 0908/1006 24010MPS 9999 BKN030 TEMPO 0910/0913 24012G18MPS",
                expected_results={
                    "visibility": {
                        "value": 10000,
                        "unit": "meters",
                        "boundary_flag": False
                    },
                    "wind": {
                        "speed": 10,
                        "gust": 18,
                        "unit": "m/s",
                        "boundary_flag": False,
                        "critical_threshold": 17
                    },
                    "is_boundary_weather": False,
                    "risk_level": "normal"
                },
                severity="normal",
                notes="风速在正常范围内"
            ),
            
            # NORMAL_004: 正常多云
            TestCase(
                test_id="NORMAL_004",
                description="正常天气 - 多云",
                test_type=TestType.NORMAL_WEATHER,
                category=WeatherCategory.NORMAL,
                raw_metar="ZBAA 090700Z 18005MPS 6000 SCT020 BKN030 14/12 Q1010",
                raw_taf="TAF ZBAA 090600Z 0907/1006 18005MPS 6000 SCT020 BKN030 TEMPO 0912/0915 8000 BKN040",
                expected_results={
                    "visibility": {
                        "value": 6000,
                        "unit": "meters",
                        "boundary_flag": False
                    },
                    "ceiling": {
                        "height": 3000,
                        "unit": "feet",
                        "boundary_flag": False
                    },
                    "is_boundary_weather": False,
                    "risk_level": "normal"
                },
                severity="normal",
                notes="多云天气，飞行条件良好"
            )
        ]
        
        return cases
    
    def generate_edge_cases(self) -> List[TestCase]:
        """生成边缘案例"""
        
        cases = [
            # EDGE_001: 缺失数据
            TestCase(
                test_id="EDGE_001",
                description="边缘案例 - METAR数据缺失字段",
                test_type=TestType.EDGE_CASE,
                category=WeatherCategory.NORMAL,
                raw_metar="ZBAA 091200Z 24008MPS 9999",
                raw_taf="TAF ZBAA 091100Z 0912/1006 24008MPS 9999",
                expected_results={
                    "visibility": {
                        "value": 10000,
                        "unit": "meters",
                        "boundary_flag": False
                    },
                    "is_boundary_weather": False,
                    "risk_level": "normal",
                    "data_completeness": "partial"
                },
                severity="normal",
                notes="数据不完整但可解析"
            ),
            
            # EDGE_002: 特殊格式 - NOSIG
            TestCase(
                test_id="EDGE_002",
                description="边缘案例 - NOSIG格式",
                test_type=TestType.EDGE_CASE,
                category=WeatherCategory.NORMAL,
                raw_metar="ZBAA 091300Z 32004MPS 9999 FEW030 15/08 Q1020 NOSIG",
                raw_taf="TAF ZBAA 091200Z 0913/1006 32004MPS 9999 FEW030",
                expected_results={
                    "visibility": {
                        "value": 10000,
                        "unit": "meters",
                        "boundary_flag": False
                    },
                    "is_boundary_weather": False,
                    "risk_level": "normal",
                    "trend": "NOSIG"
                },
                severity="normal",
                notes="无显著变化趋势"
            )
        ]
        
        return cases
    
    def generate_golden_set(self) -> List[TestCase]:
        """生成完整的Golden Set"""
        
        all_cases = []
        all_cases.extend(self.generate_boundary_weather_cases())
        all_cases.extend(self.generate_normal_weather_cases())
        all_cases.extend(self.generate_edge_cases())
        
        self.test_cases = all_cases
        return all_cases
    
    def get_test_case_by_id(self, test_id: str) -> Optional[TestCase]:
        """根据ID获取测试案例"""
        for case in self.test_cases:
            if case.test_id == test_id:
                return case
        return None
    
    def get_cases_by_type(self, test_type: TestType) -> List[TestCase]:
        """根据测试类型获取案例"""
        return [case for case in self.test_cases if case.test_type == test_type]
    
    def get_cases_by_category(self, category: WeatherCategory) -> List[TestCase]:
        """根据天气类别获取案例"""
        return [case for case in self.test_cases if case.category == category]
    
    def export_to_json(self, filepath: str):
        """导出Golden Set为JSON格式"""
        import json
        
        data = []
        for case in self.test_cases:
            case_dict = {
                "test_id": case.test_id,
                "description": case.description,
                "test_type": case.test_type.value,
                "category": case.category.value,
                "raw_metar": case.raw_metar,
                "raw_taf": case.raw_taf,
                "expected_results": case.expected_results,
                "severity": case.severity,
                "notes": case.notes
            }
            data.append(case_dict)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取Golden Set统计信息"""
        stats = {
            "total_cases": len(self.test_cases),
            "by_type": {},
            "by_category": {},
            "by_severity": {}
        }
        
        for case in self.test_cases:
            # 按类型统计
            type_name = case.test_type.value
            stats["by_type"][type_name] = stats["by_type"].get(type_name, 0) + 1
            
            # 按类别统计
            category_name = case.category.value
            stats["by_category"][category_name] = stats["by_category"].get(category_name, 0) + 1
            
            # 按严重程度统计
            severity_name = case.severity
            stats["by_severity"][severity_name] = stats["by_severity"].get(severity_name, 0) + 1
        
        return stats


def main():
    """主函数 - 生成并导出Golden Set"""
    
    print("=" * 60)
    print("航空天气AI系统 - Golden Set生成器")
    print("=" * 60)
    
    # 创建生成器实例
    generator = GoldenSetGenerator()
    
    # 生成Golden Set
    test_cases = generator.generate_golden_set()
    
    # 打印统计信息
    stats = generator.get_statistics()
    print(f"\n✅ Golden Set生成完成！")
    print(f"总计测试案例: {stats['total_cases']}个\n")
    
    print("按测试类型分布:")
    for test_type, count in stats['by_type'].items():
        print(f"  - {test_type}: {count}个")
    
    print("\n按天气类别分布:")
    for category, count in stats['by_category'].items():
        print(f"  - {category}: {count}个")
    
    print("\n按严重程度分布:")
    for severity, count in stats['by_severity'].items():
        print(f"  - {severity}: {count}个")
    
    # 导出为JSON
    output_path = "/mnt/user-data/workspace/aviation-weather-ai/evaluation/golden_set.json"
    generator.export_to_json(output_path)
    print(f"\n📁 Golden Set已导出至: {output_path}")
    
    # 打印示例案例
    print("\n" + "=" * 60)
    print("示例案例展示:")
    print("=" * 60)
    
    # 展示第一个边界天气案例
    boundary_case = generator.get_test_case_by_id("BOUNDARY_001")
    if boundary_case:
        print(f"\n【{boundary_case.test_id}】{boundary_case.description}")
        print(f"类型: {boundary_case.test_type.value} | 类别: {boundary_case.category.value}")
        print(f"严重程度: {boundary_case.severity}")
        print(f"METAR: {boundary_case.raw_metar}")
        print(f"TAF: {boundary_case.raw_taf}")
        print(f"预期结果: {boundary_case.expected_results}")
        if boundary_case.notes:
            print(f"备注: {boundary_case.notes}")
    
    print("\n" + "=" * 60)
    print("✅ Golden Set生成器运行完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()