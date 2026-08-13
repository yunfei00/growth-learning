# Phase 6 AI 故事与汉字覆盖策略

本文定义可版本化、可解释、无需信任模型自报值的 Story Policy V1。AI 不参与 Mastery、复习、识字估算或证据判定。

## 字符集合

- 强掌握：`ChildKnowledgeState.mastery_level ∈ {proficient, stable}`。
- 可用识别：`recognizing`，单独保存并计数，不能冒充 strong known。
- 目标/巩固：家庭手选的 2–5 个 enabled 字，或按 priority、近期错误/不确定、低分与时间确定性排序的 introduced/recognizing/proficient 候选。
- 识字量估算不能证明某个具体字已知，因此不进入故事允许字集合。

每次生成物化 knowledge point ID、字符、当时 mastery level、snapshot timestamp 和 catalog size。当前状态改变不更新旧快照。

## Difficulty / Coverage Policy V1

| 难度 | 目标 known | 接受 known 区间 | target 区间 | unexpected 上限 | 最少 occurrence / unique / strong known |
| --- | ---: | ---: | ---: | ---: | ---: |
| Beginner | 95% | 90–98% | 2–10% | 3% | 30 / 8 / 20 |
| Normal | 90% | 84–94% | 6–16% | 4% | 40 / 10 / 30 |
| Challenge | 80% | 72–86% | 12–25% | 6% | 50 / 12 / 40 |

目标值不是最终展示值。系统始终保存并显示程序计算的实际 strong known、usable known、target、unexpected occurrence coverage 与 unique known coverage。强掌握不足时明确拒绝该难度，建议降低难度、陪读或继续识字；不为比例生成重复字垃圾文本。

## Han Character Coverage Analyzer V1

- 分析范围包含标题和按顺序拼接的故事段落，不含理解题。
- 提取 Unicode `U+3400–U+4DBF` 和 `U+4E00–U+9FFF`；稳定忽略标点、空白、拉丁字母和阿拉伯数字。
- 分类优先级：target → strong known → recognizing usable → unexpected，避免一个 occurrence 重复计数。
- 分别保存总汉字 occurrence、不同汉字 unique、各分类 occurrence 与 unexpected 字符列表。
- 版本：`han-coverage-v1`；策略：`story-coverage-v1`。

## AI Story Generation Contract V1

1. 建立孩子字符级快照并验证难度资格。
2. 验证 curated theme / 短自定义主题和 2–5 目标字。
3. 只发送年龄段、主题、难度、允许字、目标字和结构化 JSON schema。
4. Provider 必须返回 title、paragraphs、可选 summary、2–3 个带 options/correct index 的问题。
5. Pydantic 正式校验；内容基础安全检查；应用分析覆盖率和目标字实际出现。
6. 不合格时把非敏感 reason code 加入 repair 请求，最多总计 3 次。
7. 仍不合格则保存失败类别并向家长显示可操作错误；绝不无限重试。
8. 合格后保存不可变 StoryVersion、问题、字符使用和 GenerationRun。

Prompt/Analyzer/Policy 版本分别为 `story-prompt-v1`、`han-coverage-v1`、`story-coverage-v1`。GenerationRun 可保存用量和延迟，但不保存 API key、chain-of-thought 或 Provider 原始错误。

## 隐私与儿童安全

发送：派生年龄段（如 5～6 岁）、安全主题、难度、允许汉字、目标汉字、JSON 合同。

不发送：孩子姓名/昵称、完整生日、家庭信息、家长邮箱、成长笔记、照片、成员信息、会话 token 或任何 secret。

V1 使用 curated theme、年龄约束 Prompt、中英文高风险短语基础拒绝、结构校验和输出 sanity check。关键词过滤不是完整内容安全系统，因此产品仍是家长介入/可见的陪伴模式，不是孩子开放式 AI 聊天。

## 阅读证据边界与当前限制

读完只为目标字追加 `story_exposure` LearningRecord；它可以支持 introduced/exposure 历史，但绝不创建 `AssessmentItem.correct`。理解题结果也不等价于认字证据或心理/能力标签。

当前允许字符来自项目自有 200 字 Starter Catalog，不是完整儿童汉字体系。后续扩充目录时，旧 StoryVersion 的 snapshot、覆盖率和当时实际内容保持不变。
