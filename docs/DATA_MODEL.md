# Growth Learning 数据模型

本文记录已落地的数据模型与后续边界。Phase 9 在既有家庭、学习、阅读、科学与成长证据之上加入家长明确授权的教师协作；不包含学校管理、排行榜或开放式聊天。

## 通用约定

- 主键使用 UUID。
- `created_at`、`updated_at` 使用带时区时间戳，由数据库提供初始值。
- 家庭是最上层业务数据边界；所有家庭内资源必须通过成员关系鉴权。
- 孩子不是登录账户，也不继承 `User`。
- 年龄不入库，由 `birth_date` 按当前日期动态计算。
- 不提供孩子、家庭或学习证据的物理删除 API。长期数据删除/归档策略将在后续阶段单独设计。

## 已实现实体

### `users`

登录成年人账户。

| 字段 | 说明 |
| --- | --- |
| `id` | UUID 主键 |
| `email` | 规范化为小写；唯一约束和唯一索引 |
| `display_name` | 用户显示名称 |
| `password_hash` | Argon2 密码哈希；禁止 API 返回 |
| `is_active` | 兼容字段；数据库约束要求与 `account_status=active` 完全一致 |
| `account_status` | 权威状态：`active`、`suspended`、`disabled` |
| `system_role` | 平台角色：`user` 或 `admin`；注册默认 `user` |
| `registration_source` | `legacy`、`platform_invitation` 或 `admin_created` |
| `registered_via_invitation_id` | 可空平台邀请码关联；已有账号保持空值 |
| `last_login_at` | 最近一次成功登录时间 |
| `session_version` | JWT 会话撤销版本 |
| `created_at` / `updated_at` | 审计时间戳 |

密码、会话 token、密码哈希不得写入应用日志。数据库不保存明文密码。

`system_role=admin` 是平台管理权限，与 `family_members.role=admin` 完全独立。系统管理员不因平台角色自动获得任何家庭或孩子的访问权。

### `platform_invitations` / `platform_audit_logs`

`platform_invitations` 保存 HMAC-SHA256 `code_hash`、不可逆提示、用途、创建人、过期时间、最大/已用次数、可选邮箱约束、撤销与最后使用时间；不保存完整邀请码。注册事务用行锁原子消费。

`platform_audit_logs` 是追加式平台安全审计，保存 actor、可选 target、事件类型、时间和无 secret metadata。密码、邀请码明文、JWT 和基础设施 secret 禁止写入。

### `families`

家庭是权限和数据隔离边界，不直接保存 `user_id`。

| 字段 | 说明 |
| --- | --- |
| `id` | UUID 主键 |
| `name` | 家庭名称 |
| `created_at` / `updated_at` | 审计时间戳 |

### `family_members`

通过中间表连接 `users` 和 `families`，唯一约束为 `(family_id, user_id)`。

| 字段 | 说明 |
| --- | --- |
| `id` | UUID 主键 |
| `family_id` | 所属家庭 |
| `user_id` | 成年用户 |
| `role` | `admin` 或 `companion` |
| `created_at` / `updated_at` | 审计时间戳 |

角色能力：

- `admin`：查看家庭/成员/孩子；修改家庭；创建和修改孩子。
- `companion`：查看家庭/成员/孩子；不能修改家庭核心配置或孩子资料。

Phase 2 不实现邀请成员。正式邀请需要 token 生命周期、接受/拒绝、邮箱验证、撤销和审计，不使用“输入邮箱即加入”的临时实现。

### 教师协作（Phase 9）

`TeacherProfile` 是用户自愿开启的独立教师身份，既不是 `FamilyMember`，也不是 `System Admin`。`TeacherChildRelation` 记录家庭管理员对单一孩子的 active/revoked 授权，不把同一家庭的兄弟姐妹隐式包含在内。

| 表 | 作用 |
| --- | --- |
| `teacher_profiles` | 教师显示资料和 opaque、唯一、可轮换的 `teacher_code` |
| `teacher_child_relations` | 老师与单一孩子的家长授权、撤销和审计时间 |
| `classrooms` | 老师拥有的轻量班级及 opaque `class_code` |
| `classroom_memberships` | 家长确认的孩子入班/退出历史 |
| `teacher_assignments` | draft/published/closed/archived 任务及类型、截止时间 |
| `teacher_assignment_targets` | 任务目标孩子及创建时使用的授权关系 |
| `teacher_assignment_knowledge_points` | 按顺序引用 canonical `KnowledgePoint` |
| `teacher_assignment_progress` | pending/in_progress/completed 进度和 canonical session 引用 |
| `teacher_observations` | 老师原文、分类、时间及可选班级/任务关系 |
| `teacher_observation_knowledge_points` | 观察关联的 canonical `KnowledgePoint` |

教师任务不会建立 `TeacherMastery` 或平行分数。识字学习继续追加 `LearningRecord(source=teacher_assignment)`；认字检测继续追加四类 `AssessmentItem` 并记录 evaluator；阅读任务引用现有 `ReadingSession`。掌握度只由统一算法从这些原始 evidence 派生。教学观察只投影为 `GrowthEvent(source_type=teacher)`，不会直接改写 `ChildKnowledgeState`。

### `children`

家庭内的孩子成长档案。

| 字段 | 说明 |
| --- | --- |
| `id` | UUID 主键 |
| `family_id` | 所属家庭 |
| `display_name` | 正式显示名称 |
| `nickname` | 可选昵称 |
| `birth_date` | 出生日期，用于动态计算年龄 |
| `gender` | 可选：`male`、`female`、`other` |
| `avatar_key` | 可选的私有对象存储键 |
| `created_at` / `updated_at` | 审计时间戳 |

## 外键删除策略

首个迁移 `20260812_0001_create_identity_and_family_tables` 对每条业务外键显式采用 `ON DELETE RESTRICT`：

| 外键 | 删除策略 | 原因 |
| --- | --- | --- |
| `family_members.family_id → families.id` | `RESTRICT` | 不允许删除家庭时连带删除成员关系 |
| `family_members.user_id → users.id` | `RESTRICT` | 不允许删除账户时破坏家庭归属和审计边界 |
| `children.family_id → families.id` | `RESTRICT` | 不允许家庭操作级联删除多年孩子数据 |
| `chinese_characters.knowledge_point_id → knowledge_points.id` | `RESTRICT` | 禁止删除规范知识点时静默删除汉字内容 |
| `knowledge_relations.source_id → knowledge_points.id` | `RESTRICT` | 有关系引用时禁止删除源知识点 |
| `knowledge_relations.target_id → knowledge_points.id` | `RESTRICT` | 有关系引用时禁止删除目标知识点 |
| `learning_sessions.child_id → children.id` | `RESTRICT` | 不允许删除孩子时级联删除学习会话 |
| `learning_sessions.actor_user_id → users.id` | `RESTRICT` | 保留学习记录的成年人审计主体 |
| `learning_records.session_id → learning_sessions.id` | `RESTRICT` | 原始学习证据不能随会话静默删除 |
| `learning_records.child_id → children.id` | `RESTRICT` | 原始证据必须保留孩子归属 |
| `learning_records.knowledge_point_id → knowledge_points.id` | `RESTRICT` | 已使用知识不能物理删除 |
| `learning_records.actor_user_id → users.id` | `RESTRICT` | 保留学习证据创建者 |
| `assessment_sessions.child_id → children.id` | `RESTRICT` | 不允许级联删除测评会话 |
| `assessment_sessions.evaluator_user_id → users.id` | `RESTRICT` | 保留测评执行者 |
| `assessment_items.session_id → assessment_sessions.id` | `RESTRICT` | 测评结果不能脱离会话被删除 |
| `assessment_items.child_id → children.id` | `RESTRICT` | 测评结果保留孩子归属 |
| `assessment_items.knowledge_point_id → knowledge_points.id` | `RESTRICT` | 已测知识不能物理删除 |
| `assessment_items.evaluator_user_id → users.id` | `RESTRICT` | 保留测评执行者 |
| `child_knowledge_states.child_id → children.id` | `RESTRICT` | 派生状态仍受孩子生命周期保护 |
| `child_knowledge_states.knowledge_point_id → knowledge_points.id` | `RESTRICT` | 派生状态引用规范知识点 |

后续若需要停用账户、家庭或孩子，优先引入显式状态和归档流程，不直接扩大级联删除范围。

## 权限查询约束

- 家庭读取必须存在 `(current_user.id, family_id)` 成员关系。
- 家庭和孩子写入必须在同一成员关系上具备 `admin` 角色。
- 孩子读取通过 `children.family_id = family_members.family_id` 与当前用户联合查询。
- 对跨家庭资源统一返回 `404`，避免泄露资源是否存在；权限存在但角色不足返回 `403`。
- 前端隐藏按钮不是权限措施，所有规则由后端重复验证。

## 教师权限查询约束

教师是家庭外部授权角色，不能自动成为 `FamilyMember`。每次教师访问都必须验证当前用户的 active `TeacherProfile` 和目标孩子的 active `TeacherChildRelation`；撤销后立即失败。Class Code 只用于发现班级，必须经 Family Admin 确认才建立授权与成员资格。

## 系统知识目录

### `knowledge_points`

所有学科共用的规范知识主表。字段包含 UUID、`type`、`status`、标题、唯一 `canonical_key`、来源类型/引用和审计时间。当前 `type` 仅启用 `chinese_character`，结构可扩展 `chinese_word`、`math_concept`、`english_word`、`science_concept`。

### `chinese_characters`

与 `knowledge_points` 一对一，以 `knowledge_point_id` 为主键。保存唯一汉字、拼音、可选笔画/部首/难度/频次、基础释义、例句、常用词、标签及 `is_enabled`。Starter 数据不声明官方等级、教材章节或精确字频，没有可靠来源的字段保持空值。

本表严禁保存 `child_id`、`mastered`、`correct_count` 等孩子状态。系统知识和孩子学习事实必须分离。

### `knowledge_relations`

知识点之间的有向关系，支持 `related`、`prerequisite`、`confusing`、`derived`。唯一边约束为 `(source_id, target_id, relation_type)`，禁止自关联。

## 孩子汉字学习数据

### `learning_sessions` / `learning_records`

`learning_sessions` 保存一次有边界的学习活动，包含孩子、执行成年人、来源、开始/结束时间以及 `in_progress`、`completed`、`abandoned` 状态。`learning_records` 以 `(session_id, knowledge_point_id)` 唯一，保存 `introduced`、`relearned`、`parent_marked_seen` 或 `story_exposure` 原始事实。`story_exposure` 只表示在故事中接触，不能等价为认识。记录只追加，不提供更新或删除 API。

### `assessment_sessions` / `assessment_items`

测评会话同样保存状态与执行人。每个 `assessment_item` 记录一个汉字的 `correct`、`hinted_correct`、`uncertain` 或 `incorrect`，以及可选反应时间和是否使用提示。四种结果不能合并，后续算法可以从完整事实重新解释。

### `child_knowledge_states`

以 `(child_id, knowledge_point_id)` 唯一的派生投影，包含五级掌握度、0–1 分数、首次/最近学习与测评时间、四类结果计数、连续正确/错误、平均反应时间、家庭管理员设置的 `is_priority` 以及 `algorithm_version`。

五级为：`unlearned(0)`、`introduced(1)`、`recognizing(2)`、`proficient(3)`、`stable(4)`。状态可通过 `python -m app.cli.mastery` 从原始证据完整重算；重算保留 `is_priority`，不修改或删除任何原始记录。具体规则见 [Mastery V1](MASTERY_ALGORITHM.md)。

家庭 `admin` 与 `companion` 都能陪孩子学习和测评；只有家庭 `admin` 能修改优先学习标记。平台系统管理员如果不是该家庭成员，仍不能访问这些表对应的 API。

## Phase 5 派生学习数据

### `child_review_schedules`

以 `(child_id, knowledge_point_id)` 唯一，保存 `last_review_at`、`next_review_at`、间隔天数/阶段、最近结果、调度原因和 `review-v1` 版本。它完全由 `LearningRecord` 与 `AssessmentItem` 重建；`is_priority` 只在查询时参与队列排序，不伪造日程或掌握度。

### `child_learning_settings`

每个孩子一行，保存每日最多新字、每日复习容量、周/月检测开关和 IANA 时区。默认值分别为 5、15、开启、开启和 `Asia/Shanghai`。只有家庭 `admin` 可以修改，`companion` 只读。

### `daily_learning_plans` / `daily_plan_items`

`daily_learning_plans` 以 `(child_id, plan_date)` 唯一，保存计划时区、动态新字数、容量限制后的复习数、完整积压数、预计清理天数、可解释原因、完成进度和状态。`daily_plan_items` 固定当天的新字/复习字选择、顺序和完成状态，使刷新和重新登录后可以继续。

### `assessment_session_plans` / `assessment_session_targets`

这是 `AssessmentSession` 的可重复选题计划，不是新的答案证据。计划一对一保存抽样方法、版本、当时字库大小和可选每日计划；目标表保存题目、顺序及 `recently_learned`、`weak_or_priority`、`unseen_not_system_taught` 等抽样分层。答案仍只保存为追加式 `AssessmentItem`。

### `literacy_estimates`

每个已完成月度检测最多产生一条字库范围估算，保存当时字库大小、样本量、独立认识/未知数量、抽样方法与版本、点估计、上下界、数据是否充分和 `literacy-v1`。它不表示孩子全部汉字识字量；样本不足时估算字段保持 `NULL`。

Phase 5 新增表的每条业务外键均显式使用 `ON DELETE RESTRICT`。派生数据可重建不代表可以通过账户或孩子删除操作级联清除；原始证据与审计关系始终优先保护。完整规则见 [Phase 5 算法](REVIEW_AND_LITERACY_ALGORITHMS.md)。

## Phase 6 故事与阅读数据

### `stories` / `story_versions`

`stories` 是孩子私有的故事身份；`story_versions` 保存永不覆盖的具体标题、段落、主题、难度、问题、实际覆盖率和生成版本。重新生成创建 Version 2，孩子读过的 Version 1 仍可原样回看。版本保存 `snapshot_at`、已知/可用/目标知识点及当时掌握级别、策略/分析器/Prompt 版本、Provider/Model 和实际指标。

### `story_generation_runs` / `story_knowledge_points`

生成运行保存状态、有限尝试次数、幂等 request key、延迟、非敏感失败分类及可用 token 数；绝不保存 API key。字符使用表按版本保存 `strong_known`、`usable_recognizing`、`target`、`unexpected` 角色、出现次数和生成时掌握度。字库外陌生字仍保留在 Version JSON 指标，不伪造知识点。

### `reading_questions` / `reading_sessions` / `reading_answers`

理解题与故事版本绑定，保存选项和标准选项。`reading_sessions` 以 `(child_id, story_version_id)` 唯一，保存 `independent`/`with_help`、开始/完成时间、可靠时长和可选家长备注，重复开始返回同一会话。答案按会话/问题唯一，支持 `correct`、`with_help`、`partial`、`incorrect`，不写入汉字识别 AssessmentItem。

阅读完成后只针对目标字创建一个 `story_reading` LearningSession 和追加式 `story_exposure` LearningRecord；完成接口幂等，重复调用不产生重复证据。

### `daily_reading_tasks`

每个 Phase 5 DailyLearningPlan 最多一条阅读任务，状态为 `needs_story`、`pending`、`in_progress` 或 `completed`。它引用当时实际阅读的 StoryVersion/ReadingSession，使刷新、退出和重新登录后可继续。

上述全部孩子、用户、知识、计划、故事和阅读业务外键均为 `ON DELETE RESTRICT`。系统管理员没有跳过 `FamilyMember` 的故事读取权限。

## Phase 7 周末科学实验室

`science_experiments` 保存可搜索、可启用/归档的模板身份；每次内容变化写入新的 `science_experiment_versions.snapshot`，既有实验会话永远引用当时版本。`experiment_materials` 是可复用材料目录，`experiment_material_requirements` 保存必需/可选、数量和替代建议；`family_materials` 是家庭隔离的常备材料清单。

`experiment_sessions` 以孩子和家庭成员为边界，保存 `planned`、`in_progress`、`completed`、`abandoned`、当前步骤和完整模板快照。`experiment_evidence` 保存预测、观察、孩子总结、提问及孩子原话；`capability_tags` 是非评分行为标签，不能保存数值能力分。Phase 13 允许家庭成员对实验档案中的误记原文做明确修订或补充，并推进会话 `updated_at`；修订不能把 `completed` 改回进行中，也不能改写 `created_at`/`completed_at`。任何 AI 派生内容仍只能作为辅助响应或独立 derived 字段，不能覆盖人工档案或创建测评证据。

`experiment_media_assets` 只保存私有 MinIO 对象元数据。对象键使用 UUID，不包含姓名；读取必须重新通过孩子家庭鉴权，不返回公共 bucket URL。实验完成最多创建一组 `science_experiment_exposure` LearningRecord，不创建 AssessmentItem，也不推断孩子已经认识关联汉字。

`stories`、`story_generation_runs`、`story_versions` 可选引用 `source_experiment_session_id`。实验故事 Prompt 仅接收实验模板标题、引导问题和预期现象，不发送孩子原话、媒体、姓名、家庭或家长备注。所有新增业务外键均显式 `ON DELETE RESTRICT`。

## Phase 8 成长档案、报告和导出

`growth_events` 是按孩子隔离的统一时间线投影。自动事件通过 `(child_id, idempotency_key)` 保证重建幂等，并保存原始实体类型/ID、最小快照和策略版本；手工事件保存真实 actor 与原文，不被重建删除或改写。`growth_media_assets` 保存私有 MinIO 元数据，读取仍需家庭成员鉴权。

`growth_reports` / `growth_report_versions` 将报告身份与不可变版本分离。版本固定时间范围、真实指标、数据充分性、可解释章节及可选 AI 叙述；AI 字段不参与规范指标。`growth_books` / `growth_book_versions` 同样保留每次选择的事件、媒体和家长寄语快照，旧版本不会被后续编辑覆盖。

`export_jobs` 保存家庭管理员导出的状态、范围、私有对象键、manifest 校验结果、校验和与过期时间。导出 ZIP 使用 `growth-learning-export-v1`，不会保存认证或基础设施 secret。上述表全部采用 UUID、审计时间和显式 `ON DELETE RESTRICT`，没有账户级联删除孩子多年数据的路径。

## Phase 10 课程与版本化字库

`catalog_releases` 保存 catalog version、来源、引用、许可、导入时间、数量和 current 标记；
`character_catalog_entries` 将一次 release 的稳定顺序映射到既有 `KnowledgePoint`。Catalog
导入不会替换 `knowledge_points` 或 `chinese_characters`，原 200 字 UUID 保持不变。

`courses` 支持 `system`、`family`、`teacher`、`textbook_reference`，所有权由互斥约束固定；
`course_units` 与 `learning_activities` 保存通用层级，`activity_knowledge_points` 只引用
canonical knowledge，并记录角色和顺序。`child_course_enrollments` 保存孩子所选路径、课程
版本、状态和顺序，`course_activity_progress` 只保存活动完成事实及其 canonical evidence
session 引用。

课程完成比例不写入 `ChildKnowledgeState`。字符学习活动完成会追加 `LearningRecord` 并调用
统一 mastery/review 重算；识字正确性仍只能来自 `AssessmentItem`。兄弟复制不触碰任何
掌握度、证据、复习、估算、故事、科学或成长数据。所有新增业务外键均为
`ON DELETE RESTRICT`。完整边界见 [课程架构与 Catalog 来源](COURSE_ARCHITECTURE.md)。

## Phase 11 孩子体验、成就与家庭鼓励

`achievement_definitions` 保存带 `rule_version` 的确定性规则；`child_achievements` 以
`(child_id, achievement_definition_id)` 唯一，并保存来源类型/ID与当时规则计数快照。
成就是原始证据的追加式投影，重复重建不会重复解锁。

`star_ledger` 是正数-only 的追加账本，余额始终实时 `SUM(amount)`，不保存可直接覆盖的余额字段。
唯一来源/规则约束阻止重复奖励，数据库 `CHECK amount > 0` 禁止扣星。奖励只针对完整事件和成就，
绝不按每一道 AssessmentItem 加星。`family_reward_settings` 与 `family_reward_goals` 只承载家庭
管理员选择的展示开关和线下约定，不改变 `ChildKnowledgeState`。

成长树与统一 Today 是查询投影，不新增平行事实表。所有新增外键使用 `ON DELETE RESTRICT`。
规则、隐私和响应式约定见 [Phase 11 孩子体验](CHILD_EXPERIENCE.md)。

## Phase 13 档案与识字内容扩展

Phase 13 的 additive migration 为 `20260823_0013`，仅向 `chinese_characters` 添加可空的 `parent_tip`。`simple_meaning`、`common_words`、`example_sentence` 与 `parent_tip` 均由知识库人工维护，并可作为后续 AI 辅助生成的上下文。LearningRecord、AssessmentItem、ChildKnowledgeState、历史 Story/Science/Growth 快照及原有汉字 UUID 保持不变。实验媒体仍由 `experiment_media_assets` 关联私有 MinIO 对象，替换不改变媒体在档案中的稳定 ID。
