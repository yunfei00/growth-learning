# Growth Learning 数据模型

本文记录已落地的数据模型与后续边界。Phase 4 在身份、家庭和系统知识目录之上加入孩子汉字学习原始证据与可重算掌握状态；不包含复习调度、AI 故事或教师业务表。

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
| `is_active` | 账户是否可登录 |
| `system_role` | 平台角色：`user` 或 `admin`；注册默认 `user` |
| `created_at` / `updated_at` | 审计时间戳 |

密码、会话 token、密码哈希不得写入应用日志。数据库不保存明文密码。

`system_role=admin` 是平台管理权限，与 `family_members.role=admin` 完全独立。系统管理员不因平台角色自动获得任何家庭或孩子的访问权。

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

## 后续教师模型边界

教师是家庭外部授权角色，不能自动成为 `FamilyMember`。后续阶段使用类似 `TeacherChildRelation` 的独立关系，把指定孩子、权限范围、有效期、授权人和撤销状态绑定在一起。Phase 2 不创建 Teacher 表或教师授权接口。

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

`learning_sessions` 保存一次有边界的学习活动，包含孩子、执行成年人、来源、开始/结束时间以及 `in_progress`、`completed`、`abandoned` 状态。`learning_records` 以 `(session_id, knowledge_point_id)` 唯一，保存 `introduced`、`relearned` 或 `parent_marked_seen` 原始事实。记录只追加，不提供更新或删除 API。

### `assessment_sessions` / `assessment_items`

测评会话同样保存状态与执行人。每个 `assessment_item` 记录一个汉字的 `correct`、`hinted_correct`、`uncertain` 或 `incorrect`，以及可选反应时间和是否使用提示。四种结果不能合并，后续算法可以从完整事实重新解释。

### `child_knowledge_states`

以 `(child_id, knowledge_point_id)` 唯一的派生投影，包含五级掌握度、0–1 分数、首次/最近学习与测评时间、四类结果计数、连续正确/错误、平均反应时间、家庭管理员设置的 `is_priority` 以及 `algorithm_version`。

五级为：`unlearned(0)`、`introduced(1)`、`recognizing(2)`、`proficient(3)`、`stable(4)`。状态可通过 `python -m app.cli.mastery` 从原始证据完整重算；重算保留 `is_priority`，不修改或删除任何原始记录。具体规则见 [Mastery V1](MASTERY_ALGORITHM.md)。

家庭 `admin` 与 `companion` 都能陪孩子学习和测评；只有家庭 `admin` 能修改优先学习标记。平台系统管理员如果不是该家庭成员，仍不能访问这些表对应的 API。
