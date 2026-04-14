# 航空气象 Agent 执行计划

> 日期: 2026-04-14

## 文档目标

本文档只定义：
1. 一轮修改如何执行
2. 一轮评测如何执行
3. 失败样本如何回流
4. 报告如何更新

---

## 标准案例

案例 1：飞行员询问虹桥机场天气

```
输入：
- role = pilot
- query = 虹桥机场天气怎么样

期望行为：
- 调用机场天气 API
- 获取实时天气
- 提取飞行员关注点
- 输出简洁建议

失败判定：
- 未调用 API
- 输出成固定模板
- 未提炼飞行员关注点
- 只复述天气，不给建议
```

这条链路是所有执行和评测的基准。每一轮修改都围绕这条链路展开。

---

## 单轮执行流程

```
Step 1. 选择一个优化点
        例如：
        - 改写飞行员角色输出策略
        - 收紧关键风险判断
        - 减少模板化输出

Step 2. 执行修改
        - 修改代码 / 配置 / prompt 架构

Step 3. 跑 smoke + core regression + badcase regression
        - 验证是否破坏主链路
        - 验证历史 badcase 是否修复

Step 4. 记录结果
        - 任务完成率
        - 关键信息命中率
        - 输出可用率
        - badcase 回归通过率
        - 幻觉率
        - 延迟 / 成本

Step 5. 更新 badcase 池
        - 新失败样本入池
        - 已修复样本打标

Step 6. 更新项目报告
        - 写入本轮 delta
        - 写明收益与副作用

Step 7. 决定保留还是回退
```

一次完整的单轮执行就是 Step 1 → Step 7。多轮改进就是多次循环这个流程。

---

## badcase 处理流程

1. 每次 E2E run 后自动检查：
   - 任务是否完成
   - 是否命中关键信息
   - 输出是否可用
   - 是否模板化
   - 是否出现幻觉

2. 不通过则自动生成 badcase 记录

3. badcase 分类：
   - `task_not_finished`
   - `critical_info_missed`
   - `output_too_template`
   - `hallucination`
   - `other`

4. 经确认的 badcase 自动进入回归集

5. 每轮修改后，badcase regression 必跑

---

## 评测执行

每次 Step 3 时执行：

```
开发者 git push
    ↓
pre-push hook触发 (~3分钟)
    ↓
┌─────────────────────────────────────────┐
│ L1 标准集 (50条，必须全部通过)            │
│ L2 边界集 (100条，允许5%失败)             │
│ L3 抽样20条 (幻觉+关键信息+可用性)        │
└─────────────────────────────────────────┘
    ↓
  L1全部通过 + L2失败<5% + L3通过 → ✅ 允许push
  否则 → ❌ 拒绝push + 输出失败详情
```

评测频率：

| 场景 | 跑哪些集 | 耗时 |
|------|---------|------|
| git push | L1+L2+L3抽样 | ~3分钟 |
| PR merge | 全部+对抗集 | ~5分钟 |
| 发版前 | 全部+hold-out+人工质检 | ~15分钟 |

---

## Review 重点

本项目优先 review 的不是代码风格，而是结果质量：
- 任务有没有做完
- 建议有没有用
- 输出是不是模板化
- 关键风险有没有漏报
- 历史 badcase 有没有复发

代码 review 质量检查清单：
- 改了什么：`git diff --cached --stat`
- 安全扫描：secrets / injection / eval
- 基线测试对比：新失败 vs 旧失败
- badcase 回归通过率

---

## 开发工作流（Claude Code 三层 Hook）

以下 Hook 是用 Claude Code 开发这个 Agent 时的**开发工具**，不是 Agent 本身的功能。它们保证"改 Agent 代码时"的质量和安全。

### 第一层：安全网 — 写代码时的保护

- 拦截危险命令（rm -rf, force push 等）
- 锁住敏感文件（.env, credentials 等）
- 自动格式化（ruff format + ruff check --fix）

配置位置：`.claude/settings.json` → PreToolUse / PostToolUse hooks

### 第二层：改后即测 — 代码一落地就验证

- 改 .py 文件后自动跑关联测试
- 测试失败 → 阻断代码操作
- AI 写完代码先自查一遍（requesting-code-review skill）
- PR 强制测试通过才能 merge（GitHub Actions PR Gate）

效果：带 bug 的代码进不去，代码质量有保障。

### 第三层：规范 + 日志 — 提交前消灭问题

- pre-commit: ruff lint + mypy 类型检查
- 操作日志: 每步操作写 `.hermes/ops_log.jsonl`（记录时间戳和结果）
- auto-commit: git diff → LLM 生成规范 commit message（提交信息不再将就）

效果：整个开发工作流更顺心，不用手动记操作、手动写 commit。

### 三层 Hook 在哪里

- `.claude/settings.json` → PreToolUse / PostToolUse hooks
- `.git/hooks/pre-commit` 或 pre-commit 框架
- `.github/workflows/pr-gate.yml` → PR Gate
- `scripts/hooks/` → 拦截/测试/格式化/日志脚本
