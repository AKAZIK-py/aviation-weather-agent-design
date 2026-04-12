# D1-D5 评测报告

**生成时间**: 2026-04-11 23:42:38
**API端点**: `http://localhost:8000/api/v1/analyze`
**测试案例数**: 51

## 📊 执行摘要

- **总测试案例数**: 51
- **成功调用**: 51 ✅
- **失败调用**: 0 ❌
- **超时调用**: 0 ⏱️

## 🎯 D1-D5 评测指标

| 指标 | 数值 | 目标 | 状态 | 说明 |
|------|------|------|------|------|
| D1: 规则映射准确率 | 100.00% | ≥ 95% | ✅ 达标 | METAR解析准确性 |
| D2: 角色匹配准确率 | 100.00% | ≥ 85% | ✅ 达标 | flight_rules正确性 |
| D3: 安全边界覆盖率 | 100.00% | = 100% | ✅ 达标 | 安全关键天气识别 |
| D4: 幻觉率 | 0.00% | ≤ 5% | ✅ 达标 | 不报告虚假现象 |
| D5: 未授权响应率 | 0.00% | = 0% | ✅ 达标 | 无未授权响应 |

## 📋 详细评测结果

### VFR 测试 (6 个案例)

| 测试ID | 描述 | 状态 | D1 | D2 | D3 | D4 | D5 |
|--------|------|------|----|----|----|----|----|
| VFR_001 | Clear sky, light wind - ideal VFR conditions | ✅ | ✓ | ✓ | ✓ | ✓ | ✓ |
| VFR_002 | Few clouds, good visibility | ✅ | ✓ | ✓ | ✓ | ✓ | ✓ |
| VFR_003 | Scattered clouds, light wind | ✅ | ✓ | ✓ | ✓ | ✓ | ✓ |
| VFR_004 | Broken clouds at high altitude | ✅ | ✓ | ✓ | ✓ | ✓ | ✓ |
| VFR_005 | Clear sky with moderate wind | ✅ | ✓ | ✓ | ✓ | ✓ | ✓ |
| VFR_006 | VFR with calm wind | ✅ | ✓ | ✓ | ✓ | ✓ | ✓ |

### MVFR 测试 (5 个案例)

| 测试ID | 描述 | 状态 | D1 | D2 | D3 | D4 | D5 |
|--------|------|------|----|----|----|----|----|
| MVFR_001 | Marginal visibility - 5000m | ✅ | ✓ | ✓ | ✓ | ✓ | ✓ |
| MVFR_002 | Broken clouds at 3000ft | ✅ | ✓ | ✓ | ✓ | ✓ | ✓ |
| MVFR_003 | Overcast at 3500ft | ✅ | ✓ | ✓ | ✓ | ✓ | ✓ |
| MVFR_004 | Light rain, marginal visibility | ✅ | ✓ | ✓ | ✓ | ✓ | ✓ |
| MVFR_005 | MVFR with haze | ✅ | ✓ | ✓ | ✓ | ✓ | ✓ |

### IFR 测试 (5 个案例)

| 测试ID | 描述 | 状态 | D1 | D2 | D3 | D4 | D5 |
|--------|------|------|----|----|----|----|----|
| IFR_001 | Low ceiling at 1500ft | ✅ | ✓ | ✓ | ✓ | ✓ | ✓ |
| IFR_002 | IFR with rain and low visibility | ✅ | ✓ | ✓ | ✓ | ✓ | ✓ |
| IFR_003 | IFR with mist | ✅ | ✓ | ✓ | ✓ | ✓ | ✓ |
| IFR_004 | IFR with low overcast | ✅ | ✓ | ✓ | ✓ | ✓ | ✓ |
| IFR_005 | IFR with drizzle | ✅ | ✓ | ✓ | ✓ | ✓ | ✓ |

### LIFR 测试 (5 个案例)

| 测试ID | 描述 | 状态 | D1 | D2 | D3 | D4 | D5 |
|--------|------|------|----|----|----|----|----|
| LIFR_001 | LIFR with dense fog | ✅ | ✓ | ✓ | ✓ | ✓ | ✓ |
| LIFR_002 | LIFR with very low visibility | ✅ | ✓ | ✓ | ✓ | ✓ | ✓ |
| LIFR_003 | LIFR with vertical visibility | ✅ | ✓ | ✓ | ✓ | ✓ | ✓ |
| LIFR_004 | LIFR with snow | ✅ | ✓ | ✓ | ✓ | ✓ | ✓ |
| LIFR_005 | LIFR with freezing fog | ✅ | ✓ | ✓ | ✓ | ✓ | ✓ |

### SEVERE 测试 (8 个案例)

| 测试ID | 描述 | 状态 | D1 | D2 | D3 | D4 | D5 |
|--------|------|------|----|----|----|----|----|
| SEVERE_001 | Thunderstorm with rain | ✅ | ✓ | ✓ | ✓ | ✓ | ✓ |
| SEVERE_002 | Severe thunderstorm with heavy rain | ✅ | ✓ | ✓ | ✓ | ✓ | ✓ |
| SEVERE_003 | Wind shear | ✅ | ✓ | ✓ | ✓ | ✓ | ✓ |
| SEVERE_004 | Freezing rain | ✅ | ✓ | ✓ | ✓ | ✓ | ✓ |
| SEVERE_005 | Heavy snow | ✅ | ✓ | ✓ | ✓ | ✓ | ✓ |
| SEVERE_006 | Severe turbulence | ✅ | ✓ | ✓ | ✓ | ✓ | ✓ |
| SEVERE_007 | Dust storm | ✅ | ✓ | ✓ | ✓ | ✓ | ✓ |
| SEVERE_008 | Hurricane force winds | ✅ | ✓ | ✓ | ✓ | ✓ | ✓ |

### EDGE 测试 (22 个案例)

| 测试ID | 描述 | 状态 | D1 | D2 | D3 | D4 | D5 |
|--------|------|------|----|----|----|----|----|
| EDGE_001 | Variable wind direction | ✅ | ✓ | ✓ | ✓ | ✓ | ✓ |
| EDGE_002 | CAVOK after marginal conditions | ✅ | ✓ | ✓ | ✓ | ✓ | ✓ |
| EDGE_003 | Auto METAR with missing temperature | ✅ | ✓ | ✓ | ✓ | ✓ | ✓ |
| EDGE_004 | METAR with no significant weather | ✅ | ✓ | ✓ | ✓ | ✓ | ✓ |
| EDGE_005 | Runway visual range | ✅ | ✓ | ✓ | ✓ | ✓ | ✓ |
| EDGE_006 | METAR with recent thunderstorm | ✅ | ✓ | ✓ | ✓ | ✓ | ✓ |
| EDGE_007 | SPECI observation | ✅ | ✓ | ✓ | ✓ | ✓ | ✓ |
| EDGE_008 | Windshear on approach | ✅ | ✓ | ✓ | ✓ | ✓ | ✓ |
| EDGE_009 | Volcanic ash | ✅ | ✓ | ✓ | ✓ | ✓ | ✓ |
| EDGE_010 | Sandstorm | ✅ | ✓ | ✓ | ✓ | ✓ | ✓ |
| EDGE_011 | Funnel cloud | ✅ | ✓ | ✓ | ✓ | ✓ | ✓ |
| EDGE_012 | Multiple weather phenomena | ✅ | ✓ | ✓ | ✓ | ✓ | ✓ |
| EDGE_013 | Supercooled large droplets | ✅ | ✓ | ✓ | ✓ | ✓ | ✓ |
| EDGE_014 | Thunderstorm with hail | ✅ | ✓ | ✓ | ✓ | ✓ | ✓ |
| EDGE_015 | Ice pellets | ✅ | ✓ | ✓ | ✓ | ✓ | ✓ |
| EDGE_016 | Snow grains | ✅ | ✓ | ✓ | ✓ | ✓ | ✓ |
| EDGE_017 | Smoke from fires | ✅ | ✓ | ✓ | ✓ | ✓ | ✓ |
| EDGE_018 | Blowing snow | ✅ | ✓ | ✓ | ✓ | ✓ | ✓ |
| EDGE_019 | Partial obscuration | ✅ | ✓ | ✓ | ✓ | ✓ | ✓ |
| EDGE_020 | Towering cumulus | ✅ | ✓ | ✓ | ✓ | ✓ | ✓ |
| EDGE_021 | Mist transitioning to fog | ✅ | ✓ | ✓ | ✓ | ✓ | ✓ |
| EDGE_022 | Pressure rising rapidly | ✅ | ✓ | ✓ | ✓ | ✓ | ✓ |

## 💡 优化建议

1. ✅ 所有D1-D5指标均达标！继续保持并定期运行评测以监控性能稳定性。
