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

路径页允许多项总览和任意入口；真正的学习页一次聚焦一个大符号，并依次呈现“目标拼音 → 声调动作 → 怎么读 → 拼一拼 → 例子”。目标发音、中文教学说明和例词是三个独立语义，只有目标发音可进入主播放、跟读与听音选择。整体认读明确显示“直接读出来”，不伪装为普通声韵拼读。

## 数据流

```text
pinyin-foundation-v2
  → KnowledgePoint + PinyinItem
  → 16 Unit system Course
  → child learning / listening / observation
  → LearningRecord + AssessmentItem
  → pinyin-v1 ChildKnowledgeState
  → pinyin-review-v1 ChildReviewSchedule
  → small persisted PinyinDailyPlan
```

播放声音、打开卡片和拼读动画本身不是答对证据。只有明确完成学习才创建 `LearningRecord`；听音选择、家长观察或拼读结果才创建对应维度 `AssessmentItem`。

听音选择只有在目标音频实际开始播放后才展示选项。教学说明或例词不会作为 fallback，因此孩子不能借“第四声，大树的大”等中文提示猜答案。目录语义升级不会清理或重算既有 LearningRecord、Assessment、daily plan、course progress 或 mastery。

## 家庭协作与隔离

所有状态和 Today 以 `child_id` 隔离。切换 Child 会重新读取目录状态、记录、复习和任务。任何同一家庭成员都读取同一 Child 的投影，同时每条学习记录保存 `actor_user_id`，每条测评保存 `evaluator_user_id`；跨家庭请求统一隐藏为 `404`。

## 汉字回归边界

拼音虽然属于 Chinese subject，但不是 `ChineseCharacter`。识字分母、汉字路径、汉字 Review、Story Han coverage 和汉字成就都继续通过 `ChineseCharacter` join 或 `knowledge_type=chinese_character` 收口，不能把 68 个拼音项加入 1200 字口径。
