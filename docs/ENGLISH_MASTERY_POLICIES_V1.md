# English Mastery Policies V1

Phase 19 注册四个确定性策略：`english-word-v1`、`english-letter-v1`、
`english-phonics-v1`、`english-phrase-v1`。它们不调用 AI，也不共享一个粗粒度英语总分。

核心维度分别为 listening+meaning、letter_name+case_matching、sound_recognition（出现 decoding
evidence 后以 decoding 为核心）、listening+meaning。Speaking/expression 独立显示，但不是词汇或
短句 stable 的硬门槛。

单维度状态规则：有 evidence 为 practicing；至少两个不同自然日的独立正确为 proficient；至少三次
独立正确、三个不同自然日、跨度至少七天且最近一次仍独立正确为 stable。提示后正确、同日重复和
音频重播都不能制造 stable。四种策略写入通用 `ChildKnowledgeState`，复习使用
`algorithm_version=english-review-v1`；不新增平行英语 mastery 表。
