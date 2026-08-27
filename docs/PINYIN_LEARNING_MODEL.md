# Pinyin Learning Model V1

## 目标与边界

拼音是语文内容：所有拼音 `KnowledgePoint.subject` 固定为 `chinese`。产品学习顺序是“听 → 看 → 跟读 → 辨音 → 拼读 → 复习 → 稳定掌握”，不是一屏字母表，也不是英文式字母朗读。

V1 不做儿童语音自动评分、语音诊断、手写识别、排行榜或全量音节背诵。AI 不能生成 canonical 规则、Assessment correct 或直接修改 mastery。

## 产品结构

```text
学习
└── 语文
    ├── 识字
    ├── 拼音
    │   ├── 声母
    │   ├── 韵母
    │   ├── 声调
    │   ├── 整体认读
    │   └── 拼读练习
    └── 阅读
```

路径页允许多项总览和任意入口；真正的学习页一次聚焦一个大符号，提供中文语音、例子、提示、前后导航和听音选择。整体认读明确显示“直接读出来”，不伪装为普通声韵拼读。

## 数据流

```text
pinyin-foundation-v1
  → KnowledgePoint + PinyinItem
  → 16 Unit system Course
  → child learning / listening / observation
  → LearningRecord + AssessmentItem
  → pinyin-v1 ChildKnowledgeState
  → pinyin-review-v1 ChildReviewSchedule
  → small persisted PinyinDailyPlan
```

播放声音、打开卡片和拼读动画本身不是答对证据。只有明确完成学习才创建 `LearningRecord`；听音选择、家长观察或拼读结果才创建对应维度 `AssessmentItem`。

## 家庭协作与隔离

所有状态和 Today 以 `child_id` 隔离。切换 Child 会重新读取目录状态、记录、复习和任务。任何同一家庭成员都读取同一 Child 的投影，同时每条学习记录保存 `actor_user_id`，每条测评保存 `evaluator_user_id`；跨家庭请求统一隐藏为 `404`。

## 汉字回归边界

拼音虽然属于 Chinese subject，但不是 `ChineseCharacter`。识字分母、汉字路径、汉字 Review、Story Han coverage 和汉字成就都继续通过 `ChineseCharacter` join 或 `knowledge_type=chinese_character` 收口，不能把 68 个拼音项加入 1200 字口径。
