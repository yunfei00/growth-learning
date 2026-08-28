# English Foundation V1

Phase 19 把英语作为独立 `subject=english` 接入 Growth Learning，同时沿用 Phase 16 的
Knowledge / Course / Evidence / Mastery 主干。产品顺序是：

```text
听声音 → 看图片、颜色、图形或动作理解 → 选择 → 在生活中使用
                                    └── 字母名称 / 字母声音 / CVC 拼读分别学习
```

V1 不把英语缩成“背单词 + 中英互译”，也不把词汇数当作唯一结果。听懂、意义理解、开口、
字母识别、字母名称、音素辨别、blending 和 decoding 分维度保存。

## 目录与课程

`english-foundation-v1` 是项目自有、人工维护的 starter catalog，不宣称来自某套官方教材：

- 132 个常见词汇，覆盖动物、身体、颜色、家庭、玩具、食物、动作、数字、图形、自然等主题；
- 26 个字母，明确区分 uppercase、lowercase 与 letter name；
- 44 个 phonics 项：5 个短元音、19 个基础辅音开头音和 20 个 CVC blending 项；
- 15 个简单表达/短句；
- 21 个 Course Unit；共 217 个 KnowledgePoint、375 个确定性练习模板。

稳定身份由 `canonical_key` 和 UUIDv5 生成。再次导入只更新人工字段，不复制 KnowledgePoint、
PracticeItem 或 Course。目录上限由代码断言与自动化测试锁定，避免把任意词形组合膨胀成知识点。

## 音频与视觉

默认口音固定为 `en-US`，解析顺序为：正式 curated object → 受控 TTS/安全示例词 → 明确不可用。
普通词汇、字母名称和短句可在没有正式录音时使用固定 `en-US` speech text。Phonics 有严格边界：

- 正式音素音频存在时播放正式资源；
- 缺失时只播放人工配置的完整示例词并提示家长关注目标位置；
- CVC blending 可播放完整 CVC 词；
- 绝不播放字母名称来假装目标音素；没有安全示例词时明确标记 unavailable。

视觉资源优先使用项目静态 SVG；颜色与图形用可审计的 CSS 表示；其余由人工 `visual_key` 回退。
每一项保存 source、license 和 attribution。首批静态 smoke 词为 cat、dog、apple、ball、sun、moon。

## 练习、测评与原始证据

儿童页每屏只显示一个主要问题。`english-generator-v1` 由 template + seed + version 确定生成并保存
prompt/options/expected answer 快照。听音选图、看图选音、字母配对、大小写配对、phonics 辨音、
CVC blending 和短句听力都不依赖 AI。

`EnglishExerciseAttempt` 保存 first/submitted answer、重试次数、显式提示、声音重播次数、响应时间、
actor/evaluator 与结果。声音重播不是提示；显示中文解释才是提示。Practice 可以重试，只生成
`LearningRecord`；Assessment 只接受首次答案，结束后聚合为 `AssessmentItem`。通用 assessment API
拒绝英语知识点，防止绕过确定性题目和证据规则。

家长可以保存“愿意跟读 / 能自然说 / 需要提示 / 暂时不说”的口语观察。V1 不使用自动发音评分，
口音和速度不参与掌握度。

## Mastery 与复习

四类内容分别注册策略：

| KnowledgeType | policy key | 核心维度 |
| --- | --- | --- |
| `english_word` | `english-word-v1` | listening + meaning |
| `english_letter` | `english-letter-v1` | letter_name + case_matching |
| `english_phonics` | `english-phonics-v1` | sound_recognition；有 decoding evidence 后以 decoding 为核心 |
| `english_phrase` | `english-phrase-v1` | listening + meaning |

单维度至少两个不同日期的独立正确才到 proficient；至少三次、三个不同日期、跨度七天且最近一次仍
独立正确才到 stable。同一天重复作答永远不能得到 stable。Speaking/expression 是可见的独立维度，
但不是词汇或短句稳定掌握的硬门槛。复习投影使用 `english-review-v1`，Today 使用
`english-plan-v1`，每天最多 3 个新内容和 6 个到期复习，估时保持在 5～10 分钟。

## 家庭边界与运维

目录对家庭共享，证据、Today、History、Mastery 与 Review 全部按 `child_id` 隔离。同一家庭的有效
成员可以协作并看到真实 actor；兄弟姐妹不共享进度；退出家庭后立即失去访问。System Admin 只能
维护 `/admin/english` 的目录、资源和状态，不因管理员角色获得家庭私有数据，也不能直接修改孩子
mastery。

部署顺序为备份 → Alembic additive migration → `import_english_foundation` → 健康检查 → 登录态
Child smoke。生产 smoke 至少覆盖 cat/dog/red/blue、A/a、phonics m 和 CVC cat，并确认重新打开后
原始 attempt、历史与今日完成状态仍存在。
