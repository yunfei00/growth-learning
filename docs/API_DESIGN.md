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

当前不提供家庭成员邮件邀请或孩子删除。

### Parent-authorized teacher collaboration

| Method | Path | 权限与说明 |
| --- | --- | --- |
| `POST/GET/PATCH` | `/api/v1/teacher/profile` | 登录用户开启/读取/更新独立教师模式；不自动获得孩子权限 |
| `POST` | `/api/v1/teacher/profile/rotate-code` | 教师轮换 opaque 连接码 |
| `GET` | `/api/v1/teacher/dashboard` | 教师自己的班级、授权学生、任务和真实计数 |
| `POST/GET/PATCH` | `/api/v1/teacher/classrooms[/{id}]` | 教师自己的轻量班级；其他老师统一拒绝 |
| `GET` | `/api/v1/teacher/connections/resolve?code=...` | 登录用户查询连接码的最少必要资料，不产生授权 |
| `POST` | `/api/v1/children/{id}/teacher-connections` | Family Admin 以 teacher/class code 明确授权单一孩子 |
| `POST` | `/api/v1/children/{id}/teacher-connections/{relation_id}/revoke` | Family Admin 立即撤销；历史 evidence 保留 |
| `POST` | `/api/v1/children/{id}/teacher-classrooms/{membership_id}/leave` | Family Admin 让孩子退出班级 |
| `GET` | `/api/v1/children/{id}/teacher-collaboration` | 家庭成员查看该孩子的授权、班级、任务和观察历史 |
| `POST/GET` | `/api/v1/teacher/assignments` | 教师创建/查看自己的任务，只能选择 active 授权孩子 |
| `POST` | `/api/v1/teacher/assignments/{id}/publish` | 发布前再次验证授权与家长确认的班级成员资格 |
| `GET` | `/api/v1/teacher/assignments/{id}/analytics` | scoped aggregate；固定禁止 ranking |
| `GET` | `/api/v1/teacher/students[/{child_id}]` | teacher-specific DTO，不返回家庭私人 DTO |
| `POST` | `/api/v1/teacher/students/{child_id}/observations` | active 老师保存原文观察；不直接修改 mastery |
| `GET` | `/api/v1/children/{id}/teacher-tasks` | 家庭成员或 active 授权老师查看已发布任务 |
| `POST` | `/api/v1/children/{id}/teacher-tasks/{assignment_id}/start` | 开始/恢复 canonical learning 或 assessment session |
| `POST` | `/api/v1/children/{id}/teacher-tasks/{assignment_id}/progress` | 事务性、幂等追加 evidence 并完成任务 |

Companion 可陪孩子执行任务，但不能授权、撤销或入班。System Admin 无隐式教师或家庭权限。撤销后的下一次教师请求立即失败。

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

### Weekend Science Lab

| Method | Path | 权限与说明 |
| --- | --- | --- |
| `GET` | `/api/v1/science/experiments` | 已登录；只读 enabled 系统模板，支持搜索/难度/分页 |
| `GET` | `/api/v1/science/experiments/{id}` | 已登录；模板详情与材料、安全、家长解释 |
| `GET/PUT` | `/api/v1/families/{family_id}/science/materials` | 家庭成员读；仅家庭 admin 写 |
| `GET` | `/api/v1/children/{child_id}/science/recommendations` | 按年龄、家中材料、近 60 天历史和难度确定性排序 |
| `POST/GET` | `/api/v1/children/{child_id}/experiment-sessions` | 家庭 admin/companion 开始、恢复和查看历史 |
| `GET/PATCH` | `/api/v1/children/{child_id}/experiment-sessions/{id}` | 家庭成员；已完成/放弃会话不可修改 |
| `POST` | `.../{id}/evidence` | 追加孩子预测、观察、提问、原话与非评分标签 |
| `POST/GET` | `.../{id}/media` / `.../media/{media_id}/content` | 鉴权上传并流式读取私有图片/视频/语音 |
| `POST` | `.../{id}/complete` | 幂等完成，只产生 science exposure |
| `GET` | `.../{id}/growth-card` | 返回可读成长卡，不返回能力分数 |
| `POST` | `.../{id}/generate-story` | 家庭 admin；完成实验后复用 Phase 6 覆盖分析 |
| `GET/POST/PATCH` | `/api/v1/admin/science/*` | system admin 管理、版本化、归档和幂等 Starter 导入 |

系统管理员不自动拥有家庭实验、证据、媒体或故事权限；跨家庭统一返回 `404`。媒体 MIME 和大小在服务端验证，MinIO 不暴露公网端口。

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
| `GET` | `/api/v1/children/{child_id}/characters?mastery_level=&sort_by=&sort_order=` | 五类掌握状态的具体汉字列表与基础排序 |
| `GET` | `/api/v1/children/{child_id}/characters/{point_id}` | 汉字详情、人工学习提示和真实时间线 |
| `POST` | `/api/v1/children/{child_id}/characters/{point_id}/ai-assistance` | 非权威儿童讲解、组词、例句和家长提示；不写 mastery/evidence |

计划会话提交在一个数据库事务内追加 `AssessmentItem`、重算 `ChildKnowledgeState`、重算 `ChildReviewSchedule` 并更新 `DailyLearningPlan` 进度。若已有题目已经提交，重复请求返回 `409`；会话只有在所有固定目标都有原始证据后才能完成。

`daily_review`、`weekly_check`、`monthly_assessment` 是 `AssessmentSession.source`，不会建立并行的答案表。抽样题目和分层由 `AssessmentSessionTarget` 固定，月测中的 `unseen_not_system_taught` 明确表示系统此前没有正式教过该字。

### Mastery-aware stories and reading

所有端点首先验证孩子所属家庭；跨家庭及仅有 `system_role=admin` 的用户返回 `404`。家庭 `admin` 可生成，`admin`/`companion` 均可阅读、回答和完成会话。

| Method | Path | 说明 |
| --- | --- | --- |
| `GET` | `/api/v1/children/{child_id}/reading-context` | 年龄段、强掌握/可用字数量、确定性目标候选、推荐难度、Provider 状态 |
| `POST` | `/api/v1/children/{child_id}/stories/generate` | 家庭 `admin` 结构化生成；有限 repair/retry；支持幂等 `request_key` |
| `GET` | `/api/v1/children/{child_id}/stories` | 孩子的不可变版本故事书，支持标题搜索、难度过滤和分页 |
| `GET` | `/api/v1/children/{child_id}/story-versions/{version_id}` | 当时真实版本、实际覆盖率、问题与字库释义 |
| `POST` | `/api/v1/children/{child_id}/story-versions/{version_id}/reading/start` | 开始或恢复唯一阅读会话 |
| `POST` | `/api/v1/children/{child_id}/reading-sessions/{session_id}/answers` | 批量保存 2–3 道理解题答案 |
| `POST` | `/api/v1/children/{child_id}/reading-sessions/{session_id}/complete` | 幂等完成并追加目标字 story exposure |
| `GET` | `/api/v1/children/{child_id}/reading-summary` | 近 7 天真实阅读/陪读/理解题与接触计数 |

Provider 未配置时 context 返回 `provider_configured=false`，生成返回 `503 AI 服务尚未配置`；不会暴露缺失 key、Provider 原始错误或堆栈。故事响应的 coverage 均由应用分析器计算，不采信模型自报值。

### Experiment archive maintenance

| Method | Path | 说明 |
| --- | --- | --- |
| `GET/PATCH` | `/api/v1/children/{child_id}/experiment-sessions/{session_id}` | 完成后仍可读；仅允许修改家长备注，禁止状态/步骤回退 |
| `POST` | `.../experiment-sessions/{session_id}/evidence` | 进行中或完成后追加实验现象、回答与原话 |
| `PATCH` | `.../experiment-sessions/{session_id}/evidence/{evidence_id}` | 修订误记的现象或孩子回答，并更新档案时间 |
| `POST/PUT/DELETE` | `.../experiment-sessions/{session_id}/media[/media_id]` | 完成后添加、替换或删除私有媒体 |
| `GET` | `.../experiment-sessions/{session_id}/media/{media_id}/content` | 每次重新验证家庭关系后读取私有对象 |
| `POST` | `.../experiment-sessions/{session_id}/ai-parent-tip` | 完成后生成辅助家长讲解建议；不写学习记录 |

实验档案维护保留 `created_at` 和 `completed_at`，只推进 `updated_at`；所有写操作都保持 `status=completed`。媒体不通过公共 `/static` 或 `/media` 暴露。

## 错误约定

- `400/422`：请求内容无效。
- `401`：没有有效浏览器会话。
- `403`：用户属于家庭，但角色不允许当前操作。
- `404`：资源不存在，或资源属于另一个家庭。
- `409`：唯一约束冲突，例如重复邮箱。

管理员接口中的 `403` 表示当前用户不是系统管理员；它不依赖家庭成员角色。

所有家庭与孩子访问必须经过后端授权服务，不依赖客户端传入的角色或前端页面状态。

### Growth archive, reports, books and export

| Method | Path | 说明 |
| --- | --- | --- |
| `GET` | `/api/v1/children/{child_id}/growth-events` | 家庭成员时间线；支持年月、类别、来源和分页过滤 |
| `GET` | `/api/v1/children/{child_id}/growth-events/recent` | 首页最近 3–5 条真实事件 |
| `POST` | `/api/v1/children/{child_id}/growth-events` | 家庭 admin/companion 追加原文成长记录 |
| `POST` | `.../growth-events/{event_id}/media` | 鉴权上传私有附件 |
| `GET` | `.../growth-media/{media_id}/content` | 每次请求重新验证家庭关系后流式读取 |
| `POST` | `/api/v1/children/{child_id}/growth-events/rebuild` | 家庭 admin 安全补齐自动投影；不删除手工事件 |
| `POST/GET` | `/api/v1/children/{child_id}/growth-reports` | 仅家庭 admin 生成并列出月/年/自定义报告 |
| `GET` | `/api/v1/children/{child_id}/growth-reports/{id}` | 仅家庭 admin 读取不可变报告版本 |
| `POST/GET` | `/api/v1/children/{child_id}/growth-books` | 仅家庭 admin 创建版本并列出成长书 |
| `GET` | `/api/v1/children/{child_id}/growth-books/{id}` | 仅家庭 admin 读取当时真实版本 |
| `POST` | `/api/v1/families/{family_id}/exports` | 仅家庭 admin 创建私有异步语义导出任务 |
| `GET` | `/api/v1/families/{family_id}/exports/{id}` | 仅请求管理员读取状态 |
| `GET` | `/api/v1/families/{family_id}/exports/{id}/download` | 短期、禁止缓存、过期后 `410` |

报告、成长书和导出写操作不授权给 companion。平台 system admin 不绕过 FamilyMember，跨家庭资源按 `404` 处理。AI Provider 未配置时确定性报告仍可成功，仅省略可选叙述。

### Reusable courses and catalog

| Method | Path | 说明 |
| --- | --- | --- |
| `GET` | `/api/v1/courses?child_id=` | 家庭鉴权后列出系统、同家庭及已授权老师课程 |
| `GET` | `/api/v1/courses/{course_id}?child_id=` | 真实活动进度与独立 mastery 统计 |
| `POST/PATCH` | `/api/v1/families/{family_id}/courses[...]` | Family Admin 创建/归档家庭或教材参考课程 |
| `GET/POST/PATCH` | `/api/v1/teacher/courses[...]` | 教师只管理自己的 canonical 字表课程 |
| `GET/POST/PATCH` | `/api/v1/children/{child_id}/course-enrollments[...]` | 路径选择、暂停、继续与顺序；修改仅 Family Admin |
| `POST` | `/api/v1/children/{source_child_id}/course-path/copy` | 同家庭兄弟复制课程选择，不复制 mastery/history |
| `POST` | `/api/v1/children/{child_id}/course-activities/{activity_id}/complete` | 幂等追加 canonical LearningRecord 并推进活动 |
| `GET/POST` | `/api/v1/admin/catalog[/import]` | System Admin 查看来源或执行受控幂等导入 |
| `GET/PATCH` | `/api/v1/admin/courses[...]` | System Admin 查看/归档系统课程，不读取孩子数据 |

统一识字学习新增两个家庭鉴权 read model：

| Method | Path | 说明 |
| --- | --- | --- |
| `GET` | `/api/v1/children/{child_id}/character-learning-history` | 只从 `LearningSession/LearningRecord` 返回分页学习批次；支持搜索和时间边界，不包含 assessment-only 汉字 |
| `GET` | `/api/v1/children/{child_id}/characters/{point_id}/navigation` | 按 system path、today、mastery、learning/assessment session 或 course activity 解析稳定前后字；URL 只携带轻量上下文 |

`system_path` 导航只使用 current `CatalogRelease` 的 `CharacterCatalogEntry.order_index`；前端不得另按 Unicode、创建时间或本地数组重排。

Teacher Course 可见性不能替代 `TeacherChildRelation`；Family Admin 未授权时不能为孩子选入。
课程端点不会创建 parallel mastery 或 answer DTO。Catalog 历史由 version + size 同时返回。

### Child experience and positive encouragement

| Method | Path | 说明 |
| --- | --- | --- |
| `GET` | `/api/v1/children/{child_id}/experience/today` | 聚合真实今日/进行中任务，不创建学习或答题证据 |
| `GET` | `/api/v1/children/{child_id}/growth-tree` | 课程活动进度与 mastery 分离的分支摘要 |
| `GET` | `/api/v1/children/{child_id}/achievements` | 幂等补齐成就与正向账本后返回孩子摘要 |
| `POST` | `/api/v1/children/{child_id}/achievements/rebuild` | 家庭成员触发确定性规则重建 |
| `GET/PATCH` | `/api/v1/families/{family_id}/reward-settings` | 成员查看；仅 Family Admin 修改星星展示 |
| `POST/PATCH` | `/api/v1/families/{family_id}/reward-goals[...]` | 仅 Family Admin 管理线下家庭小目标 |

上述孩子端点不授予 Teacher 或 System Admin 隐式访问。星星账本不存在扣减接口，也不接受客户端
提交金额；服务只从 canonical completed event 和版本化 achievement rule 生成正向条目。

### V1 operator endpoints

| Method | Path | 说明 |
| --- | --- | --- |
| `GET` | `/health` | Liveness；只返回 `status`、`version=1.0.0` 与安全截短的 build revision |
| `GET` | `/docs` | FastAPI OpenAPI UI；生产经 `/growth/api/docs` 有意开放用于当前自托管验收 |

健康响应不返回环境、数据库、对象存储、AI 配置、author 或 secret。家庭私有 API 的权限矩阵见 [V1 角色与隐私矩阵](ROLE_PRIVACY_MATRIX.md)。
