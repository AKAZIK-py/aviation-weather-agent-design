"""
METAR解析服务
METAR Parsing Service (Layer 1: 气象事实解析)
"""
import re
from typing import Dict, Any, List, Optional
from app.models import ParsedMETAR, WindData, VisibilityData, CloudData, WeatherPhenomenon


class METARParser:
    """METAR报文解析器"""
    
    def parse(self, metar_raw: str) -> ParsedMETAR:
        """解析METAR报文"""
        parsed = ParsedMETAR(raw=metar_raw)
        
        try:
            tokens = metar_raw.split()
            token_idx = 0
            
            # 解析站点代码 (ZBAA, ZSSS等)
            if len(tokens) > token_idx and re.match(r'^[A-Z]{4}$', tokens[token_idx]):
                parsed.station = tokens[token_idx]
                token_idx += 1
            
            # 解析观测时间 (110800Z)
            if len(tokens) > token_idx and re.match(r'^\d{6}Z$', tokens[token_idx]):
                parsed.time = tokens[token_idx]
                token_idx += 1
            
            # 解析风 (18015G25KT 或 18015MPS)
            if len(tokens) > token_idx:
                wind_match = re.match(
                    r'^(\d{3})(\d{2,3})(G(\d{2,3}))?(KT|MPS|KMH)$',
                    tokens[token_idx]
                )
                if wind_match:
                    parsed.wind = WindData(
                        direction=int(wind_match.group(1)),
                        speed=int(wind_match.group(2)),
                        gust=int(wind_match.group(4)) if wind_match.group(4) else None,
                        unit="MPS" if "MPS" in tokens[token_idx] else "KT"
                    )
                    token_idx += 1
            
            # 解析能见度 (3000 或 9999 或 1/2SM)
            if len(tokens) > token_idx:
                vis_match = re.match(r'^(\d{4})$', tokens[token_idx])
                if vis_match:
                    parsed.visibility = VisibilityData(value=int(vis_match.group(1)))
                    token_idx += 1
            
            # 解析天气现象 (TSRA, -RA, +SHRA等)
            if len(tokens) > token_idx:
                while len(tokens) > token_idx and re.match(r'^[\+\-]?[A-Z]{2,4}$', tokens[token_idx]):
                    weather_code = tokens[token_idx]
                    intensity = "moderate"
                    if weather_code.startswith('+'):
                        intensity = "heavy"
                        weather_code = weather_code[1:]
                    elif weather_code.startswith('-'):
                        intensity = "light"
                        weather_code = weather_code[1:]
                    
                    parsed.weather.append(WeatherPhenomenon(
                        code=weather_code,
                        intensity=intensity
                    ))
                    token_idx += 1
            
            # 解析云层 (BKN010CB, SCT030, FEW015等)
            if len(tokens) > token_idx:
                while len(tokens) > token_idx:
                    cloud_match = re.match(
                        r'^(FEW|SCT|BKN|OVC|NSC)(\d{3})(CB|TCU)?$',
                        tokens[token_idx]
                    )
                    if cloud_match:
                        parsed.clouds.append(CloudData(
                            coverage=cloud_match.group(1),
                            height=int(cloud_match.group(2)) * 30,  # 转换为米
                            type=cloud_match.group(3)
                        ))
                        token_idx += 1
                    else:
                        break
            
            # 解析温度/露点 (25/22)
            if len(tokens) > token_idx:
                temp_match = re.match(r'^(M?\d{2})/(M?\d{2})$', tokens[token_idx])
                if temp_match:
                    temp_str = temp_match.group(1).replace('M', '-')
                    dew_str = temp_match.group(2).replace('M', '-')
                    parsed.temperature = int(temp_str)
                    parsed.dewpoint = int(dew_str)
                    token_idx += 1
            
            # 解析QNH气压 (Q1008)
            if len(tokens) > token_idx:
                qnh_match = re.match(r'^Q(\d{4})$', tokens[token_idx])
                if qnh_match:
                    parsed.qnh = int(qnh_match.group(1))
                    token_idx += 1
            
            # 解析趋势预报 (TEMPO, BECMG, NOSIG)
            while token_idx < len(tokens):
                if tokens[token_idx] in ['TEMPO', 'BECMG', 'NOSIG', 'PROB']:
                    parsed.trends.append(' '.join(tokens[token_idx:]))
                    break
                token_idx += 1
            
            return parsed
            
        except Exception as e:
            print(f"METAR解析错误: {e}")
            return parsed


# 全局解析器实例
metar_parser = METARParser()
