# Phase 5 复习、每日计划与识字估算算法

本文记录 Phase 5 中所有影响复习时间、每日负荷、周期测评抽样和识字估算的确定性规则。算法不调用 LLM。`LearningRecord` 与 `AssessmentItem` 始终是权威原始证据；本文涉及的日程、计划和估算均可重建。

## Review Algorithm V1

版本：`review-v1`。

基础间隔阶梯为：

```text
1 → 3 → 7 → 14 → 30 → 60 → 90 天
```

系统按时间和证据 UUID 的稳定顺序重放某个孩子、某个知识点的全部学习与测评证据：

| 事件 | 阶段变化 | 原因代码 |
| --- | --- | --- |
| `introduced` / `relearned` / `parent_marked_seen` | 回到阶段 0，即 1 天 | `learning_or_relearning` |
| `correct` | 前进一个阶段，最高 90 天 | `independent_correct_progression` |
| `hinted_correct` | 后退一个阶段，最低 1 天 | `hinted_correct_shortened` |
| `uncertain` | 后退两个阶段，最低 1 天 | `uncertain_strongly_shortened` |
| `incorrect` | 回到阶段 0，即 1 天 | `incorrect_reset` |

一次独立认识最多前进一个阶段，不会跳到长期间隔。已经达到 `stable` 的知识点仍沿 60/90 天间隔接受维护复习。`is_priority` 只影响队列顺序，不改变间隔、掌握分数或掌握等级。

可通过下列命令从原始证据重建全部或指定孩子的日程：

```bash
python -m app.cli.review
python -m app.cli.review --child-id CHILD_UUID
```

该命令不更新或删除 `learning_records`、`assessment_items`。

## Daily Plan V1

版本：`plan-v1`。默认时区为 `Asia/Shanghai`，数据库时间戳仍使用 UTC。计划日期由孩子的 IANA 时区计算，不使用 UTC 00:00 直接切日。

每个 `(child_id, plan_date)` 只有一个 `DailyLearningPlan`。首次读取当日计划时固定选题，后续读取返回同一个计划，避免刷新后任务变化。`DailyPlanItem` 保存新字和复习字的确定选择及顺序。

复习队列只包含已经到期的启用知识点，按下列因素稳定排序：

1. 逾期时长；
2. 同等逾期程度下的家长重点复习标记；
3. 最近结果风险：`incorrect`、`uncertain`、`hinted_correct`、其他；
4. 到期时间和汉字目录顺序。

每日只选择 `daily_review_capacity` 项，默认 15。`due_count` 保存完整积压数量，未选项目保留在后续日期；`ceil(due_count / capacity)` 作为当前速度下的清理天数说明。

每日新字上限默认 5，实际建议按以下确定性阈值向下调整：

| 条件 | 建议新字数 |
| --- | --- |
| 上限为 0 | 0 |
| 积压达到每日容量的 2 倍 | 0 |
| 积压达到每日容量 | 最多 2 |
| 最近 7 天至少 5 个结果且独立认识率低于 50% | 最多 1 |
| 最近 7 天至少 5 个结果，独立认识率低于 75% 或“不确定+不认识”达到 30% | 最多 3 |
| 数据不足 5 项 | 家长上限 |
| 状态健康 | 家长上限 |

响应同时返回由规则模板生成的中文原因，不调用生成式 AI。当前日期计划创建后不会因当天设置变化而改写；新设置从下一个新计划生效。

## 可恢复测评会话

`daily_review`、`weekly_check`、`monthly_assessment` 均复用 `AssessmentSession` 和 `AssessmentItem`。`AssessmentSessionPlan` 记录抽样方法和字库范围，`AssessmentSessionTarget` 记录固定题目、顺序和抽样分层，但不保存答案。

每个已提交题目立即追加一个 `AssessmentItem`，并在同一事务内重算 `ChildKnowledgeState`、`ChildReviewSchedule` 和每日计划进度。同一会话、同一知识点不能再次提交。刷新或重新登录后继续未完成目标；只有全部固定目标都有证据时会话才能变为 `completed`。

## Periodic Assessment V1

抽样版本：`sampling-v1`。所有候选首先限定为当前启用字库，并按目录创建时间和汉字稳定排序。

周度小挑战最多 15 项，来自：

- 重点或较弱项目；
- 最近 30 天新接触项目；
- 少量稳定项目；
- 已学项目补足。

月度识字检测最多 50 项，来自：

- 重点或较弱项目；
- 稳定维护项目；
- 约 20% 系统从未正式教过的启用字；
- 已学项目和目录补足。

每个题目的 `sampling_class` 会永久保存在会话目标中，例如 `unseen_not_system_taught`，因此系统不会把月测发现误写成“以前教过”。答题证据仍只进入 `AssessmentItem`。

## Literacy Estimation V1

版本：`literacy-v1`。估算只针对测评当时的启用字库，不推断孩子的全部汉字识字量。

- 少于 20 个已作答月测项目：返回 `is_sufficient=false` 和“数据不足”，不返回估算值。
- `known_count` 只计独立 `correct`；提示后认识、不确定和不认识均不计为独立认识。
- 点估计：`round(known_count / sample_size × catalog_size)`。
- 区间：二项比例的 95% Wilson 区间乘以 `catalog_size`。
- 点估计及上下界始终限制在 `0..catalog_size`。

每条 `LiteracyEstimate` 保存当时的 `catalog_size`、`sample_size`、认识/未知数量、抽样方法与版本、点估计、上下界和算法版本。UI 必须同时显示 `/ catalog_size` 及以下限制说明：

> 该结果仅代表当前系统字库范围，不是孩子全部汉字识字量。
