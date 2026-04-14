"""
METAR报文获取服务
从aviationweather.gov JSON API获取实时METAR数据
"""
import httpx
import logging
from typing import Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# NOAA aviationweather.gov JSON API
METAR_API_URL = "https://aviationweather.gov/api/data/metar"
TAF_API_URL = "https://aviationweather.gov/api/data/taf"

# 支持的江浙沪机场ICAO列表
SUPPORTED_AIRPORTS = [
    "ZSPD",  # 上海浦东
    "ZSSS",  # 上海虹桥
    "ZSNJ",  # 南京禄口
    "ZSHC",  # 杭州萧山
    "ZSNB",  # 宁波栎社
    "ZSWZ",  # 温州龙湾
    "ZSLY",  # 连云港白塔阜
]


class MetarFetchError(Exception):
    """METAR获取错误"""
    pass


async def fetch_metar_for_airport(icao_code: str) -> tuple[str, dict]:
    """
    获取指定机场的实时METAR报文
    
    Args:
        icao_code: 机场ICAO代码（4位大写字母）
        
    Returns:
        tuple: (metar_raw: 原始METAR报文字符串, metadata: 元数据字典)
        
    Raises:
        MetarFetchError: 获取失败
    """
    icao_code = icao_code.upper()
    
    if len(icao_code) != 4:
        raise MetarFetchError(f"无效的ICAO代码: {icao_code}（必须为4位）")
    
    # 构建请求参数
    params = {
        "ids": icao_code,
        "format": "json",
        "taf": "false",  # 不包含TAF
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            logger.info(f"Fetching METAR for {icao_code} from aviationweather.gov")
            response = await client.get(METAR_API_URL, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            # 检查返回数据
            if not data:
                raise MetarFetchError(f"未找到机场 {icao_code} 的METAR数据")
            
            # aviationweather.gov返回的是数组
            if isinstance(data, list) and len(data) > 0:
                metar_data = data[0]
                metar_raw = metar_data.get("rawOb", "")
                
                if not metar_raw:
                    raise MetarFetchError(f"METAR数据格式错误：缺少rawOb字段")
                
                # 提取元数据
                metadata = {
                    "icao": icao_code,
                    "fetch_time": datetime.now(timezone.utc).isoformat(),
                    "observation_time": metar_data.get("reportTime", ""),
                    "station_name": metar_data.get("name", ""),
                    "latitude": metar_data.get("lat"),
                    "longitude": metar_data.get("lon"),
                    "temperature": metar_data.get("temp"),
                    "dewpoint": metar_data.get("dewp"),
                    "wind_direction": metar_data.get("wdir"),
                    "wind_speed": metar_data.get("wspd"),
                    "visibility": metar_data.get("visib"),
                    "altimeter": metar_data.get("altim"),
                    "flight_category": metar_data.get("flightCats", [{}])[0].get("text", "UNKNOWN") if metar_data.get("flightCats") else "UNKNOWN",
                }
                
                logger.info(f"Successfully fetched METAR for {icao_code}: {metar_raw[:50]}...")
                return metar_raw, metadata
                
            else:
                raise MetarFetchError(f"METAR数据格式错误：{type(data)}")
                
    except httpx.TimeoutException:
        logger.error(f"Timeout fetching METAR for {icao_code}")
        raise MetarFetchError(f"获取 {icao_code} METAR超时，请稍后重试")
        
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error fetching METAR for {icao_code}: {e}")
        raise MetarFetchError(f"获取 {icao_code} METAR失败: HTTP {e.response.status_code}")
        
    except Exception as e:
        logger.error(f"Unexpected error fetching METAR for {icao_code}: {e}", exc_info=True)
        raise MetarFetchError(f"获取 {icao_code} METAR时发生错误: {str(e)}")


async def fetch_taf_for_airport(icao_code: str) -> tuple[str, dict]:
    """
    获取指定机场的TAF预报报文

    Args:
        icao_code: 机场ICAO代码（4位大写字母）

    Returns:
        tuple: (taf_raw: 原始TAF报文字符串, metadata: 元数据字典)

    Raises:
        MetarFetchError: 获取失败
    """
    icao_code = icao_code.upper()

    if len(icao_code) != 4:
        raise MetarFetchError(f"无效的ICAO代码: {icao_code}（必须为4位）")

    params = {
        "ids": icao_code,
        "format": "json",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            logger.info(f"Fetching TAF for {icao_code} from aviationweather.gov")
            response = await client.get(TAF_API_URL, params=params)
            response.raise_for_status()

            data = response.json()

            if not data:
                raise MetarFetchError(f"未找到机场 {icao_code} 的TAF数据")

            if isinstance(data, list) and len(data) > 0:
                taf_data = data[0]
                taf_raw = taf_data.get("rawTAF", "")

                if not taf_raw:
                    raise MetarFetchError(f"TAF数据格式错误：缺少rawTAF字段")

                metadata = {
                    "icao": icao_code,
                    "fetch_time": datetime.now(timezone.utc).isoformat(),
                    "issue_time": taf_data.get("issueTime", ""),
                    "valid_from": taf_data.get("validTimeFrom", ""),
                    "valid_to": taf_data.get("validTimeTo", ""),
                    "station_name": taf_data.get("name", ""),
                    "latitude": taf_data.get("lat"),
                    "longitude": taf_data.get("lon"),
                    # 提取预报时段
                    "forecasts": [
                        {
                            "period": fc.get("fcstTimeFrom", "") + " - " + fc.get("fcstTimeTo", ""),
                            "wind_direction": fc.get("wdir"),
                            "wind_speed": fc.get("wspd"),
                            "visibility": fc.get("visib"),
                            "weather": fc.get("wxString", ""),
                            "clouds": [
                                {
                                    "cover": c.get("cover", ""),
                                    "base": c.get("base"),
                                    "type": c.get("type", ""),
                                }
                                for c in fc.get("clouds", [])
                            ],
                        }
                        for fc in taf_data.get("fcsts", [])
                    ],
                }

                logger.info(f"Successfully fetched TAF for {icao_code}: {taf_raw[:50]}...")
                return taf_raw, metadata

            else:
                raise MetarFetchError(f"TAF数据格式错误：{type(data)}")

    except httpx.TimeoutException:
        logger.error(f"Timeout fetching TAF for {icao_code}")
        raise MetarFetchError(f"获取 {icao_code} TAF超时，请稍后重试")

    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error fetching TAF for {icao_code}: {e}")
        raise MetarFetchError(f"获取 {icao_code} TAF失败: HTTP {e.response.status_code}")

    except Exception as e:
        logger.error(f"Unexpected error fetching TAF for {icao_code}: {e}", exc_info=True)
        raise MetarFetchError(f"获取 {icao_code} TAF时发生错误: {str(e)}")


def is_airport_supported(icao_code: str) -> bool:
    """检查机场是否在支持列表中"""
    return icao_code.upper() in SUPPORTED_AIRPORTS


__all__ = [
    "fetch_metar_for_airport",
    "fetch_taf_for_airport",
    "MetarFetchError",
    "SUPPORTED_AIRPORTS",
    "is_airport_supported",
]
