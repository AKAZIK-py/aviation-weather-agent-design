# 航空气象 Agent 评测数据集

## 目录结构

```
eval/
├── datasets/                    # 评测数据集
│   ├── standard_testset_v1.json # L1 标准集 (25条，git tag冻结)
│   ├── boundary_testset_v1.json # L2 边界集 (待构建)
│   ├── adversarial_testset_v1.json # L3 对抗集 (待构建)
│   └── README.md                # 本文件
├── golden_answers/              # 人工标注标准答案
│   ├── standard_v1_answers.json # (待标注)
│   └── boundary_v1_answers.json # (待标注)
├── results/                     # 每次评测结果存档
│   └── eval_YYYY-MM-DD_runNN.json
└── badcases/                    # 失败案例沉淀
    ├── schema.json              # badcase 记录格式
    └── *.json                   # 具体 badcase 记录
```

## 数据字典

### Case 结构

```json
{
  "id": "GS_001",                   // 唯一标识，格式: GS_NNN
  "metar": "ZBAA ...",              // 原始 METAR 报文
  "parsed": { ... },                // METAR 解析结果
  "role": "pilot",                  // 用户角色
  "query": "首都机场能见度怎么样",    // 用户提问
  "expected_key_info": [ ... ],     // 期望命中的关键信息
  "scoring_criteria": { ... }       // 打分标准
}
```

### 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | string | 是 | 唯一标识，格式 `GS_NNN`，全局不重复 |
| metar | string | 是 | 原始 METAR 编码报文 |
| parsed | object | 是 | METAR 解析后的结构化数据 |
| role | string | 是 | 用户角色: `pilot` / `dispatcher` / `forecaster` / `ground_crew` |
| query | string | 是 | 用户自然语言提问 |
| expected_key_info | array | 是 | 期望 Agent 输出必须命中的关键信息列表 |
| scoring_criteria | object | 是 | 打分标准（见下） |

### parsed 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| icao_code | string | ICAO 机场代码 |
| visibility | float | 能见度(km) |
| wind_speed | int | 风速(kt) |
| wind_direction | int\|null | 风向(度)，静风时为 null |
| wind_gust | int | 阵风(kt)，可选 |
| temperature | int | 温度(°C) |
| dewpoint | int | 露点(°C) |
| cloud_layers | array | 云层列表 |
| present_weather | array | 当前天气现象 |
| vertical_visibility | int\|null | 垂直能见度(ft) |
| flight_rules | string | 飞行规则: VFR / MVFR / IFR / LIFR |
| is_cavok | bool | 是否 CAVOK，可选 |
| wind_shear | string | 风切变信息，可选 |
| has_trend | bool | 是否有趋势组，可选 |
| trend_type | string | 趋势类型: BECMG / TEMPO，可选 |

### scoring_criteria 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| must_mention | array | 输出必须提到的关键词/短语 |
| must_give | array | 输出必须给出的建议/结论类型 |
| must_not_output | array | 禁止输出的内容（如固定模板栏目） |

## 角色定义

| 角色 | 值 | 关注点 |
|------|-----|--------|
| 飞行员 | `pilot` | 能见度、云底高、风、进近方式 |
| 签派员 | `dispatcher` | 放行条件、备降油量、航路天气 |
| 预报员 | `forecaster` | 天气趋势、变化时间窗 |
| 地勤机务 | `ground_crew` | 外场作业条件、除冰、风速限制 |

## 场景覆盖 (标准集 v1)

| 场景分类 | 数量 | 典型 METAR |
|---------|------|-----------|
| VFR 晴好天气 | ~6 | CAVOK, 9999 SCT040 |
| MVFR 轻度影响 | ~5 | 4000 BR, 6000 -RA |
| IFR 低能见度/低云 | ~8 | 1200 FG OVC003, 1500 RA |
| LIFR 极端低能见度 | ~4 | 0400 FG VV001, 050 VV001 |
| 极端天气(雷暴/冻雨/风切变) | ~5 | +TSRA, FZFG, WS R23 |
| 边界值 | ~2 | 1600 HZ, 2000 FZFG |

## 标注规范

### expected_key_info 标注原则

1. **基于角色**: 只标该角色最关心的信息
2. **具体可验证**: 用具体数值或明确描述，不用模糊词汇
3. **最小集**: 只标必须命中的，不标可有可无的

### 打分规则

- **关键信息命中率**: 逐条检查 `expected_key_info` 是否在输出中出现，命中数/总数
- **任务完成率**: 用户的 query 是否被真正回答，必须有结论而非仅数据复述
- **输出可用率**: 输出能否直接给角色使用（LLM-as-Judge）
- **模板化检测**: 是否输出固定模板栏目

### 防过拟合

1. 标准集 git tag 锁定，修改需 PR + 人工审核
2. 边界集从真实历史 METAR 分层抽样
3. 对抗集独立管理，开发团队不可见
4. hold-out 集永不参与调优

## 版本历史

| 版本 | 日期 | 说明 |
|------|------|------|
| v1 | 2026-04-14 | 初始版本，从 golden_set.json 迁移，25条 |
