# 航空气象 Agent — 项目报告

> 生成日期: 2026-04-14
> 项目位置: /Users/twzl/aviation-weather-projects/aviation-weather-agent

---

## 本轮结论摘要

本轮修改目标：
- 减少飞行员场景中的模板化输出
- 提高"机场天气问答"类任务的输出可用率
- 将失败样本自动沉淀到 badcase 回归集

本轮结果：
- 任务完成率：xx → xx
- 关键信息命中率：xx → xx
- 输出可用率：xx → xx
- badcase 回归通过率：xx → xx
- 幻觉率：xx → xx
- P95 延迟：xx → xx

---

## 指标变化

| 指标 | Baseline | Current | Delta |
|------|----------|---------|-------|
| 任务完成率 | xx | xx | +x |
| 关键信息命中率 | xx | xx | +x |
| 输出可用率 | xx | xx | +x |
| badcase 回归通过率 | xx | xx | +x |
| 幻觉率 | xx | xx | -x |
| P95 延迟 | xx | xx | +/- |

---

## 模板化输出专项

本轮重点不是让系统输出更长，而是让系统输出更贴问题。

重点检查：
- 是否还在输出固定栏目
- 是否还在长篇复述天气
- 是否直接给出适合飞行员使用的建议

结果：
- 模板化严重样本数：xx → xx
- 飞行员场景输出可用率：xx → xx

---

## badcase 修复情况

本轮新增 badcase：x 条
本轮修复 badcase：x 条
累计 badcase 回归通过率：xx%

代表性已修复问题：
1. 飞行员问机场天气时，输出整套固定模板
2. 只复述天气，不给飞行建议
3. 天气 API 已调用，但没有转化为角色相关建议

仍未解决：
1. 边界天气下建议还不够稳
2. 个别样本仍有模板腔

---

## 典型案例前后对比

### Case: 飞行员询问虹桥机场天气

旧版本输出问题：
- 固定模板
- 信息过多
- 建议不直接

新版本输出目标：
- 先给结论
- 再给关键天气点
- 最后给飞行员建议
- 不输出统一模板结构

---

## 附录

- 代码结构：见 `aviation-weather-agent/` 目录树
- 评测集路径：`eval/datasets/`
- badcase 存储路径：`eval/badcases/`
- 运行命令：`python3 -m pytest tests/ -q` / `sh scripts/evals/run_eval.sh`
