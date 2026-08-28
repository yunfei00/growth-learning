# English Vocabulary Evidence V1

英语题目由 `EnglishPracticeItem` 的 template、seed 和 `english-generator-v1` 生成。每个
`EnglishExerciseAttempt` 保存 prompt/options/expected answer 快照、first/submitted answer、重试、
显式提示、音频重播、响应时间、actor/evaluator 和结果。

- Practice 允许重试；完成一组后最多创建一条 `LearningRecord`，绝不创建 `AssessmentItem`。
- Assessment 只接受一次答案；完成一组后聚合为一条 `AssessmentItem`。
- 通用 assessment API 拒绝四种英语 KnowledgeType，不能绕过确定性题目直接提交正确结果。
- 音频重播独立计数，`replay_is_hint=false`；中文线索才算提示。
- 家长口语观察保存为 `oral_check`，metadata 明确 `automatic_speech_score=false`。

词汇维度为 listening、meaning、speaking；字母、phonics、短句拥有各自维度。原始 evidence 是权威
事实，`ChildKnowledgeState` 与 Review 都能从原始记录重建。家庭成员共享同一孩子证据并保存真实
陪伴人；兄弟、跨家庭、已移除成员和 System Admin 都不能读取不属于自己的孩子历史。
