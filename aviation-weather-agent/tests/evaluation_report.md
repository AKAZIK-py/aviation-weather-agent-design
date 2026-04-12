============================================================
航空气象Agent PE评测报告
============================================================

## 总体指标
- 总测试场景: 60
- 成功调用: 60
- 失败调用: 0
- 平均响应时间: 5.21ms

- **准确率 (Precision)**: 15.00%
- **召回率 (Recall)**: 3.61%
- **F1 Score**: 5.83%

## Bad Cases

### LOWVIS_001 (角色: pilot)
- 缺失字段: ['key_risks', 'flight_rules', 'weather', 'visibility_m']
- 错误匹配: ['risk_level']

### LOWVIS_002 (角色: pilot)
- 缺失字段: ['visibility_m', 'flight_rules', 'weather']
- 错误匹配: ['risk_level']

### LOWVIS_003 (角色: pilot)
- 缺失字段: ['visibility_m', 'flight_rules', 'weather']
- 错误匹配: ['risk_level']

### LOWVIS_004 (角色: pilot)
- 缺失字段: ['visibility_m', 'flight_rules', 'weather']
- 错误匹配: ['risk_level']

### WIND_001 (角色: pilot)
- 缺失字段: ['wind_speed_kt', 'flight_rules', 'weather', 'wind_gust_kt']
- 错误匹配: ['risk_level']

### WIND_002 (角色: pilot)
- 缺失字段: ['flight_rules', 'wind_speed_kt', 'wind_shear', 'wind_gust_kt']
- 错误匹配: ['risk_level']

### WIND_003 (角色: pilot)
- 缺失字段: ['wind_speed_kt', 'flight_rules', 'weather', 'wind_gust_kt']
- 错误匹配: ['risk_level']

### TSTORM_001 (角色: pilot)
- 缺失字段: ['visibility_m', 'flight_rules', 'weather']
- 错误匹配: ['risk_level']

### TSTORM_002 (角色: pilot)
- 缺失字段: ['flight_rules', 'weather']
- 错误匹配: ['risk_level']

### TSTORM_003 (角色: pilot)
- 缺失字段: ['visibility_m', 'flight_rules', 'weather']
- 错误匹配: ['risk_level']