# 评分规则文档 (scoring/CLAUDE.md)

统一评分标准，供 normal_scorer 和 expert_scorer 使用。

## 一、4 个主指标（LLM 普通评分）

### 1. task_complete — 任务完成率 (0/1)
- **1**: Agent 输出了明确结论（建议起飞/降落/备降/GO/NO-GO 等），真正回答了用户问题
- **0**: 输出为空、出现"报告生成中"/"请稍后"等未完成模式、或无明确结论

### 2. key_info_hit — 关键信息命中率 (0/1)
- **1**: case 中 expected_key_info 的所有关键信息都在输出中被提及（支持语义等价匹配）
- **0**: 有任何一条关键信息缺失

### 3. usable — 输出可用率 (0/1)
- **1**: 输出内容完整、逻辑清晰、对目标角色有实际参考价值，可以直接使用
- **0**: 输出混乱、矛盾、信息不全、或包含无关内容，无法直接使用

### 4. template — 模板化检测 (0/1)
- **1**: 输出使用了固定模板（包含【风险分析】【建议措施】等固定栏目、连续3个以上【xxx】标题、或套话短语"作为资深""以下是"等）
- **0**: 输出自然流畅，是针对问题的个性化回答，不是套模板

## 二、2 个辅助指标（LLM 普通评分）

### 5. hallucination — 幻觉检测 (0/1)
- **1**: 存在幻觉 — 编造了 METAR 数据中不存在的气象信息、捏造飞行规则标准、或虚构安全建议
- **0**: 无幻觉 — 所有信息都能追溯到 METAR 报文或公认的航空知识

**幻觉判定标准**:
- 编造数据: 输出中出现 METAR 报文中不存在的数值（如能见度、温度、风速等）
- 编造规则: 引用了不存在的 ICAO 附件号、虚构的 FAA 法规编号
- 编造事实: 声称某机场有特殊运行规则但 METAR/NOTAM 中未提及

## 三、3 个专家指标（LLM 专家评分，基于 ICAO Annex 3）

### 6. flight_rules_accurate — 飞行规则准确率 (0/1)
- **1**: Agent 对飞行规则的判定与 METAR 数据一致
- **0**: 飞行规则判定错误

**ICAO Annex 3 飞行规则标准**:
| 规则 | 能见度 (VIS) | 云底高 (Ceiling) |
|------|-------------|-----------------|
| VFR  | > 5 km      | > 3000 ft (900m)  |
| MVFR | 3-5 km      | 1000-3000 ft (300-900m) |
| IFR  | 1-3 km      | 500-1000 ft (150-300m)  |
| LIFR | < 1 km      | < 500 ft (150m)  |

注意: 云底高以最低的 BKN/OVC 层为准，FEW/SCT 不计为 ceiling。

### 7. risk_accurate — 风险评估准确率 (0/1)
- **1**: Agent 的风险等级判定（CRITICAL/HIGH/MEDIUM/LOW）与 METAR 条件匹配
- **0**: 风险等级明显偏高或偏低

**风险等级判定标准**:
- **CRITICAL**: 雷暴(TS/CB)、能见度<1km、风切变(LLWS)、严重颠簸、火山灰
- **HIGH**: 能见度<3km、云底高<500ft、阵风>40kt、冻雨(FZFG)
- **MEDIUM**: MVFR条件、能见度3-5km、风速20-30kt
- **LOW**: VFR条件、能见度>5km、风速<20kt、无危险天气

### 8. safety_covered — 安全边界覆盖率 (0/1)
- **1**: 对于 CRITICAL 条件，Agent 正确标记了不适飞/NO-GO/备降等安全警告
- **0**: CRITICAL 条件下未给出安全警告

## 四、模板化检测标准

输出满足以下任一条件即判定为模板化（template=1）:
1. 包含固定栏目标题: 【风险分析】【建议措施】【角色职责】【核心职责】【思维链路】等
2. 连续3个以上【xxx】格式标题
3. 连续3个以上**加粗标题：**格式
4. 包含套话短语: "作为资深""根据您的角色""以下是""首先...其次...最后"等

## 五、幻觉判定标准

hallucination=1 当且仅当:
1. **编造数据**: 输出中出现 METAR 报文中不存在的气象数值（能见度、温度、风速、云底高等）
2. **编造规则**: 引用了不存在的 ICAO 附件编号、虚构的 FAA/CAAC 法规
3. **编造事实**: 声称某机场有特殊运行限制但 METAR/NOTAM 中未提及

不算幻觉的情况:
- 使用通用航空常识（如"雷暴天气不适合目视飞行"）
- 对已有数据的合理推断（如"能见度下降趋势"）

## 六、输出 JSON 格式规范

### 普通评分输出 (normal_scores.jsonl)
```json
{
  "case_id": "STD_001",
  "task_complete": 1,
  "key_info_hit": 1,
  "usable": 1,
  "template": 0,
  "hallucination": 0,
  "reasoning": {
    "task_complete": "Agent 明确建议可以降落，给出了 GO 判定",
    "key_info_hit": "提到了能见度良好、云层较高、VFR条件三个关键信息",
    "usable": "回答完整，对飞行员有参考价值",
    "template": "自然语言回答，无固定栏目",
    "hallucination": "所有数据均可追溯到 METAR 报文"
  }
}
```

### 专家评分输出 (expert_scores.jsonl)
```json
{
  "case_id": "STD_001",
  "flight_rules_accurate": 1,
  "risk_accurate": 1,
  "safety_covered": 1,
  "reasoning": {
    "flight_rules_accurate": "METAR 显示 VIS>5km + SCT040，判定 VFR 正确",
    "risk_accurate": "无危险天气，风速适中，LOW 风险合理",
    "safety_covered": "非 CRITICAL case，无需安全警告"
  }
}
```

### 汇总 JSON (summary.json 中的 llm_normal / llm_expert)
```json
{
  "case_id": "STD_001",
  "query": "ZSSS天气怎么样",
  "metar_text": "METAR ZSSS 0600Z 09008KT 9999 SCT040 25/18 Q1015",
  "script_scores": {"task_completed": true, "key_info_hit_rate": 1.0, "is_template": false},
  "script_labels": {"flight_rules": "VFR", "risk_level": "LOW", "key_weather": "clear", "role": "pilot"},
  "llm_normal": {"task_complete": 1, "key_info_hit": 1, "usable": 1, "template": 0, "hallucination": 0, "reasoning": "..."},
  "llm_expert": {"flight_rules_accurate": 1, "risk_accurate": 1, "safety_covered": 1, "reasoning": "..."}
}
```
