# Pinyin Mastery Policy V1

## Policy

拼音使用独立 `policy_key=pinyin-v1`，不调用 `chinese-character-v1`。复习日程使用 `algorithm_version=pinyin-review-v1`。算法是确定性投影，不调用 AI；原始 `LearningRecord` 和 `AssessmentItem` 始终是权威事实。

内部状态为：

- `unlearned`：没有拼音 evidence；
- `introduced`：存在 LearningRecord，尚无测评；
- `practicing`：至少有一个 AssessmentItem，但核心维度未达到要求；
- `proficient`：每个核心维度至少两次独立正确，且分布在至少两个自然日；
- `stable`：每个核心维度至少三次独立正确，分布在至少三个自然日，并且首末成功间隔至少 7 天、最近一次不是失败。

同一天连续点击无论多少次都不能变成 `proficient` 或 `stable`。提示、犹豫和错误会被保存，但不计入独立正确次数。

## 维度与核心要求

| 类型 | 核心维度 | 可选辅助维度 |
| --- | --- | --- |
| 声母 | recognition + listening | blending、pronunciation |
| 韵母 | recognition + listening | blending、pronunciation |
| 声调 | tone + listening | recognition、pronunciation |
| 整体认读 | recognition + listening | pronunciation |
| 拼读练习 | blending | 作为相关声/韵母的独立练习 evidence，不要求声母靠 blending 才 Stable |

各维度状态分别保存在 `ChildKnowledgeState.dimensions_json`，一个维度的成功不会提升另一个维度。例如 recognition 稳定但 listening 仅一次尝试，整体仍是练习中。

## Evidence 来源

- `recognition`：成人观察孩子是否认出符号，或受控识别任务；
- `listening`：播放中文语音后，从少量大符号中选择；
- `tone`：声调听辨/识别；
- `blending`：孩子真实完成声母 + 韵母拼读后的成人记录；单纯播放动画不写 correct；
- `pronunciation`：只能由家长/老师观察，以 `oral_check` 保存，不是 AI 发音准确率。

所有投影都可从 raw evidence 重建。向后兼容的 `mastery_level` 将 `practicing` 映射为 `recognizing`，儿童 UI 始终显示中文状态。
