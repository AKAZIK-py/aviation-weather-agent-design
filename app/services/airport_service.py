"""
机场代码翻译服务
ICAO代码 → 中文名称映射
"""
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class AirportInfo:
    """机场信息"""
    icao_code: str
    iata_code: str
    chinese_name: str
    english_name: str
    city: str
    country: str
    elevation_ft: int
    coordinates: Tuple[float, float]  # (lat, lon)


class AirportService:
    """机场信息服务"""
    
    # 中国主要机场ICAO映射表
    AIRPORTS: Dict[str, AirportInfo] = {
        # 北京
        "ZBAA": AirportInfo(
            icao_code="ZBAA", iata_code="PEK",
            chinese_name="北京首都国际机场",
            english_name="Beijing Capital International Airport",
            city="北京", country="中国",
            elevation_ft=116, coordinates=(40.0801, 116.5846)
        ),
        "ZBAD": AirportInfo(
            icao_code="ZBAD", iata_code="PKX",
            chinese_name="北京大兴国际机场",
            english_name="Beijing Daxing International Airport",
            city="北京", country="中国",
            elevation_ft=82, coordinates=(39.5098, 116.4105)
        ),
        # 上海
        "ZSSS": AirportInfo(
            icao_code="ZSSS", iata_code="SHA",
            chinese_name="上海虹桥国际机场",
            english_name="Shanghai Hongqiao International Airport",
            city="上海", country="中国",
            elevation_ft=10, coordinates=(31.1979, 121.3363)
        ),
        "ZSPD": AirportInfo(
            icao_code="ZSPD", iata_code="PVG",
            chinese_name="上海浦东国际机场",
            english_name="Shanghai Pudong International Airport",
            city="上海", country="中国",
            elevation_ft=13, coordinates=(31.1443, 121.8083)
        ),
        # 广州/深圳
        "ZGGG": AirportInfo(
            icao_code="ZGGG", iata_code="CAN",
            chinese_name="广州白云国际机场",
            english_name="Guangzhou Baiyun International Airport",
            city="广州", country="中国",
            elevation_ft=50, coordinates=(23.3924, 113.2988)
        ),
        "ZGSZ": AirportInfo(
            icao_code="ZGSZ", iata_code="SZX",
            chinese_name="深圳宝安国际机场",
            english_name="Shenzhen Bao'an International Airport",
            city="深圳", country="中国",
            elevation_ft=13, coordinates=(22.6393, 113.8107)
        ),
        # 成都/重庆
        "ZUUU": AirportInfo(
            icao_code="ZUUU", iata_code="CTU",
            chinese_name="成都双流国际机场",
            english_name="Chengdu Shuangliu International Airport",
            city="成都", country="中国",
            elevation_ft=1615, coordinates=(30.5785, 103.9471)
        ),
        "ZUCK": AirportInfo(
            icao_code="ZUCK", iata_code="CKG",
            chinese_name="重庆江北国际机场",
            english_name="Chongqing Jiangbei International Airport",
            city="重庆", country="中国",
            elevation_ft=1365, coordinates=(29.7192, 106.6417)
        ),
        # 西安/武汉/昆明
        "ZLXY": AirportInfo(
            icao_code="ZLXY", iata_code="XIY",
            chinese_name="西安咸阳国际机场",
            english_name="Xi'an Xianyang International Airport",
            city="西安", country="中国",
            elevation_ft=1579, coordinates=(34.4471, 108.7516)
        ),
        "ZHHH": AirportInfo(
            icao_code="ZHHH", iata_code="WUH",
            chinese_name="武汉天河国际机场",
            english_name="Wuhan Tianhe International Airport",
            city="武汉", country="中国",
            elevation_ft=112, coordinates=(30.7838, 113.8964)
        ),
        "ZPPP": AirportInfo(
            icao_code="ZPPP", iata_code="KMG",
            chinese_name="昆明长水国际机场",
            english_name="Kunming Changshui International Airport",
            city="昆明", country="中国",
            elevation_ft=6986, coordinates=(25.1019, 102.9290)
        ),
        # 杭州/南京/厦门
        "ZSHC": AirportInfo(
            icao_code="ZSHC", iata_code="HGH",
            chinese_name="杭州萧山国际机场",
            english_name="Hangzhou Xiaoshan International Airport",
            city="杭州", country="中国",
            elevation_ft=23, coordinates=(30.2295, 120.4343)
        ),
        "ZSNJ": AirportInfo(
            icao_code="ZSNJ", iata_code="NKG",
            chinese_name="南京禄口国际机场",
            english_name="Nanjing Lukou International Airport",
            city="南京", country="中国",
            elevation_ft=49, coordinates=(31.7420, 118.8620)
        ),
        "ZSSS": AirportInfo(
            icao_code="ZSAM", iata_code="XMN",
            chinese_name="厦门高崎国际机场",
            english_name="Xiamen Gaoqi International Airport",
            city="厦门", country="中国",
            elevation_ft=59, coordinates=(24.5440, 118.1277)
        ),
        # 香港/台北
        "VHHH": AirportInfo(
            icao_code="VHHH", iata_code="HKG",
            chinese_name="香港国际机场",
            english_name="Hong Kong International Airport",
            city="香港", country="中国",
            elevation_ft=28, coordinates=(22.3080, 113.9185)
        ),
        "RCTP": AirportInfo(
            icao_code="RCTP", iata_code="TPE",
            chinese_name="台湾桃园国际机场",
            english_name="Taiwan Taoyuan International Airport",
            city="台北", country="中国台湾",
            elevation_ft=100, coordinates=(25.0797, 121.2342)
        ),
    }
    
    def __init__(self):
        self._icao_to_airport = self.AIRPORTS.copy()
        self._iata_to_icao: Dict[str, str] = {
            info.iata_code: icao 
            for icao, info in self.AIRPORTS.items()
        }
    
    def get_airport_info(self, icao_code: str) -> Optional[AirportInfo]:
        """根据ICAO代码获取机场信息"""
        icao = icao_code.upper().strip()
        return self._icao_to_airport.get(icao)
    
    def get_chinese_name(self, icao_code: str) -> str:
        """根据ICAO代码获取机场中文名"""
        info = self.get_airport_info(icao_code)
        if info:
            return info.chinese_name
        return f"未知机场({icao_code})"
    
    def get_city(self, icao_code: str) -> str:
        """根据ICAO代码获取城市名"""
        info = self.get_airport_info(icao_code)
        if info:
            return info.city
        return "未知城市"
    
    def iata_to_icao(self, iata_code: str) -> Optional[str]:
        """IATA代码转ICAO代码"""
        iata = iata_code.upper().strip()
        return self._iata_to_icao.get(iata)
    
    def is_valid_icao(self, icao_code: str) -> bool:
        """检查ICAO代码是否有效"""
        icao = icao_code.upper().strip()
        return icao in self._icao_to_airport
    
    def search_airports(self, keyword: str) -> List[AirportInfo]:
        """根据关键词搜索机场"""
        keyword = keyword.lower()
        results = []
        
        for info in self.AIRPORTS.values():
            if (keyword in info.chinese_name.lower() or
                keyword in info.english_name.lower() or
                keyword in info.city.lower() or
                keyword in info.icao_code.lower() or
                keyword in info.iata_code.lower()):
                results.append(info)
        
        return results
    
    def get_all_airports(self) -> List[AirportInfo]:
        """获取所有机场列表"""
        return list(self.AIRPORTS.values())
    
    def get_airports_by_city(self, city: str) -> List[AirportInfo]:
        """根据城市获取机场列表"""
        city_lower = city.lower()
        return [
            info for info in self.AIRPORTS.values()
            if city_lower in info.city.lower()
        ]


# 单例
_airport_service: Optional[AirportService] = None


def get_airport_service() -> AirportService:
    """获取机场服务单例"""
    global _airport_service
    if _airport_service is None:
        _airport_service = AirportService()
    return _airport_service


# 便捷函数
def get_airport_name(icao_code: str) -> str:
    """获取机场中文名"""
    return get_airport_service().get_chinese_name(icao_code)


def translate_icao(icao_code: str) -> Dict[str, str]:
    """翻译ICAO代码为机场信息"""
    service = get_airport_service()
    info = service.get_airport_info(icao_code)
    
    if info:
        return {
            "icao_code": info.icao_code,
            "iata_code": info.iata_code,
            "chinese_name": info.chinese_name,
            "english_name": info.english_name,
            "city": info.city,
            "country": info.country,
        }
    
    return {
        "icao_code": icao_code,
        "iata_code": "",
        "chinese_name": f"未知机场({icao_code})",
        "english_name": f"Unknown Airport ({icao_code})",
        "city": "未知",
        "country": "未知",
    }


if __name__ == "__main__":
    # 测试
    service = get_airport_service()
    
    # 测试ICAO翻译
    test_codes = ["ZBAA", "ZSPD", "ZGGG", "VHHH", "XXXX"]
    
    print("=== ICAO翻译测试 ===")
    for icao in test_codes:
        info = service.get_airport_info(icao)
        if info:
            print(f"{icao} -> {info.chinese_name} ({info.city})")
        else:
            print(f"{icao} -> 未知机场")
    
    print("\n=== 城市搜索测试 ===")
    results = service.get_airports_by_city("北京")
    for info in results:
        print(f"{info.icao_code}: {info.chinese_name}")
