"""
江浙沪地区机场数据配置
包含ICAO代码、中文名称、城市、经纬度等信息
"""

from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class Airport:
    """机场数据模型"""
    icao: str           # ICAO代码（如 ZSPD）
    iata: str           # IATA代码（如 PVG）
    name_cn: str        # 中文名称
    name_en: str        # 英文名称
    city_cn: str        # 所在城市（中文）
    city_en: str        # 所在城市（英文）
    latitude: float     # 纬度
    longitude: float    # 经度
    elevation: int      # 海拔（米）
    is_major: bool      # 是否为主要机场
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "icao": self.icao,
            "iata": self.iata,
            "name_cn": self.name_cn,
            "name_en": self.name_en,
            "city_cn": self.city_cn,
            "city_en": self.city_en,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "elevation": self.elevation,
            "is_major": self.is_major
        }


# 江浙沪地区机场列表
JANGSU_ZHEJIANG_SHANGHAI_AIRPORTS: List[Airport] = [
    # ========== 上海市 ==========
    Airport(
        icao="ZSPD",
        iata="PVG",
        name_cn="上海浦东国际机场",
        name_en="Shanghai Pudong International Airport",
        city_cn="上海",
        city_en="Shanghai",
        latitude=31.1443,
        longitude=121.8083,
        elevation=4,
        is_major=True
    ),
    Airport(
        icao="ZSSS",
        iata="SHA",
        name_cn="上海虹桥国际机场",
        name_en="Shanghai Hongqiao International Airport",
        city_cn="上海",
        city_en="Shanghai",
        latitude=31.1979,
        longitude=121.3363,
        elevation=3,
        is_major=True
    ),
    
    # ========== 浙江省 ==========
    Airport(
        icao="ZSHC",
        iata="HGH",
        name_cn="杭州萧山国际机场",
        name_en="Hangzhou Xiaoshan International Airport",
        city_cn="杭州",
        city_en="Hangzhou",
        latitude=30.2295,
        longitude=120.4344,
        elevation=7,
        is_major=True
    ),
    Airport(
        icao="ZSNB",
        iata="NGB",
        name_cn="宁波栎社国际机场",
        name_en="Ningbo Lishe International Airport",
        city_cn="宁波",
        city_en="Ningbo",
        latitude=29.8267,
        longitude=121.4586,
        elevation=4,
        is_major=False
    ),
    Airport(
        icao="ZSWZ",
        iata="WNZ",
        name_cn="温州龙湾国际机场",
        name_en="Wenzhou Longwan International Airport",
        city_cn="温州",
        city_en="Wenzhou",
        latitude=27.9922,
        longitude=120.6436,
        elevation=4,
        is_major=False
    ),
    Airport(
        icao="ZSYW",
        iata="YIW",
        name_cn="义乌机场",
        name_en="Yiwu Airport",
        city_cn="义乌",
        city_en="Yiwu",
        latitude=29.3456,
        longitude=120.0331,
        elevation=83,
        is_major=False
    ),
    Airport(
        icao="ZSHZ",
        iata="HYN",
        name_cn="台州路桥机场",
        name_en="Taizhou Luqiao Airport",
        city_cn="台州",
        city_en="Taizhou",
        latitude=28.5656,
        longitude=121.4289,
        elevation=3,
        is_major=False
    ),
    Airport(
        icao="ZSOS",
        iata="HSN",
        name_cn="舟山普陀山机场",
        name_en="Zhoushan Putuoshan Airport",
        city_cn="舟山",
        city_en="Zhoushan",
        latitude=29.9381,
        longitude=122.3592,
        elevation=2,
        is_major=False
    ),
    Airport(
        icao="ZSJU",
        iata="JUZ",
        name_cn="衢州机场",
        name_en="Quzhou Airport",
        city_cn="衢州",
        city_en="Quzhou",
        latitude=28.9658,
        longitude=118.8997,
        elevation=50,
        is_major=False
    ),
    Airport(
        icao="ZSLG",
        iata="LNJ",
        name_cn="丽水机场",
        name_en="Lishui Airport",
        city_cn="丽水",
        city_en="Lishui",
        latitude=28.4563,
        longitude=119.9142,
        elevation=150,
        is_major=False
    ),
    
    # ========== 江苏省 ==========
    Airport(
        icao="ZSNJ",
        iata="NKG",
        name_cn="南京禄口国际机场",
        name_en="Nanjing Lukou International Airport",
        city_cn="南京",
        city_en="Nanjing",
        latitude=31.7420,
        longitude=118.8622,
        elevation=15,
        is_major=True
    ),
    Airport(
        icao="ZSWX",
        iata="WUX",
        name_cn="无锡硕放机场",
        name_en="Wuxi Shuofang International Airport",
        city_cn="无锡",
        city_en="Wuxi",
        latitude=31.7422,
        longitude=120.4339,
        elevation=5,
        is_major=False
    ),
    Airport(
        icao="ZSSZ",
        iata="SZV",
        name_cn="苏州工业园区直升机场",
        name_en="Suzhou Industrial Park Heliport",
        city_cn="苏州",
        city_en="Suzhou",
        latitude=31.3228,
        longitude=120.7150,
        elevation=0,
        is_major=False
    ),
    Airport(
        icao="ZSCG",
        iata="CZX",
        name_cn="常州奔牛国际机场",
        name_en="Changzhou Benniu International Airport",
        city_cn="常州",
        city_en="Changzhou",
        latitude=31.9050,
        longitude=119.7806,
        elevation=7,
        is_major=False
    ),
    Airport(
        icao="ZSYT",
        iata="YTY",
        name_cn="扬州泰州国际机场",
        name_en="Yangzhou Taizhou International Airport",
        city_cn="扬州/泰州",
        city_en="Yangzhou/Taizhou",
        latitude=32.0617,
        longitude=119.7050,
        elevation=3,
        is_major=False
    ),
    Airport(
        icao="ZSNJ",
        iata="NTG",
        name_cn="南通兴东国际机场",
        name_en="Nantong Xingdong International Airport",
        city_cn="南通",
        city_en="Nantong",
        latitude=32.0708,
        longitude=120.0994,
        elevation=5,
        is_major=False
    ),
    Airport(
        icao="ZSLY",
        iata="LYG",
        name_cn="连云港白塔埠机场",
        name_en="Lianyungang Baitabu Airport",
        city_cn="连云港",
        city_en="Lianyungang",
        latitude=34.5311,
        longitude=119.1783,
        elevation=5,
        is_major=False
    ),
    Airport(
        icao="ZSXZ",
        iata="XUZ",
        name_cn="徐州观音国际机场",
        name_en="Xuzhou Guanyin International Airport",
        city_cn="徐州",
        city_en="Xuzhou",
        latitude=34.0542,
        longitude=117.5553,
        elevation=37,
        is_major=False
    ),
    Airport(
        icao="ZSYC",
        iata="YNZ",
        name_cn="盐城南洋国际机场",
        name_en="Yancheng Nanyang International Airport",
        city_cn="盐城",
        city_en="Yancheng",
        latitude=33.4486,
        longitude=120.2208,
        elevation=3,
        is_major=False
    ),
    Airport(
        icao="ZSHZ",
        iata="HZH",
        name_cn="淮安涟水国际机场",
        name_en="Huai'an Lianshui International Airport",
        city_cn="淮安",
        city_en="Huai'an",
        latitude=33.7817,
        longitude=119.1656,
        elevation=8,
        is_major=False
    ),
]


def get_airport_by_icao(icao: str) -> Optional[Airport]:
    """根据ICAO代码获取机场信息"""
    for airport in JANGSU_ZHEJIANG_SHANGHAI_AIRPORTS:
        if airport.icao.upper() == icao.upper():
            return airport
    return None


def get_airport_by_iata(iata: str) -> Optional[Airport]:
    """根据IATA代码获取机场信息"""
    for airport in JANGSU_ZHEJIANG_SHANGHAI_AIRPORTS:
        if airport.iata.upper() == iata.upper():
            return airport
    return None


def get_major_airports() -> List[Airport]:
    """获取主要机场列表"""
    return [a for a in JANGSU_ZHEJIANG_SHANGHAI_AIRPORTS if a.is_major]


def get_airports_by_city(city: str) -> List[Airport]:
    """根据城市获取机场列表"""
    return [
        a for a in JANGSU_ZHEJIANG_SHANGHAI_AIRPORTS 
        if city.lower() in a.city_cn.lower() or city.lower() in a.city_en.lower()
    ]


def get_airport_list_for_dropdown() -> List[Dict]:
    """
    获取下拉框使用的机场列表
    
    Returns:
        [{"value": "ZSPD", "label": "上海浦东国际机场 (ZSPD/PVG)"}, ...]
    """
    # 按城市和重要性排序
    sorted_airports = sorted(
        JANGSU_ZHEJIANG_SHANGHAI_AIRPORTS,
        key=lambda a: (not a.is_major, a.city_cn, a.name_cn)
    )
    
    return [
        {
            "value": airport.icao,
            "label": f"{airport.name_cn} ({airport.icao}/{airport.iata})",
            "city": airport.city_cn,
            "is_major": airport.is_major
        }
        for airport in sorted_airports
    ]


def get_airport_options_grouped_by_city() -> Dict[str, List[Dict]]:
    """
    获取按城市分组的机场选项（用于前端下拉框）
    
    Returns:
        {
            "上海": [{"value": "ZSPD", "label": "浦东机场"}, ...],
            "杭州": [{"value": "ZSHC", "label": "萧山机场"}],
            ...
        }
    """
    grouped = {}
    for airport in JANGSU_ZHEJIANG_SHANGHAI_AIRPORTS:
        if airport.city_cn not in grouped:
            grouped[airport.city_cn] = []
        grouped[airport.city_cn].append({
            "value": airport.icao,
            "label": airport.name_cn.replace(airport.city_cn, "").replace("国际机场", "").replace("机场", "").strip(),
            "iata": airport.iata,
            "is_major": airport.is_major
        })
    
    # 每个城市内按重要性排序
    for city in grouped:
        grouped[city] = sorted(grouped[city], key=lambda x: not x["is_major"])
    
    return grouped


# 导出便捷常量
MAJOR_AIRPORTS = get_major_airports()
AIRPORT_DROPDOWN_OPTIONS = get_airport_list_for_dropdown()
AIRPORT_GROUPED_OPTIONS = get_airport_options_grouped_by_city()


# 测试代码
if __name__ == "__main__":
    print("江浙沪机场列表:")
    print(f"总计: {len(JANGSU_ZHEJIANG_SHANGHAI_AIRPORTS)} 个机场")
    print(f"主要机场: {len(MAJOR_AIRPORTS)} 个\n")
    
    print("主要机场:")
    for airport in MAJOR_AIRPORTS:
        print(f"  {airport.icao} ({airport.iata}) - {airport.name_cn}")
    
    print("\n按城市分组:")
    for city, airports in AIRPORT_GROUPED_OPTIONS.items():
        print(f"\n{city}:")
        for a in airports:
            print(f"  {a['value']} - {a['label']}")
