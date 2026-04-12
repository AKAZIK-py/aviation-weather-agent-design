"""
角色识别节点 - classify_role_node
职责：根据用户查询识别角色（pilot/dispatcher/forecaster/ground_crew）
使用关键词匹配+LLM辅助识别
"""
from typing import Dict, Any, List, Tuple
from langchain_core.runnables import RunnableConfig

from app.core.workflow_state import WorkflowState
from app.core.llm_client import get_llm_client


class RoleClassifier:
    """角色分类器"""
    
    # 角色关键词映射（四角色体系）
    ROLE_KEYWORDS = {
        "pilot": {
            "keywords": [
                "飞行员", "机长", "副驾", "起飞", "着陆", "进近", "航路",
                "侧风", "能见度", "决断高", "ILS", "VFR", "IFR",
                "飞行", "航空气象", "飞行安全", "起飞标准", "着陆标准",
                "复飞", "备降", "燃油", "飞行计划", "pilot", "起飞重量"
            ],
            "concerns": ["飞行安全", "起降决策", "航路天气", "备降选择"],
        },
        "dispatcher": {
            "keywords": [
                "签派", "运控", "放行", "航班计划", "流量", "AOC", "FOC",
                "签派员", "航班正常性", "延误", "取消", "备降场",
                "油量计算", "时刻协调", "运行控制", "dispatcher",
                "签派放行", "飞行计划", "航路选择", "性能计算"
            ],
            "concerns": ["航班正常性", "运行效率", "成本控制", "决策支持"],
        },
        "forecaster": {
            "keywords": [
                "预报员", "气象台", "天气预报", "趋势", "TAF", "METAR",
                "气压", "锋面", "高压", "低压", "气团", "对流",
                "雷暴", "降水", "能见度预报", "风向风速预报",
                "sigmet", "气象警报", "forecaster", "天气系统",
                "形势分析", "数值预报", "气象学"
            ],
            "concerns": ["天气演变", "预报准确性", "警报发布", "趋势研判"],
        },
        "ground_crew": {
            "keywords": [
                "地勤", "机坪", "廊桥", "行李", "清洁", "加油", "配餐",
                "拖车", "摆渡", "登机", "下客", "装卸", "地面服务",
                "除冰", "排污", "供水", "跑道检查", "道面状况",
                "地面作业", "机务", "维修", "检查", "故障", "MEL",
                "ground", "ground_crew", "地面运行"
            ],
            "concerns": ["地面作业", "旅客服务", "航班保障", "设备操作"],
        },
    }
    
    # 中文名映射（用于显示）
    ROLE_NAMES_CN = {
        "pilot": "飞行员",
        "dispatcher": "签派管制",
        "forecaster": "预报员",
        "ground_crew": "地勤",
    }
    
    def __init__(self):
        self.llm_client = None
    
    async def init_llm(self):
        """初始化LLM客户端"""
        if self.llm_client is None:
            self.llm_client = get_llm_client()
    
    def classify_by_keywords(self, query: str) -> Tuple[str, float, List[str]]:
        """
        基于关键词的角色识别
        
        Returns:
            Tuple[role, confidence, matched_keywords]
        """
        query_lower = query.lower()
        scores = {}
        matched = {}
        
        for role, data in self.ROLE_KEYWORDS.items():
            score = 0
            matches = []
            
            for keyword in data["keywords"]:
                if keyword.lower() in query_lower:
                    score += 1
                    matches.append(keyword)
            
            # 归一化分数
            max_keywords = len(data["keywords"])
            scores[role] = score / max_keywords if max_keywords > 0 else 0
            matched[role] = matches
        
        # 找出得分最高的角色
        if not scores or max(scores.values()) == 0:
            return "dispatcher", 0.5, []  # 默认角色
        
        best_role = max(scores, key=scores.get)
        confidence = scores[best_role]
        
        return best_role, confidence, matched[best_role]
    
    async def classify_with_llm(
        self, 
        query: str, 
        metar_data: Dict[str, Any]
    ) -> Tuple[str, float, str]:
        """
        使用LLM进行角色识别
        
        Returns:
            Tuple[role, confidence, reasoning]
        """
        await self.init_llm()
        
        prompt = f"""你是一个航空气象专家，需要根据用户的查询识别其角色。

航空气象服务的四类用户角色：
1. **pilot（飞行员）** - 关注飞行安全、起降决策、航路天气、备降选择
2. **dispatcher（签派管制）** - 关注航班正常性、运行效率、签派放行、流量管理
3. **forecaster（预报员）** - 关注天气演变、预报准确性、警报发布、趋势研判
4. **ground_crew（地勤）** - 关注地面作业、旅客服务、航班保障、设备操作

当前METAR报文：
{metar_data.get('raw_text', '')}

解析后的关键信息：
- ICAO: {metar_data.get('icao_code', 'N/A')}
- 风向风速: {metar_data.get('wind_direction', 'N/A')}° / {metar_data.get('wind_speed', 'N/A')}KT
- 能见度: {metar_data.get('visibility', 'N/A')} km
- 天气现象: {', '.join([w['description'] for w in metar_data.get('present_weather', [])]) or '无'}
- 云层: {len(metar_data.get('cloud_layers', []))}层

用户查询：
{query}

请分析用户查询的意图，识别最可能的角色。

输出格式（严格JSON）：
{{
  "role": "pilot|dispatcher|forecaster|ground_crew",
  "confidence": 0.0-1.0,
  "reasoning": "识别理由（50字以内）"
}}

只输出JSON，不要有其他内容。"""

        try:
            response = await self.llm_client.ainvoke(prompt)
            
            # 解析JSON响应
            import json
            result = json.loads(response.content.strip())
            
            return (
                result.get("role", "dispatcher"),
                result.get("confidence", 0.5),
                result.get("reasoning", "")
            )
        except Exception as e:
            # LLM失败，降级到关键词匹配
            role, confidence, keywords = self.classify_by_keywords(query)
            return role, confidence, f"LLM失败({str(e)})，使用关键词匹配: {', '.join(keywords)}"


# 节点函数
async def classify_role_node(
    state: WorkflowState, 
    config: RunnableConfig
) -> Dict[str, Any]:
    """
    角色识别节点
    
    输入: user_query, metar_parsed
    输出: detected_role, role_confidence, role_keywords
    """
    classifier = RoleClassifier()
    
    query = state.get("user_query", "")
    user_role = state.get("user_role")
    metar_data = state.get("metar_parsed", {})
    
    # 如果用户已提供角色，直接使用
    if user_role:
        updates = {
            "detected_role": user_role,
            "role_confidence": 1.0,
            "role_keywords": [],
            "current_node": "classify_role_node",
        }
        updates["reasoning_trace"] = [
            f"[classify_role_node] 用户指定角色: {user_role}"
        ]
        return updates
    
    # 如果没有查询，使用默认角色
    if not query:
        updates = {
            "detected_role": "dispatcher",
            "role_confidence": 0.5,
            "role_keywords": [],
            "current_node": "classify_role_node",
        }
        updates["reasoning_trace"] = [
            "[classify_role_node] 无查询，使用默认角色: dispatcher（签派管制）"
        ]
        return updates
    
    # 先用关键词匹配
    role_kw, conf_kw, keywords = classifier.classify_by_keywords(query)
    
    # 如果关键词匹配置信度足够高，直接返回
    if conf_kw >= 0.7:
        role_cn = classifier.ROLE_NAMES_CN.get(role_kw, role_kw)
        updates = {
            "detected_role": role_kw,
            "role_confidence": conf_kw,
            "role_keywords": keywords,
            "current_node": "classify_role_node",
        }
        updates["reasoning_trace"] = [
            f"[classify_role_node] 关键词匹配: {role_kw}({role_cn}) 置信度{conf_kw:.2f}，匹配词: {', '.join(keywords)}"
        ]
        return updates
    
    # 否则使用LLM识别
    role_llm, conf_llm, reasoning = await classifier.classify_with_llm(
        query, metar_data
    )
    
    role_cn = classifier.ROLE_NAMES_CN.get(role_llm, role_llm)
    
    updates = {
        "detected_role": role_llm,
        "role_confidence": conf_llm,
        "role_keywords": keywords,
        "current_node": "classify_role_node",
        "llm_calls": 1,
    }
    
    updates["reasoning_trace"] = [
        f"[classify_role_node] LLM识别: {role_llm}({role_cn}) 置信度{conf_llm:.2f}，理由: {reasoning}"
    ]
    
    return updates


# 测试代码
if __name__ == "__main__":
    import asyncio
    
    async def test():
        test_cases = [
            "这个天气适不适合起飞？",
            "塔台，请问现在的间隔标准是多少？",
            "机务检查发动机需要注意什么？",
            "地勤除冰作业有什么要求？",
            "预报员看这个天气趋势怎么样？",
            "签派员需要考虑备降场吗？",
        ]
        
        classifier = RoleClassifier()
        
        for query in test_cases:
            role, conf, keywords = classifier.classify_by_keywords(query)
            role_cn = classifier.ROLE_NAMES_CN.get(role, role)
            print(f"查询: {query}")
            print(f"角色: {role}({role_cn}), 置信度: {conf:.2f}, 关键词: {keywords}\n")
    
    asyncio.run(test())
