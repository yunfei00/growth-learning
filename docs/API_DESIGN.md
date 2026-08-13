# Growth Learning API 设计

## 路径与认证

- 本地 API：`http://localhost:8000`
- 线上同源代理：`/growth/api`
- 版本前缀：`/api/v1`
- 浏览器认证：带过期时间的签名 token，保存在 HttpOnly Cookie 中。
- 本地 Cookie Path 为 `/`；当前线上 HTTP 环境为 `/growth/api`，`SameSite=Lax`、`Secure=false`。未来启用 HTTPS 后通过配置切换 `Secure=true`。
- 前端 API Client 统一使用 `credentials: include`，处理 JSON、超时、错误详情和 `401` 状态。

密码采用 Argon2 哈希，认证失败使用统一错误，不返回或记录密码、token、session secret、`password_hash`。

## 已实现端点

### Authentication

| Method | Path | 说明 |
| --- | --- | --- |
| `POST` | `/api/v1/auth/register` | 注册账户 |
| `POST` | `/api/v1/auth/login` | 登录并设置 HttpOnly Cookie |
| `POST` | `/api/v1/auth/logout` | 清除同路径 Cookie |
| `GET` | `/api/v1/auth/me` | 获取当前用户 |

### Families

| Method | Path | 权限 |
| --- | --- | --- |
| `POST` | `/api/v1/families` | 已登录；创建者成为 `admin` |
| `GET` | `/api/v1/families` | 返回当前用户加入的家庭 |
| `GET` | `/api/v1/families/{family_id}` | 家庭成员 |
| `PATCH` | `/api/v1/families/{family_id}` | `admin` |
| `GET` | `/api/v1/families/{family_id}/members` | 家庭成员 |

### Children

| Method | Path | 权限 |
| --- | --- | --- |
| `POST` | `/api/v1/families/{family_id}/children` | `admin` |
| `GET` | `/api/v1/families/{family_id}/children` | 家庭成员 |
| `GET` | `/api/v1/children/{child_id}` | 所属家庭成员 |
| `PATCH` | `/api/v1/children/{child_id}` | 所属家庭 `admin` |

当前不提供家庭成员邀请、孩子删除或 Teacher 端点。

### System administration

所有 `/api/v1/admin/*` 端点统一经过 `require_system_admin`。家庭 `admin` 不具备平台管理权限。

| Method | Path | 说明 |
| --- | --- | --- |
| `GET` | `/api/v1/admin/overview` | 用户、家庭、孩子、汉字的真实 COUNT |
| `GET` | `/api/v1/admin/characters` | 搜索、启用状态过滤、分页 |
| `POST` | `/api/v1/admin/characters` | 新增规范汉字 |
| `GET` | `/api/v1/admin/characters/{id}` | 管理员读取单字 |
| `PATCH` | `/api/v1/admin/characters/{id}` | 编辑、启用或归档 |
| `POST` | `/api/v1/admin/characters/import` | 幂等导入请求数据 |
| `POST` | `/api/v1/admin/characters/import-starter` | 幂等导入项目 Starter 数据 |
| `GET/POST` | `/api/v1/admin/knowledge-relations` | 查看/创建少量规范关系 |

导入响应包含 `created`、`updated`、`skipped`、`errors`。重复导入不会创建重复汉字或关系。

### Character read API

| Method | Path | 权限 |
| --- | --- | --- |
| `GET` | `/api/v1/characters` | 已登录；仅返回 active + enabled |
| `GET` | `/api/v1/characters/{id}` | 已登录；仅返回 active + enabled |

普通用户没有汉字写入端点。

### Child character learning

下列接口全部先通过孩子所属家庭成员关系鉴权。家庭 `admin` 和 `companion` 可读取、学习和测评；优先级修改只允许家庭 `admin`。`system_role=admin` 不绕过家庭关系。

| Method | Path | 说明 |
| --- | --- | --- |
| `GET` | `/api/v1/children/{child_id}/characters/summary` | 五级真实数量、优先数量和原始证据计数 |
| `GET` | `/api/v1/children/{child_id}/characters` | 汉字/拼音搜索、掌握度/优先过滤、分页 |
| `GET` | `/api/v1/children/{child_id}/characters/{knowledge_point_id}` | 当前投影和按时间排序的原始证据时间线 |
| `GET` | `/api/v1/children/{child_id}/characters/recommendations` | `new` 或 `assessment` 的确定性候选，默认 5 字 |
| `POST` | `/api/v1/children/{child_id}/learning-sessions` | 批量创建学习会话和追加式 LearningRecord |
| `POST` | `/api/v1/children/{child_id}/assessment-sessions` | 批量创建测评会话和四类 AssessmentItem |
| `PATCH` | `/api/v1/children/{child_id}/characters/{knowledge_point_id}/priority` | 家庭 `admin` 设置/取消优先学习 |

学习和测评批量请求单次最多 50 个不同知识点；`(session_id, knowledge_point_id)` 唯一约束阻止同一会话重复记录。新证据与 Mastery V1 派生状态在同一事务中写入。没有原始证据的知识点按 `unlearned` 返回，但不会为了读取而批量生成空状态行。

### Adaptive review and daily plan

下列端点全部要求当前用户是孩子所属家庭成员；跨家庭和无家庭关系的系统管理员统一返回 `404`。

| Method | Path | 说明 |
| --- | --- | --- |
| `GET` | `/api/v1/children/{child_id}/today` | 幂等获取/创建本地日期的今日计划、动态新字数和真实积压 |
| `GET` | `/api/v1/children/{child_id}/reviews/backlog` | 完整到期数、容量、预计清理天数及当日排序队列 |
| `GET` | `/api/v1/children/{child_id}/learning-settings` | 家庭成员读取孩子学习设置 |
| `PATCH` | `/api/v1/children/{child_id}/learning-settings` | 仅家庭 `admin` 修改新字上限、复习容量、开关和时区 |
| `POST` | `/api/v1/children/{child_id}/reviews/start` | 开始或恢复当天 `daily_review` 会话 |
| `POST` | `/api/v1/children/{child_id}/weekly-check/start` | 开始、恢复或读取本周固定小挑战 |
| `POST` | `/api/v1/children/{child_id}/monthly-assessment/start` | 开始、恢复或读取本月固定检测 |
| `GET` | `/api/v1/children/{child_id}/planned-assessments/{session_id}` | 读取固定题目、已完成结果和进度 |
| `POST` | `/api/v1/children/{child_id}/planned-assessments/{session_id}/items` | 批量/逐项追加结果；同一题不重复 |
| `GET` | `/api/v1/children/{child_id}/assessment-history` | 每日复习、周度和月度测试历史及四类计数 |
| `GET` | `/api/v1/children/{child_id}/literacy-estimate` | 最新字库范围估算或明确“数据不足” |
| `GET` | `/api/v1/children/{child_id}/literacy-estimate/history` | 历次字库范围与抽样版本 |

计划会话提交在一个数据库事务内追加 `AssessmentItem`、重算 `ChildKnowledgeState`、重算 `ChildReviewSchedule` 并更新 `DailyLearningPlan` 进度。若已有题目已经提交，重复请求返回 `409`；会话只有在所有固定目标都有原始证据后才能完成。

`daily_review`、`weekly_check`、`monthly_assessment` 是 `AssessmentSession.source`，不会建立并行的答案表。抽样题目和分层由 `AssessmentSessionTarget` 固定，月测中的 `unseen_not_system_taught` 明确表示系统此前没有正式教过该字。

## 错误约定

- `400/422`：请求内容无效。
- `401`：没有有效浏览器会话。
- `403`：用户属于家庭，但角色不允许当前操作。
- `404`：资源不存在，或资源属于另一个家庭。
- `409`：唯一约束冲突，例如重复邮箱。

管理员接口中的 `403` 表示当前用户不是系统管理员；它不依赖家庭成员角色。

所有家庭与孩子访问必须经过后端授权服务，不依赖客户端传入的角色或前端页面状态。
