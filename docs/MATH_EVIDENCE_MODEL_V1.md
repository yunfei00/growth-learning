# Math Evidence Model V1

三层证据职责：

- `MathExerciseAttempt`：题目级原始事实，保留模板、seed、快照、标准答案、首次/最终答案、提示、
  重试、耗时和 actor/evaluator。
- `LearningRecord`：Practice 中完成一个 Skill 学习活动的 canonical 接触事实。提示后最终答对不会
  被包装成测评正确。
- `AssessmentItem`：Check 中多道题结束后的 Skill 级聚合证据，保留结果、维度、representation、
  首次独立正确数量和 attempt IDs。

真实物品活动没有虚构题目 snapshot；家长通过专用 offline observation 入口记录“独立完成 / 需要提示 /
暂时不会”，产生带 `offline_objects` representation 的 `AssessmentItem`。单条家长观察不能直接成为
Stable。通用 Assessment API 拒绝 math_skill，避免绕过确定性 Math session 伪造 correct。

Assessment 第一次提交后不能覆盖。Practice 可以重试，但 `first_answer` 和 `attempt_count` 永久保留。
多家长看到同一 Child 的历史并保留真实 actor；兄弟姐妹和不同家庭完全隔离。平台 System Admin
只能维护公共目录，不能读取孩子私有历史。
