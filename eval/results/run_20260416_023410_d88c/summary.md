# 评测报告: run_20260416_023410_d88c

- 模式: `direct`
- 数据集: `standard_testset_v2.json`
- Commit: `bca2a3a`
- 时间: 2026-04-16T02:47:03.237677

## 汇总

| 指标 | 值 |
|------|-----|
| 总用例数 | 50 |
| 通过数 | 49 |
| 通过率 | 98.0% |
| 基础设施失败 | 1 |
| 格式失败 | 0 |
| 模型失败 | 0 |
| 平均延迟 | 15456ms |
| P95延迟 | 21335ms |
| 最大延迟 | 25905ms |
| 平均分 | 0.6829 |

## 门禁结果

**PASS** (阈值: 通过率 >= 90%)

## 失败用例

| case_id | error_type | error |
|---------|-----------|-------|
| STD_001 | infra_failure | import_error: Expecting value: line 1 column 2 (char 1) |
