"""
航空术语多语言支持 - 中英对照和翻译功能
"""
from typing import Dict, Optional, List
import re


class AviationTerminology:
    """航空术语类"""
    
    # 天气现象术语
    WEATHER_PHENOMENA = {
        "TS": {"cn": "雷暴", "en": "Thunderstorm"},
        "FG": {"cn": "雾", "en": "Fog"},
        "BR": {"cn": "薄雾", "en": "Mist"},
        "HZ": {"cn": "霾", "en": "Haze"},
        "DU": {"cn": "浮尘", "en": "Dust"},
        "SA": {"cn": "沙", "en": "Sand"},
        "FU": {"cn": "烟", "en": "Smoke"},
        "VA": {"cn": "火山灰", "en": "Volcanic Ash"},
        "SQ": {"cn": "飑", "en": "Squall"},
        "FC": {"cn": "龙卷", "en": "Funnel Cloud"},
        "SS": {"cn": "沙暴", "en": "Sandstorm"},
        "DS": {"cn": "尘暴", "en": "Duststorm"},
        "PO": {"cn": "尘卷", "en": "Dust Whirl"},
        "UP": {"cn": "未知降水", "en": "Unknown Precipitation"},
    }
    
    # 飞行规则术语
    FLIGHT_RULES = {
        "VFR": {"cn": "目视飞行规则", "en": "Visual Flight Rules"},
        "MVFR": {"cn": "边缘目视飞行规则", "en": "Marginal Visual Flight Rules"},
        "IFR": {"cn": "仪表飞行规则", "en": "Instrument Flight Rules"},
        "LIFR": {"cn": "低仪表飞行规则", "en": "Low Instrument Flight Rules"},
    }
    
    # 风相关术语
    WIND_TERMS = {
        "wind_direction": {"cn": "风向", "en": "Wind Direction"},
        "wind_speed": {"cn": "风速", "en": "Wind Speed"},
        "gust": {"cn": "阵风", "en": "Gust"},
        "variable_wind": {"cn": "风向不定", "en": "Variable Wind"},
        "calm": {"cn": "静风", "en": "Calm"},
        "knots": {"cn": "节", "en": "Knots"},
        "meters_per_second": {"cn": "米/秒", "en": "Meters per Second"},
    }
    
    # 云量术语
    CLOUD_AMOUNTS = {
        "SKC": {"cn": "晴空", "en": "Sky Clear"},
        "CLR": {"cn": "晴空", "en": "Clear"},
        "NSC": {"cn": "无显著云", "en": "No Significant Cloud"},
        "FEW": {"cn": "稀云", "en": "Few"},
        "SCT": {"cn": "散云", "en": "Scattered"},
        "BKN": {"cn": "裂云", "en": "Broken"},
        "OVC": {"cn": "阴天", "en": "Overcast"},
        "VV": {"cn": "垂直能见度", "en": "Vertical Visibility"},
    }
    
    # 云类型术语
    CLOUD_TYPES = {
        "CU": {"cn": "积云", "en": "Cumulus"},
        "CB": {"cn": "积雨云", "en": "Cumulonimbus"},
        "TCU": {"cn": "浓积云", "en": "Towering Cumulus"},
        "CI": {"cn": "卷云", "en": "Cirrus"},
        "CC": {"cn": "卷积云", "en": "Cirrocumulus"},
        "CS": {"cn": "卷层云", "en": "Cirrostratus"},
        "AC": {"cn": "高积云", "en": "Altocumulus"},
        "AS": {"cn": "高层云", "en": "Altostratus"},
        "ST": {"cn": "层云", "en": "Stratus"},
        "SC": {"cn": "层积云", "en": "Stratocumulus"},
        "NS": {"cn": "雨层云", "en": "Nimbostratus"},
    }
    
    # 能见度术语
    VISIBILITY_TERMS = {
        "prevailing_visibility": {"cn": "主导能见度", "en": "Prevailing Visibility"},
        "minimum_visibility": {"cn": "最小能见度", "en": "Minimum Visibility"},
        "variable_visibility": {"cn": "能见度变化", "en": "Variable Visibility"},
        "meters": {"cn": "米", "en": "Meters"},
        "kilometers": {"cn": "公里", "en": "Kilometers"},
        "statute_miles": {"cn": "法定英里", "en": "Statute Miles"},
    }
    
    # 进近术语
    APPROACH_TERMS = {
        "decision_height": {"cn": "决断高", "en": "Decision Height (DH)"},
        "minimum_descent_altitude": {"cn": "最低下降高", "en": "Minimum Descent Altitude (MDA)"},
        "instrument_landing_system": {"cn": "仪表着陆系统", "en": "Instrument Landing System (ILS)"},
        "localizer": {"cn": "航向台", "en": "Localizer"},
        "glideslope": {"cn": "下滑道", "en": "Glideslope"},
        "approach_lighting": {"cn": "进近灯光", "en": "Approach Lighting"},
        "runway_visual_range": {"cn": "跑道视程", "en": "Runway Visual Range (RVR)"},
    }
    
    # 温度术语
    TEMPERATURE_TERMS = {
        "temperature": {"cn": "温度", "en": "Temperature"},
        "dewpoint": {"cn": "露点", "en": "Dewpoint"},
        "dewpoint_depression": {"cn": "温度露点差", "en": "Dewpoint Depression"},
        "freezing": {"cn": "冰点", "en": "Freezing"},
        "below_freezing": {"cn": "零下", "en": "Below Freezing"},
    }
    
    # 压力术语
    PRESSURE_TERMS = {
        "qnh": {"cn": "修正海平面气压", "en": "QNH"},
        "qfe": {"cn": "场面气压", "en": "QFE"},
        "altimeter_setting": {"cn": "高度表设定", "en": "Altimeter Setting"},
        "hectopascals": {"cn": "百帕", "en": "Hectopascals (hPa)"},
        "inches_of_mercury": {"cn": "英寸汞柱", "en": "Inches of Mercury (inHg)"},
    }
    
    # 组合所有术语
    ALL_TERMS = {}
    ALL_TERMS.update(WEATHER_PHENOMENA)
    ALL_TERMS.update(FLIGHT_RULES)
    ALL_TERMS.update(WIND_TERMS)
    ALL_TERMS.update(CLOUD_AMOUNTS)
    ALL_TERMS.update(CLOUD_TYPES)
    ALL_TERMS.update(VISIBILITY_TERMS)
    ALL_TERMS.update(APPROACH_TERMS)
    ALL_TERMS.update(TEMPERATURE_TERMS)
    ALL_TERMS.update(PRESSURE_TERMS)


def get_term_cn(term_en: str) -> str:
    """
    获取英文术语的中文翻译
    
    Args:
        term_en: 英文术语
        
    Returns:
        中文翻译，如果未找到则返回原术语
    """
    term_en_upper = term_en.upper()
    for term_code, translations in AviationTerminology.ALL_TERMS.items():
        if term_en_upper == term_code or term_en_upper == translations["en"].upper():
            return translations["cn"]
    return term_en


def get_term_en(term_cn: str) -> str:
    """
    获取中文术语的英文翻译
    
    Args:
        term_cn: 中文术语
        
    Returns:
        英文翻译，如果未找到则返回原术语
    """
    for term_code, translations in AviationTerminology.ALL_TERMS.items():
        if term_cn == translations["cn"]:
            return translations["en"]
    return term_cn


def format_bilingual(cn: str, en: str) -> str:
    """
    格式化双语显示
    
    Args:
        cn: 中文术语
        en: 英文术语
        
    Returns:
        格式化的双语字符串 "中文 (English)"
    """
    return f"{cn} ({en})"


def translate_report(report_text: str, target_lang: str = "cn") -> str:
    """
    翻译报告文本（简单字符串替换）
    
    Args:
        report_text: 原始报告文本
        target_lang: 目标语言 ("cn" 或 "en")
        
    Returns:
        翻译后的文本
    """
    if target_lang not in ["cn", "en"]:
        raise ValueError("目标语言必须是 'cn' 或 'en'")
    
    translated_text = report_text
    
    if target_lang == "cn":
        # 英文转中文
        for term_code, translations in AviationTerminology.ALL_TERMS.items():
            # 替换英文术语为中文
            pattern = r'\b' + re.escape(translations["en"]) + r'\b'
            translated_text = re.sub(pattern, translations["cn"], translated_text, flags=re.IGNORECASE)
            # 替换代码为中文
            pattern = r'\b' + re.escape(term_code) + r'\b'
            translated_text = re.sub(pattern, translations["cn"], translated_text, flags=re.IGNORECASE)
    else:
        # 中文转英文
        for term_code, translations in AviationTerminology.ALL_TERMS.items():
            # 替换中文术语为英文
            pattern = r'\b' + re.escape(translations["cn"]) + r'\b'
            translated_text = re.sub(pattern, translations["en"], translated_text)
    
    return translated_text


def get_terminology_dict(category: Optional[str] = None) -> Dict:
    """
    获取术语字典
    
    Args:
        category: 类别名称 (可选)
        
    Returns:
        术语字典
    """
    if category is None:
        return AviationTerminology.ALL_TERMS
    
    category_map = {
        "weather": AviationTerminology.WEATHER_PHENOMENA,
        "flight_rules": AviationTerminology.FLIGHT_RULES,
        "wind": AviationTerminology.WIND_TERMS,
        "cloud_amounts": AviationTerminology.CLOUD_AMOUNTS,
        "cloud_types": AviationTerminology.CLOUD_TYPES,
        "visibility": AviationTerminology.VISIBILITY_TERMS,
        "approach": AviationTerminology.APPROACH_TERMS,
        "temperature": AviationTerminology.TEMPERATURE_TERMS,
        "pressure": AviationTerminology.PRESSURE_TERMS,
    }
    
    return category_map.get(category, AviationTerminology.ALL_TERMS)


def search_terms(query: str, lang: str = "both") -> List[Dict]:
    """
    搜索术语
    
    Args:
        query: 搜索词
        lang: 搜索语言 ("cn", "en", "both")
        
    Returns:
        匹配的术语列表
    """
    results = []
    query_lower = query.lower()
    
    for term_code, translations in AviationTerminology.ALL_TERMS.items():
        match = False
        
        if lang in ["cn", "both"]:
            if query_lower in translations["cn"].lower():
                match = True
        
        if lang in ["en", "both"]:
            if query_lower in translations["en"].lower():
                match = True
        
        if query_lower in term_code.lower():
            match = True
        
        if match:
            results.append({
                "code": term_code,
                "cn": translations["cn"],
                "en": translations["en"],
                "bilingual": format_bilingual(translations["cn"], translations["en"])
            })
    
    return results