# Mastery V1 汉字掌握度算法

Mastery V1 是基于已保存原始证据的确定性算法。它不调用 AI，不根据年龄或姓名推断能力，也不把单次答对解释为长期掌握。算法版本保存为 `v1`。

Phase 16 后，本算法通过 `MasteryPolicyRegistry` 只注册给 `chinese_character`，策略键为 `chinese-character-v1`。拼音、数学、英语与科学可保存规范证据，但在各自策略完成验证前返回 `unavailable`，不生成 `ChildKnowledgeState` 或复习日程，也不把“算法未配置”显示为“未学习”。

## 输入证据

- 学习证据：`introduced`、`relearned`、`parent_marked_seen`。
- 测评证据：`correct`、`hinted_correct`、`uncertain`、`incorrect`。
- 反应时间只用于计算可解释的平均值，V1 不用它改变等级。
- 证据按 `assessed_at` 和 UUID 稳定排序；所有原始行永久保留。

## 分数

每种测评结果的权重：

| 结果 | 权重 |
| --- | ---: |
| `correct` | `+1.00` |
| `hinted_correct` | `+0.50` |
| `uncertain` | `-0.25` |
| `incorrect` | `-0.75` |

`mastery_score = clamp(weighted_sum / 4, 0, 1)`，保存到小数点后四位。学习证据本身不会增加正确分数，但会把知识从“未学习”推进到“已接触”。

## 五级规则

算法从低到高匹配，只有满足全部条件才进入更高等级：

| 等级 | 条件 |
| --- | --- |
| `unlearned` | 没有学习或测评证据 |
| `introduced` | 至少有一条证据，但不满足更高条件 |
| `recognizing` | 至少 1 次独立正确或 2 次提示后正确，且分数 ≥ 0.15 |
| `proficient` | 至少 3 次独立正确、末尾连续正确 ≥ 2，且分数 ≥ 0.50 |
| `stable` | 至少 4 次独立正确、发生在至少 3 个日期、首尾跨度 ≥ 7 天、末尾连续正确 ≥ 3，且分数 ≥ 0.80 |

`hinted_correct` 不计入独立正确次数。`uncertain`、`incorrect` 与提示后正确都会打断独立正确连续值；只有连续 `incorrect` 增加连续错误值。因此，新的错误证据可以让派生等级下降，但不会覆盖此前的正确证据。

## 重算

API 在每次批量写入后重算本次涉及的 `(child_id, knowledge_point_id)`。完整重算命令：

```bash
python -m app.cli.mastery
python -m app.cli.mastery --child-id CHILD_UUID
```

重算会覆盖所有派生计数、时间、分数和等级，保留家庭配置 `is_priority`，绝不更新或删除 `learning_records` 与 `assessment_items`。未来算法升级应增加新版本并通过相同证据做可比较重算。
