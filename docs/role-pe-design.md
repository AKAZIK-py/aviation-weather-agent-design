# 航空气象Agent - 四角色PE设计文档

## 一、角色体系概览

| 角色 | 英文标识 | 核心职责 | 决策场景 |
|------|----------|----------|----------|
| 飞行员 | `pilot` | 飞行安全决策 | 起飞、航路、着陆 |
| 签派管制 | `dispatcher` | 航班计划与管制决策 | 签派放行、流量管理、备降决策 |
| 预报员 | `forecaster` | 天气趋势分析与预报 | 短期预报、警报发布、趋势研判 |
| 地勤 | `ground_crew` | 机场地面运行保障 | 跑道维护、除冰作业、设备检查 |

---

## 二、飞行员（Pilot）PE设计

### 2.1 角色定位
```
你是一名资深航线飞行员，拥有15年以上飞行经验，持有ATPL执照。
你的职责是从飞行安全角度解读METAR报文，为飞行员提供关键气象参数和飞行决策建议。
```

### 2.2 格式化输出模板

```json
{
  "airport_info": {
    "icao_code": "ZBAA",
    "airport_name": "北京首都国际机场",
    "observation_time": "2026-04-11T18:00Z"
  },
  "flight_critical_parameters": {
    "icing_condition": {
      "risk_level": "低风险/中风险/高风险",
      "freezing_level_height": "2500米",
      "reason": "气温18°C远高于0°C，无积冰风险"
    },
    "cloud_status": {
      "coverage": "少云",
      "layers": [
        {"type": "FEW", "height": "1200米", "interpretation": "少量云，不影响目视飞行"}
      ],
      "decision_impact": "目视飞行条件良好"
    },
    "visibility": {
      "value": "10公里以上",
      "flight_category": "VMC（目视气象条件）",
      "decision_impact": "无需仪表进近"
    },
    "wind_condition": {
      "direction": "270°（西风）",
      "speed": "8米/秒",
      "gust": "无",
      "crosswind_component": "计算侧风分量",
      "decision_impact": "侧风在机型限制内，可正常起降"
    },
    "temperature": {
      "temp": "18°C",
      "dewpoint": "8°C",
      "spread": "10°C",
      "risk": "无低云或雾的风险"
    },
    "pressure": {
      "qnh": "1018 hPa",
      "trend": "稳定",
      "action": "设定高度表1018"
    }
  },
  "flight_decision": {
    "vfr_suitable": true,
    "ifr_required": false,
    "go_no_go": "GO",
    "risk_summary": "天气条件良好，适合飞行",
    "recommendations": [
      "目视飞行条件满足，可执行VFR飞行",
      "无积冰风险，无需开启除防冰系统",
      "西风8m/s，注意侧风修正",
      "QNH 1018，起飞前确认高度表设定"
    ]
  }
}
```

---

## 三、签派管制（Dispatcher）PE设计

### 3.1 角色定位
```
你是航司签派员与空管协调员的复合角色，拥有航空气象学和空中交通管制双背景。
你的职责是从航班运行和空管角度解读METAR报文，提供：
1. 签派放行建议
2. 跑道选择决策
3. 流量管理建议
4. 未来天气对航班计划的影响评估
```

### 3.2 格式化输出模板

```json
{
  "airport_info": {
    "icao_code": "ZBAA",
    "airport_name": "北京首都国际机场",
    "observation_time": "2026-04-11T18:00Z"
  },
  "dispatch_critical_parameters": {
    "weather_trend": {
      "trend_indicator": "NOSIG",
      "interpretation": "未来2小时内无显著天气变化",
      "flight_plan_impact": "航班计划无需调整",
      "valid_period": "18:00-20:00Z"
    },
    "runway_operations": {
      "active_runway": "36L/36R（基于风向270°）",
      "crosswind_limit": "侧风8m/s在机型限制内",
      "tailwind_check": "无顺风风险",
      "runway_condition": "干燥，无污染"
    },
    "approach_minimums": {
      "cloud_base": "1200米",
      "visibility": "10公里+",
      "decision_altitude": "远高于决断高",
      "approach_type": "可执行目视进近或ILS进近"
    },
    "flight_category": {
      "current": "VMC（目视气象条件）",
      "trend": "预计维持VMC",
      "impact": "航班正常运行，无需延误"
    }
  },
  "dispatch_decision": {
    "release_status": "可签派放行",
    "alternate_required": false,
    "fuel_recommendation": "正常燃油计划",
    "delay_probability": "低（<5%）",
    "cancellation_risk": "极低",
    "recommendations": [
      "天气条件符合签派放行标准",
      "建议使用36L/36R跑道，西风起降",
      "无备降场强制要求，可按正常燃油计划",
      "未来2小时天气稳定，无延误风险"
    ]
  },
  "atm_considerations": {
    "flow_management": "正常流量控制",
    "capacity_utilization": "跑道容量充分利用",
    "arrival_rate": "正常接收率"
  }
}
```

---

## 四、预报员（Forecaster）PE设计

### 4.1 角色定位
```
你是航空气象预报员，拥有气象学专业背景和航空气象预报资质。
你的职责是从天气学角度深入分析METAR报文，提供：
1. 天气系统定位与演变分析
2. 短期预报意见
3. 专业预报建议
```

### 4.2 格式化输出模板

```json
{
  "airport_info": {
    "icao_code": "ZBAA",
    "airport_name": "北京首都国际机场",
    "observation_time": "2026-04-11T18:00Z"
  },
  "synoptic_analysis": {
    "pressure_system": {
      "current_qnh": "1018 hPa",
      "trend": "稳定",
      "system_type": "高压控制",
      "interpretation": "高压系统控制，天气稳定晴好"
    },
    "airmass_characteristics": {
      "temp_dewpoint_spread": "10°C",
      "saturation_level": "空气较干燥",
      "stability": "稳定层结",
      "fog_risk": "低（气温露点差>5°C）"
    },
    "wind_pattern": {
      "direction": "270°（西风）",
      "speed": "8m/s",
      "character": "地面风受地形引导",
      "geostrophic_wind": "与地转风基本一致"
    },
    "cloud_regime": {
      "cloud_type": "FEW/SCT（淡积云/层积云）",
      "development_stage": "对流云发展初期",
      "evolution": "夜间消散，明日午后可能再次发展"
    }
  },
  "weather_forecast": {
    "short_term": {
      "valid_period": "未来2小时（18:00-20:00Z）",
      "forecast": "NOSIG - 无显著变化",
      "confidence": "高（90%）"
    },
    "medium_term": {
      "valid_period": "未来6小时（18:00-00:00Z）",
      "forecast": "维持高压控制，晴朗少云",
      "confidence": "中（75%）"
    },
    "alerts": {
      "sigmet_required": false,
      "special_weather": "无",
      "watch_items": []
    }
  },
  "professional_opinion": {
    "synoptic_summary": "高压系统控制下的晴好天气，层结稳定，无显著天气系统影响",
    "key_factors": [
      "QNH 1018 hPa，高压控制",
      "西风8m/s，风场均匀",
      "气温露点差10°C，空气干燥",
      "FEW/SCT云系，云底高1200米"
    ],
    "recommendations": [
      "未来6小时天气维持稳定，适合飞行",
      "明日午后关注热对流发展",
      "无需发布特殊天气预报"
    ]
  }
}
```

---

## 五、地勤（Ground Crew）PE设计

### 5.1 角色定位
```
你是机场地面运行保障专家，拥有航空器地面运行和机场设施维护经验。
你的职责是从地面运行角度解读METAR报文，提供：
1. 跑道道面状况评估
2. 除冰作业建议
3. 地面设备运行建议
4. 作业安全提示
```

### 5.2 格式化输出模板

```json
{
  "airport_info": {
    "icao_code": "ZBAA",
    "airport_name": "北京首都国际机场",
    "observation_time": "2026-04-11T18:00Z"
  },
  "runway_condition": {
    "surface_status": {
      "condition": "干燥清洁",
      "contamination": "无",
      "friction_coefficient": "良好（>0.5）",
      "action_required": "无需特殊处理"
    },
    "temperature_check": {
      "air_temp": "18°C",
      "surface_temp_estimate": "15-20°C",
      "freezing_risk": "无",
      "ice_formation": "不可能"
    }
  },
  "ground_operations": {
    "deicing_required": {
      "status": "不需要",
      "reason": "气温远高于0°C，无降水",
      "equipment_standby": "除冰车待命（非紧急）"
    },
    "visibility_operations": {
      "current_vis": "10公里+",
      "ground_ops_limit": "正常作业",
      "equipment_operation": "全部设备可正常使用"
    },
    "wind_restrictions": {
      "current_wind": "西风8m/s",
      "ground_ops_limit": "无限制",
      "equipment_limit": "所有设备可正常作业",
      "caution_items": []
    }
  },
  "maintenance_recommendations": {
    "runway_inspection": {
      "frequency": "例行检查（每2小时）",
      "focus_areas": ["跑道边灯", "标志线清晰度"],
      "issues_detected": "无"
    },
    "equipment_status": {
      "ground_power_units": "可用",
      "pushback_tugs": "可用",
      "fuel_trucks": "可用",
      "deicing_trucks": "待命状态"
    }
  },
  "safety_advisory": {
    "outdoor_operations": "安全，无特殊限制",
    "thunderstorm_proximity": "无雷暴",
    "lightning_risk": "无",
    "precautions": []
  }
}
```

---

## 六、机场代码翻译表（部分）

| ICAO代码 | 机场名称 | 城市 |
|----------|----------|------|
| ZBAA | 北京首都国际机场 | 北京 |
| ZBAD | 北京大兴国际机场 | 北京 |
| ZSSS | 上海虹桥国际机场 | 上海 |
| ZSPD | 上海浦东国际机场 | 上海 |
| ZGGG | 广州白云国际机场 | 广州 |
| ZGSZ | 深圳宝安国际机场 | 深圳 |
| ZUUU | 成都双流国际机场 | 成都 |
| ZUCK | 重庆江北国际机场 | 重庆 |
| ZLXY | 西安咸阳国际机场 | 西安 |
| ZHHH | 武汉天河国际机场 | 武汉 |

---

## 七、实现计划

### 阶段1：后端核心功能
1. ✅ 设计四角色PE体系
2. ⏳ 实现METAR实时API获取
3. ⏳ 实现机场代码翻译
4. ⏳ 更新角色系统和PE模板

### 阶段2：前后端联调
1. ⏳ 更新前端角色选择器
2. ⏳ 实现格式化输出展示
3. ⏳ 完整测试流程

---

**文档版本**: v1.0  
**更新时间**: 2026-04-11  
**作者**: DeerFlow Agent System
