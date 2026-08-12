# Growth Learning 数据模型

本文记录已落地的数据模型与后续边界。Phase 2 只创建身份、家庭、成员和孩子四类正式业务实体，不提前创建学习、复习、故事或教师业务表。

## 通用约定

- 主键使用 UUID。
- `created_at`、`updated_at` 使用带时区时间戳，由数据库提供初始值。
- 家庭是最上层业务数据边界；所有家庭内资源必须通过成员关系鉴权。
- 孩子不是登录账户，也不继承 `User`。
- 年龄不入库，由 `birth_date` 按当前日期动态计算。
- Phase 2 不提供孩子或家庭的物理删除 API。长期数据删除/归档策略将在后续阶段单独设计。

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
| `created_at` / `updated_at` | 审计时间戳 |

密码、会话 token、密码哈希不得写入应用日志。数据库不保存明文密码。

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

后续若需要停用账户、家庭或孩子，优先引入显式状态和归档流程，不直接扩大级联删除范围。

## 权限查询约束

- 家庭读取必须存在 `(current_user.id, family_id)` 成员关系。
- 家庭和孩子写入必须在同一成员关系上具备 `admin` 角色。
- 孩子读取通过 `children.family_id = family_members.family_id` 与当前用户联合查询。
- 对跨家庭资源统一返回 `404`，避免泄露资源是否存在；权限存在但角色不足返回 `403`。
- 前端隐藏按钮不是权限措施，所有规则由后端重复验证。

## 后续教师模型边界

教师是家庭外部授权角色，不能自动成为 `FamilyMember`。后续阶段使用类似 `TeacherChildRelation` 的独立关系，把指定孩子、权限范围、有效期、授权人和撤销状态绑定在一起。Phase 2 不创建 Teacher 表或教师授权接口。

## 后续学习数据

识字、复习、测评、阅读、AI 故事和科学实验属于后续阶段。学习事实将以孩子为上下文，并保留原始事实与可重算派生状态的分离；Phase 2 不创建假学习记录或统计数据。
