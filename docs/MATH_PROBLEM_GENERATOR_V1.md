# Math Problem Generator V1

生成版本为 `math-generator-v1`。每道题由以下三元组确定：

```text
MathProblemTemplate + seed + generator_version
```

Registry 使用小型 Python handler，不实现通用 DSL。V1 handler 覆盖数量选择、数字匹配、比较、数序、
分解组合、合起来、拿走、规律、图形、空间、分类和直观测量。所有选项顺序由 seed 控制；同一 seed
可重建相同 render payload 和 expected answer。

生成器保证答案唯一、干扰项邻近、范围受控、减法不为负、正确位置不固定。前端从不使用
`Math.random()` 生成题目，也不接收 expected answer。AI 不能作为数字答案权威；若未来生成生活题，
后端必须独立重算并拒绝不一致结果。
