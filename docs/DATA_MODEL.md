# Growth Learning 数据模型

本文描述目标领域模型，不代表 Phase 1 会一次创建所有表。首阶段只建立 ORM 与迁移基础；正式表应随用例逐步落地，并为每次迁移补充约束与回滚评估。

## 1. 约定

- 主键使用 UUID；时间使用带时区 UTC 时间戳。
- 家庭域表显式保存 `family_id`，查询必须受家庭边界约束。
- 可修改实体包含 `created_at`、`updated_at`；需要追溯的实体包含状态变更或审计信息。
- 原始学习事实采用追加式记录，不通过修改历史答案来“修正”当前状态。
- 枚举值以稳定机器码存储，展示文本由应用层本地化。
- JSON 只保存供应商元数据或版本化快照，不替代核心关系和约束。

## 2. 身份、家庭与授权

### User

登录主体：`id`、`email/phone`、`display_name`、`status`、身份提供方信息。敏感认证材料由专门身份机制管理。

### Family

家庭数据边界：`id`、`name`、`timezone`、`locale`、`status`。

### FamilyMember

连接 User 与 Family：`family_id`、`user_id`、`role`（parent/companion）、`status`、`joined_at`。唯一约束 `(family_id, user_id)`；至少一名有效管理员由业务规则保证。

### Child

家庭内儿童档案：`family_id`、`preferred_name`、`birth_date`（可选/最小化保存）、`learning_preferences`、`status`。Child 不要求关联登录账号；未来可选关联 User。

### Teacher

老师专业档案，关联一个 User：`user_id`、`display_name`、`organization`、`verification_status`。

### TeacherChildRelation

家长授予老师的有限权限：`teacher_id`、`child_id`、`granted_by_user_id`、`scopes`、`allowed_actions`、`valid_from`、`expires_at`、`revoked_at`。读取时必须验证时间和撤销状态；授权范围变更保留历史。

## 3. 课程与知识图谱

### Subject

学科或领域，例如 Chinese Literacy、Science：`code`、`name`、`status`。

### Ability

能力维度，例如识别、理解、书写、应用：`subject_id`、`code`、`name`、`description`。

### KnowledgePoint

通用、可版本化的最小学习单元：`subject_id`、`code`、`name`、`kind`、`content`、`difficulty`、`metadata`、`version`、`status`。汉字、词语、概念都通过 `kind` 表达。

### KnowledgeRelation

知识点有向关系：`source_id`、`target_id`、`relation_type`（prerequisite/part_of/related_to 等）、`weight`、`version`。禁止自环；有向无环要求仅对 prerequisite 子图成立并由服务校验。

### Course / CourseUnit / LearningActivity

- Course：课程集合、适用年龄/阶段和版本。
- CourseUnit：课程内有序单元，可表达先修关系。
- LearningActivity：实际可执行活动，关联一个或多个知识点、能力维度、内容版本与预估时长。

课程发布后保留版本；历史记录引用当时的活动版本，避免内容更新改变历史含义。

## 4. 学习事实与派生状态

### LearningRecord（原始事实）

一次学习行为：`child_id`、`activity_id/version`、`knowledge_point_id`、`ability_id`、`occurred_at`、`duration_seconds`、`result`、`attempt_data`、`source`、`idempotency_key`。

### AssessmentSession / AssessmentItem（原始事实）

- Session 保存测评类型、内容版本、开始/结束时间和环境。
- Item 保存题目快照、知识点、作答、正确性、响应时长、评分规则版本。

题目快照保证多年后仍能解释当时评分；估算值属于会话结果，不覆盖单题证据。

### ReviewRecord（原始事实）

实际发生的复习：`child_id`、`knowledge_point_id`、`schedule_id`（可选）、`occurred_at`、`prompt/result`、`response_time`、`quality`、`idempotency_key`。

### ReviewSchedule（可更新计划）

某知识点下一次复习建议：`child_id`、`knowledge_point_id`、`due_at`、`priority`、`reason_codes`、`algorithm_version`、`status`。它是调度投影，不是学习证据；重新计划不修改 ReviewRecord。

### ChildKnowledgeState（派生投影）

当前状态：`child_id`、`knowledge_point_id`、`ability_id`、`mastery_score`、`confidence`、`evidence_count`、`last_evidence_at`、`next_review_at`、`algorithm_version`、`evidence_through`、`computed_at`。

唯一约束 `(child_id, knowledge_point_id, ability_id)`。分数必须带置信度和算法版本，不能单独解释为事实。

### 为什么必须分离

`LearningRecord`、`AssessmentItem` 和 `ReviewRecord` 回答“发生过什么”，必须长期、稳定、可审计。`ChildKnowledgeState` 回答“按当前算法如何理解这些证据”，会随着新证据、衰减时间和算法升级而改变。

如果只保存 `mastery_score = 0.83`，系统无法解释分数、回放误判、升级复习算法或纠正旧逻辑。分离后可以按 `algorithm_version` 在后台重算状态，同时比较新旧结果而不破坏历史。

## 5. 阅读、实验与成长

### Story / ReadingSession

- Story 保存家庭/孩子可见范围、文本版本、目标知识点、允许字符集快照、供应商/模型/模板版本、规则校验结果和发布状态。
- ReadingSession 保存孩子实际阅读的故事版本、开始/完成时间、理解题作答和反馈。

### ScienceExperiment / ExperimentSession

- ScienceExperiment 保存版本化实验方案、年龄范围、材料、步骤、风险等级、安全要求和关联知识点。
- ExperimentSession 保存实际准备、执行、观察、结论、成人确认和媒体引用。

### GrowthEvent

统一时间线事件：`family_id`、`child_id`、`event_type`、`occurred_at`、`source_type/source_id`、`title`、`summary`、`visibility`。可引用学习里程碑、实验、作品或人工记录，但不复制全部源数据。

### GrowthReport

周期性、可重建报告：`child_id`、`period_start/end`、`generator_version`、`evidence_through`、`content_snapshot`、`status`、`published_at`。

### MediaAsset

对象存储元数据：`family_id`、`owner_type/id`、`bucket`、`object_key`、`mime_type`、`size`、`sha256`、`purpose`、`status`。bucket 保持私有，对象键使用不可猜测 ID。

## 6. 主要关系

```text
User ──< FamilyMember >── Family ──< Child
User ── Teacher ──< TeacherChildRelation >── Child

Subject ──< Ability
Subject ──< KnowledgePoint ──< KnowledgeRelation >── KnowledgePoint
Course ──< CourseUnit ──< LearningActivity >── KnowledgePoint

Child ──< LearningRecord >── KnowledgePoint
Child ──< AssessmentSession ──< AssessmentItem >── KnowledgePoint
Child ──< ReviewRecord >── KnowledgePoint
Child ──< ChildKnowledgeState >── KnowledgePoint
Child ──< ReviewSchedule >── KnowledgePoint

Child ──< ReadingSession >── Story
Child ──< ExperimentSession >── ScienceExperiment
Child ──< GrowthEvent
Child ──< GrowthReport
Family ──< MediaAsset
```

## 7. 索引、分区与保留策略

- 高频事实表优先索引 `(child_id, occurred_at desc)`、`(child_id, knowledge_point_id, occurred_at desc)` 和幂等键。
- 所有授权查询索引有效状态与到期时间；所有家庭资源索引 `family_id`。
- 先使用普通 PostgreSQL 表；只有真实数据量和查询证据支持时，才按时间对事件表分区。
- 媒体生命周期与引用实体解耦：先标记删除，异步清理无引用对象并记录结果。
- 家庭导出包含版本化 JSON/CSV、媒体 manifest、时区和生成时间；导入不是 V1 承诺，但导出不得依赖专有二进制格式。

## 8. 数据演进规则

- Alembic 迁移只向前追加并经 CI 验证；生产迁移避免不可控的长锁。
- 破坏性字段变更采用 expand/migrate/contract，先兼容读写再清理旧字段。
- 算法重算使用新版本写入或原子替换投影，不修改原始事实。
- 课程、故事、题目和实验的已使用版本不可原地改写；发布新版本并让新会话引用它。

