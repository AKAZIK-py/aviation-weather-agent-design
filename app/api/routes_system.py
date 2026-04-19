"""
系统端点 — 机场搜索、METAR 查询、评测指标、Badcase 列表

这些端点为前端 Chat UI 提供辅助数据，
不破坏 V1/V2 API。
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.data.airports import JANGSU_ZHEJIANG_SHANGHAI_AIRPORTS

logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== 机场搜索 ====================


@router.get("/airports/search")
async def search_airports(q: str = "", limit: int = 20):
    """模糊搜索机场（ICAO / IATA / 名称 / 城市）。"""
    q_lower = q.strip().lower()
    if not q_lower:
        # 返回全部（按 limit 截断）
        airports = JANGSU_ZHEJIANG_SHANGHAI_AIRPORTS[:limit]
    else:
        results = []
        for ap in JANGSU_ZHEJIANG_SHANGHAI_AIRPORTS:
            searchable = " ".join(
                [
                    ap.icao.lower(),
                    ap.iata.lower(),
                    ap.name_cn.lower(),
                    ap.name_en.lower(),
                    ap.city_cn.lower(),
                    ap.city_en.lower(),
                ]
            )
            if q_lower in searchable:
                results.append(ap)
            if len(results) >= limit:
                break
        airports = results

    return {
        "results": [
            {
                "icao": ap.icao,
                "iata": ap.iata,
                "name": ap.name_cn,
                "city": ap.city_cn,
            }
            for ap in airports
        ],
        "count": len(airports),
    }


# ==================== 机场 METAR ====================


@router.get("/airports/{icao}/metar")
async def get_airport_metar(icao: str):
    """获取指定机场的实时 METAR 报文。"""
    icao_upper = icao.upper()

    # 检查是否在支持列表中
    supported = {ap.icao for ap in JANGSU_ZHEJIANG_SHANGHAI_AIRPORTS}
    if icao_upper not in supported:
        raise HTTPException(
            status_code=404,
            detail=f"机场 {icao_upper} 不在支持列表中。支持: {', '.join(sorted(supported))}",
        )

    from app.services.metar_fetcher import fetch_metar_for_airport

    try:
        metar_raw, metadata = await fetch_metar_for_airport(icao_upper)
        return {
            "icao": icao_upper,
            "metar_raw": metar_raw,
            "metadata": metadata,
        }
    except Exception as e:
        logger.error("获取 %s METAR 失败: %s", icao_upper, e)
        raise HTTPException(status_code=502, detail=f"获取 METAR 失败: {e}")


# ==================== 评测指标 ====================


@router.get("/metrics")
async def get_system_metrics(days: int = 7):
    """返回评测指标概览 — 基于 eval_store 聚合。"""
    from app.services.eval_store import get_aggregated_metrics
    return get_aggregated_metrics(days=days)


# ==================== Badcase 列表 ====================


@router.get("/badcases")
async def list_badcases(limit: int = 20):
    """返回 badcase 列表。"""
    from app.evaluation.badcase_manager import BadcaseManager

    manager = BadcaseManager()
    cases = manager.load_badcases()

    # 按 case_id 降序（最新在前）
    sorted_cases = sorted(cases, key=lambda c: c.get("case_id", ""), reverse=True)

    return {
        "badcases": sorted_cases[:limit],
        "total": len(cases),
        "returned": min(limit, len(sorted_cases)),
    }
