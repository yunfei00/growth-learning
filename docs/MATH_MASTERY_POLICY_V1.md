# Math Mastery Policy V1

策略键为 `math-v1`，只处理 `math_skill + math_check`。核心维度为：

- `understanding`：理解数量、关系或操作含义。
- `independent`：首次回答、不依赖明显提示。
- `transfer`：数字、图片、排列、场景或 representation 改变后仍能完成。

Practice 不产生正确测评。Proficient 至少需要同一 Skill 中 2 道首次独立正确的问题证据。Stable
至少需要 6 道首次独立正确问题、3 个独立 Check、3 个自然日、至少 7 天跨度、3 种
独立正确的 representation，并且最近一条证据仍为无提示成功。同日重复最多到 Proficient；提示后
正确或错误题目中出现的新 representation 不能凑出迁移掌握。
`response_time_ms` 只用于异常和 UX 研究，不影响分数或状态。

复习策略为 `math-review-v1`，间隔从 1/3/7/14/30 天递进；复习使用新的 seed 和可用的不同
representation，不能把记住原题当成迁移。
