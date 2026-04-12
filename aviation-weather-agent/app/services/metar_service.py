"""
METAR实时数据获取服务
支持从NOAA/aviationweather.gov获取实时METAR报文
"""
import aiohttp
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime
import re
import logging

logger = logging.getLogger(__name__)


class METARService:
    """METAR实时数据服务"""
    
    # NOAA METAR API端点（JSON格式）
    NOAA_METAR_URL = "https://aviationweather.gov/api/data/metar"
    
    # 备用API（中国气象局风格，需要API密钥时使用）
    # ALT_METAR_URL = "https://api.weather.gov/..."
    
    def __init__(self, timeout: int = 10):
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建HTTP会话"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(timeout=self.timeout)
        return self.session
    
    async def close(self):
        """关闭HTTP会话"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def fetch_metar(self, icao_code: str) -> Dict[str, Any]:
        """
        获取指定机场的最新METAR报文
        
        Args:
            icao_code: ICAO机场代码（如ZBAA, ZSPD）
            
        Returns:
            {
                "success": bool,
                "metar_raw": str,  # 原始METAR报文
                "icao_code": str,
                "observation_time": datetime,
                "source": str,  # 数据来源
                "error": str | None
            }
        """
        try:
            # 标准化ICAO代码（大写）
            icao = icao_code.upper().strip()
            
            # 尝试从NOAA获取
            result = await self._fetch_from_noaa(icao)
            
            if result["success"]:
                return result
            
            # NOAA失败，尝试备用源（如果有）
            # result = await self._fetch_from_alternate(icao)
            
            return result
            
        except Exception as e:
            logger.error(f"获取METAR失败 [{icao_code}]: {str(e)}")
            return {
                "success": False,
                "metar_raw": None,
                "icao_code": icao_code,
                "observation_time": None,
                "source": None,
                "error": str(e)
            }
    
    async def _fetch_from_noaa(self, icao: str) -> Dict[str, Any]:
        """
        从NOAA aviationweather.gov获取METAR（JSON格式）
        
        API文档: https://aviationweather.gov/data/api/
        返回格式: JSON数组，包含rawOb字段
        """
        try:
            session = await self._get_session()
            
            # NOAA API参数（JSON格式）
            params = {
                "ids": icao,  # ICAO代码
                "format": "json",  # JSON格式
            }
            
            headers = {
                "User-Agent": "DeerFlow-AviationWeather-Agent/1.0",
                "Accept": "application/json"
            }
            
            async with session.get(
                self.NOAA_METAR_URL,
                params=params,
                headers=headers
            ) as response:
                if response.status != 200:
                    return {
                        "success": False,
                        "metar_raw": None,
                        "icao_code": icao,
                        "observation_time": None,
                        "source": "NOAA",
                        "error": f"HTTP {response.status}"
                    }
                
                # 解析JSON响应
                data = await response.json()
                
                if not data or not isinstance(data, list) or len(data) == 0:
                    return {
                        "success": False,
                        "metar_raw": None,
                        "icao_code": icao,
                        "observation_time": None,
                        "source": "NOAA",
                        "error": f"未找到 {icao} 的METAR数据"
                    }
                
                # 取最新一条（第一条）
                metar_data = data[0]
                metar_raw = metar_data.get("rawOb", "")
                
                # 解析观测时间
                obs_time_str = metar_data.get("reportTime")
                if obs_time_str:
                    try:
                        obs_time = datetime.fromisoformat(obs_time_str.replace("Z", "+00:00"))
                    except:
                        obs_time = self._extract_observation_time(metar_raw)
                else:
                    obs_time = self._extract_observation_time(metar_raw)
                
                return {
                    "success": True,
                    "metar_raw": metar_raw,
                    "icao_code": icao,
                    "observation_time": obs_time,
                    "source": "NOAA/aviationweather.gov",
                    "error": None,
                    "parsed_data": metar_data  # 返回完整解析数据供后续使用
                }
                
        except asyncio.TimeoutError:
            return {
                "success": False,
                "metar_raw": None,
                "icao_code": icao,
                "observation_time": None,
                "source": "NOAA",
                "error": "请求超时"
            }
        except Exception as e:
            return {
                "success": False,
                "metar_raw": None,
                "icao_code": icao,
                "observation_time": None,
                "source": "NOAA",
                "error": str(e)
            }
    
    def _parse_noaa_response(self, text: str, icao: str) -> Optional[str]:
        """
        解析NOAA API响应，提取最新的METAR报文
        
        响应格式可能是：
        1. 单条METAR: "METAR ZBAA 111800Z 27008MPS 9999 FEW040 18/08 Q1018 NOSIG"
        2. 多条METAR（换行分隔）
        3. 空响应
        """
        if not text or not text.strip():
            return None
        
        # 清理并分割
        lines = [line.strip() for line in text.strip().split('\n') if line.strip()]
        
        if not lines:
            return None
        
        # 过滤出包含目标ICAO的METAR
        metar_lines = []
        for line in lines:
            # 移除可能的METAR前缀
            clean = line.replace("METAR ", "").strip()
            if clean.startswith(icao.upper()):
                metar_lines.append(clean)
        
        if not metar_lines:
            # 如果没有精确匹配，返回第一条（可能ICAO在第二位）
            first_line = lines[0].replace("METAR ", "").strip()
            return first_line if first_line else None
        
        # 返回最新的一条（通常是第一条）
        return metar_lines[0]
    
    def _extract_observation_time(self, metar_raw: str) -> Optional[datetime]:
        """
        从METAR报文中提取观测时间
        
        格式: DDHHMMZ (如 111800Z 表示11日18:00UTC)
        """
        try:
            # 匹配时间模式
            pattern = r'(\d{2})(\d{2})(\d{2})Z'
            match = re.search(pattern, metar_raw)
            
            if match:
                day, hour, minute = int(match.group(1)), int(match.group(2)), int(match.group(3))
                
                # 使用当前年月
                now = datetime.utcnow()
                return datetime(now.year, now.month, day, hour, minute)
            
            return None
        except Exception:
            return None
    
    async def fetch_multiple_metars(self, icao_codes: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        批量获取多个机场的METAR（一次请求，效率更高）
        
        Args:
            icao_codes: ICAO代码列表
            
        Returns:
            Dict[icao_code, result]
        """
        try:
            session = await self._get_session()
            
            # 批量请求（逗号分隔）
            params = {
                "ids": ",".join(icao_codes),
                "format": "json",
            }
            
            headers = {
                "User-Agent": "DeerFlow-AviationWeather-Agent/1.0",
                "Accept": "application/json"
            }
            
            async with session.get(
                self.NOAA_METAR_URL,
                params=params,
                headers=headers
            ) as response:
                if response.status != 200:
                    # 如果批量失败，返回所有机场的错误
                    return {
                        icao: {
                            "success": False,
                            "metar_raw": None,
                            "icao_code": icao,
                            "observation_time": None,
                            "source": "NOAA",
                            "error": f"HTTP {response.status}"
                        }
                        for icao in icao_codes
                    }
                
                data = await response.json()
                
                # 构建结果字典
                results = {}
                for icao in icao_codes:
                    # 查找匹配的METAR
                    matched = None
                    if data and isinstance(data, list):
                        for item in data:
                            if item.get("icaoId", "").upper() == icao.upper():
                                matched = item
                                break
                    
                    if matched:
                        metar_raw = matched.get("rawOb", "")
                        obs_time_str = matched.get("reportTime")
                        if obs_time_str:
                            try:
                                obs_time = datetime.fromisoformat(obs_time_str.replace("Z", "+00:00"))
                            except:
                                obs_time = self._extract_observation_time(metar_raw)
                        else:
                            obs_time = self._extract_observation_time(metar_raw)
                        
                        results[icao] = {
                            "success": True,
                            "metar_raw": metar_raw,
                            "icao_code": icao,
                            "observation_time": obs_time,
                            "source": "NOAA/aviationweather.gov",
                            "error": None,
                            "parsed_data": matched
                        }
                    else:
                        results[icao] = {
                            "success": False,
                            "metar_raw": None,
                            "icao_code": icao,
                            "observation_time": None,
                            "source": "NOAA",
                            "error": f"未找到 {icao} 的METAR数据"
                        }
                
                return results
                
        except Exception as e:
            logger.error(f"批量获取METAR失败: {str(e)}")
            return {
                icao: {
                    "success": False,
                    "metar_raw": None,
                    "icao_code": icao,
                    "observation_time": None,
                    "source": "NOAA",
                    "error": str(e)
                }
                for icao in icao_codes
            }
    
    async def fetch_metar_with_fallback(
        self, 
        icao_code: str, 
        fallback_metar: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取METAR，支持降级到备用报文
        
        用于实时API失败时，使用用户提供的或预设的METAR
        """
        result = await self.fetch_metar(icao_code)
        
        if result["success"]:
            return result
        
        # API失败，使用备用METAR
        if fallback_metar:
            obs_time = self._extract_observation_time(fallback_metar)
            return {
                "success": True,
                "metar_raw": fallback_metar,
                "icao_code": icao_code,
                "observation_time": obs_time,
                "source": "fallback/manual",
                "error": None,
                "is_fallback": True
            }
        
        return result


# 单例实例
_metar_service: Optional[METARService] = None


def get_metar_service() -> METARService:
    """获取METAR服务单例"""
    global _metar_service
    if _metar_service is None:
        _metar_service = METARService()
    return _metar_service


# 便捷函数
async def fetch_metar(icao_code: str) -> Dict[str, Any]:
    """获取指定机场的METAR"""
    service = get_metar_service()
    return await service.fetch_metar(icao_code)


# 测试代码
if __name__ == "__main__":
    import asyncio
    
    async def test():
        service = METARService()
        
        # 测试几个机场
        test_airports = ["ZBAA", "ZSPD", "KJFK"]
        
        for icao in test_airports:
            print(f"\n获取 {icao} 的METAR...")
            result = await service.fetch_metar(icao)
            
            if result["success"]:
                print(f"✓ 成功 [{result['source']}]")
                print(f"  METAR: {result['metar_raw']}")
                print(f"  时间: {result['observation_time']}")
            else:
                print(f"✗ 失败: {result['error']}")
        
        await service.close()
    
    asyncio.run(test())
