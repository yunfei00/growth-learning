# Growth Learning 系统架构

## 1. 架构目标

系统采用模块化单体：一个 Next.js 前端、一个 FastAPI 后端，以及 PostgreSQL、Redis、MinIO 三个基础服务。它为清晰边界和长期演进留出空间，但不提前承担微服务的部署与一致性成本。

## 2. 系统上下文

```text
Browser
  │
  ├── Next.js Web ── HTTP /api/v1 ── FastAPI application
  │                                      ├── PostgreSQL (业务事实与派生状态)
  │                                      ├── Redis (缓存、限流、任务基础)
  │                                      ├── MinIO (媒体与导出文件)
  │                                      └── OpenAI-compatible provider
  │
  └── 家长、孩子、老师、陪伴者通过家庭权限边界访问
```

Windows 本地开发使用 Node.js 与 Python venv，不依赖 Docker。服务器完整集成环境使用 Docker Compose，数据服务不映射公网端口。

## 3. 后端分层

```text
app/api           HTTP 路由、请求校验、响应映射
app/services      用例编排、权限与事务边界
app/models        SQLAlchemy 持久化模型
app/schemas       跨边界的 Pydantic 数据契约
app/db            engine、session、迁移元数据
app/integrations  Redis、MinIO、AI 等外部适配器
app/core          配置、日志、安全等横切能力
```

依赖方向从外向内：路由调用服务；服务依赖领域接口/仓储；集成适配器实现外部接口。Phase 1 只建立必要骨架，不引入仓储基类、事件总线或复杂依赖注入框架。

### 业务模块边界

- `identity`：用户身份与会话
- `administration`：独立系统管理员 Guard、CLI 和真实系统计数
- `families`：家庭、成员、儿童档案、授权
- `knowledge`：通用知识点、汉字目录和知识关系
- `curriculum`：未来的学科、能力、课程和活动
- `learning`：学习/复习/测评原始事件与掌握状态计算
- `reading`：故事生成、规则校验、阅读会话
- `science`：实验课程与实验会话
- `growth`：时间线、媒体、报告和导出
- `teacher`：独立教师身份、家长逐孩子授权、轻量班级、任务和受限教学 DTO

模块之间通过稳定的服务契约和标识符协作；在模块化单体内共享一个数据库和事务能力。

## 4. 数据与一致性

PostgreSQL 是业务事实的唯一权威来源。Redis 中的数据必须可丢弃并从数据库恢复；MinIO 保存媒体对象，数据库保存对象元数据和归属关系。

学习数据采用两条链路：

```text
LearningRecord / AssessmentItem / ReviewRecord (append-only evidence)
                              │
                              └── versioned calculator
                                      │
                                      ▼
                           ChildKnowledgeState (derived projection)
```

- 原始记录在单个会话内以 `(session_id, knowledge_point_id)` 唯一；批量 API 在一个事务中写入会话与全部条目。
- 派生状态带 `algorithm_version`，以 `updated_at` 表示最近计算时间。
- 更新派生状态和写入原始事件可在同一数据库事务中完成；批量重算可以异步执行。
- 删除请求优先使用可审计的生命周期状态；法规要求的物理删除由专门流程执行并覆盖备份/对象存储。

## 5. 权限模型

- 每个请求先确认当前用户，再以 `family_id` 建立租户边界。
- FamilyMember 表达用户在家庭中的角色；Child 是受保护的档案实体。
- TeacherChildRelation 是显式授权，不从“老师角色”推导对所有孩子的访问权。
- 授权校验同时考虑角色、资源归属、scope、action、生效/过期时间和撤销状态。
- 服务层是强制授权边界；前端隐藏按钮只改善体验，不构成安全控制。
- `User.system_role` 表达平台权限；`FamilyMember.role` 表达单一家庭内权限。两套权限不互相提升。
- 系统管理员 API 只能管理系统知识与平台概览；访问家庭/孩子仍必须拥有对应 `FamilyMember`。
- 教师授权以 active `TeacherChildRelation` 为实时强制边界；连接码只用于发现，不能绕过 Family Admin 确认。
- 教师任务复用 `LearningRecord`、`AssessmentItem` 与 `ReadingSession`，不建立第二套学习事实；教师观察单向投影到家长时间线。
- 教师端响应使用专用最小 DTO，排除家庭成员、兄弟姐妹、私人媒体、完整时间线、故事书、报告、成长册和导出。

## 5.1 系统知识与孩子状态分离

`KnowledgePoint` 是跨学科规范主表，`ChineseCharacter` 是一对一的汉字属性，`KnowledgeRelation` 表达知识间关系。它们属于系统目录，不引用 Child。孩子掌握情况由 `LearningRecord`、`AssessmentItem` 和 `ChildKnowledgeState` 通过 `child_id + knowledge_point_id` 建立上下文，不污染共享知识。

## 5.2 Mastery V1 计算边界

Mastery V1 是纯确定性服务，不调用 LLM。API 写入一批学习或测评证据后，只重算受影响的知识点；运维 CLI 可从全部历史重建所有投影。`ChildKnowledgeState` 不是事实来源，即使投影损坏或算法升级，原始记录仍可恢复它。稳定掌握要求多次独立正确且跨越足够时间，规则详见 [Mastery V1](MASTERY_ALGORITHM.md)。

## 6. AI 集成

业务服务依赖统一的 `AIProvider` 协议，而不是供应商 SDK：

- 输入采用消息、温度、最大输出和可选结构化输出约束。
- 返回统一的文本、供应商、模型、用量和结束原因。
- `OpenAICompatibleProvider` 通过 `base_url`、`api_key` 和 `model` 支持 OpenAI、DeepSeek、Qwen/DashScope 或本地兼容服务。
- 默认提供禁用实现；Phase 6 由 OpenAI-compatible 适配器请求严格 JSON，CI 只使用确定性 Fake Provider。
- 提示模板、规则和模型版本必须可记录；面向孩子的输出需经过确定性内容规则和必要的家长确认。

## 7. API 与前端

- 后端业务 API 固定在 `/api/v1`，非业务探针使用 `/health`。
- API 统一错误结构、请求 ID 和 ISO 8601 UTC 时间。
- Next.js 使用 App Router；认证和 active child 由统一 Provider 管理，学习页面始终使用同一孩子上下文。
- 前端 API client 集中处理基础地址、超时、错误映射和未来的身份凭证。
- 浏览器只访问公开的 `NEXT_PUBLIC_API_BASE_URL`，任何服务端密钥都不得进入前端构建产物。

## 8. 缓存、任务与对象存储

- Redis Phase 1 仅建立连接和健康基础；后续用于短期缓存、限流计数和任务队列后端。
- 缓存键包含版本和家庭/资源范围；缓存失效不能影响事实正确性。
- MinIO bucket 默认私有，通过后端产生短期签名 URL；对象键不包含儿童姓名等敏感信息。
- 后续异步任务使用数据库事实作为输入，以幂等任务键和可观测重试保证安全执行。

## 9. 配置与环境

- 所有配置来自环境变量；本地 `.env` 不入库，`.env.example` 提供无敏感值模板。
- 开发、测试、CI 使用同一组应用入口和检查命令。
- Docker 镜像采用非 root 运行、显式依赖锁定和健康检查；服务器 Compose named volume 保存数据。
- 配置在进程启动时解析并快速失败，密钥永不写入日志。

## 10. 可观测性与演进

Phase 1 提供轻量健康检查；后续按需增加结构化日志、指标和追踪。`/health` 只表示进程存活，未来 `/ready` 可检查必需依赖，避免外部服务短暂故障导致存活探针重启风暴。

只有在模块具备独立扩缩容、故障隔离或团队所有权需求，并且迁移收益超过分布式成本时，才考虑拆分服务。首先通过模块接口和数据所有权保持可拆分性。

## 11. 关键架构决策

| 决策 | 选择 | 原因 |
| --- | --- | --- |
| 部署单元 | 模块化单体 | 保持事务简单和开发速度，避免过早微服务化 |
| 主数据库 | PostgreSQL | 强事务、关系约束、JSON 扩展与成熟运维能力 |
| ORM/迁移 | SQLAlchemy 2 + Alembic | 显式会话与稳定迁移工具链 |
| Web 框架 | Next.js App Router | 服务端渲染、类型安全与成熟生态 |
| AI | OpenAI-compatible 协议 | 供应商可替换，业务层不依赖专有 SDK |
| 学习状态 | 原始证据 + 派生投影 | 保留历史并允许算法重算和解释 |

## 12. Phase 5 自适应学习闭环

```text
LearningRecord / AssessmentItem（权威、追加式）
            │
            ├── Mastery V1 ──> ChildKnowledgeState
            ├── Review V1 ───> ChildReviewSchedule
            │                        │
            │                        └── capacity + priority + retention
            │                                      │
            └──────────────────────────────> DailyLearningPlan
                                                   │
                                      AssessmentSessionTarget
                                                   │
                                      新 AssessmentItem（事务）
```

`review_planning` 服务集中实现复习重放、队列排序、动态新字负荷、周期抽样和字库范围估算。HTTP 路由只负责授权、请求映射和错误语义。关键写入在同一个 SQLAlchemy 事务中完成，避免“答案已保存但日程未更新”或相反的不一致。

每日计划以孩子设置的 IANA 时区确定本地日期；UTC 只作为持久化时间基准。题目选择会持久化，因此恢复会话不依赖缓存或浏览器状态。Redis 不是正确性的来源。

算法版本分别记录为 `review-v1`、`plan-v1`、`sampling-v1` 和 `literacy-v1`。部署迁移后运行 `python -m app.cli.review`，为既有 Phase 4 证据安全回填日程；该过程不修改原始证据。详细规则及限制见 [Phase 5 算法](REVIEW_AND_LITERACY_ALGORITHMS.md)。

## 13. Phase 6 受控故事生成与阅读证据

```text
ChildKnowledgeState
  → immutable mastery snapshot
  → deterministic target selection + difficulty policy
  → structured provider JSON
  → Pydantic validation
  → Han Coverage Analyzer V1
  → accept / finite repair (max 3) / safe failure
  → StoryVersion + questions + generation audit
  → resumable ReadingSession
  → comprehension answers + story_exposure only
```

覆盖分析、资格判断、目标选择和学习证据都属于应用服务，不交给 LLM。Provider 只接收年龄段、主题、难度、可用字符和目标字符；不接收孩子姓名/生日、家庭、邮箱、照片或成长笔记。GenerationRun 记录 Provider/Model/版本/延迟和失败类别，不记录 secret 或原始私密 payload。

StoryVersion 与掌握快照是不可变审计材料。当前掌握状态后来变化不会回写旧故事；阅读完成也不会生成 AssessmentItem。`daily_reading_tasks` 只把 Phase 6 阅读状态连入 Phase 5 计划，不重写 Phase 5 算法。

## 14. Phase 7 线下科学证据闭环

```text
Versioned ScienceExperiment + household materials
  → deterministic child recommendation
  → resumable ExperimentSession (immutable template snapshot)
  → append-only prediction / observation / child words
  → private MinIO media streamed through household authorization
  → completion creates exposure only (never AssessmentItem.correct)
  → Growth Card
  → optional mastery-aware StoryVersion linked to the actual session
```

科学模块保持模块化单体事务：模板、版本、材料、证据和媒体元数据在 PostgreSQL，二进制对象在私有 MinIO。媒体不能依赖可分享的永久 URL；每次读取都重新检查 `FamilyMember`。实验转故事复用 Phase 6 的结构化 Provider、有限重试和程序覆盖率分析，并采用数据最小化上下文。

## 15. Phase 8 长期成长档案

```text
append-only learning / reading / science evidence + parent notes
  → deterministic GrowthEvent projector (growth-event-v1)
  → household-authorized timeline + private media
  → immutable deterministic report versions
  → immutable parent-curated GrowthBook versions
  → versioned private JSON/CSV/media export
```

GrowthEvent 投影器只读取已有事实并用稳定幂等键补齐事件，不反向修改来源。报告指标由应用服务计算；可选 AI 只生成单独标注的叙述。家庭导出在临时文件中逐条写入并在上传私有对象存储前验证 manifest 和 SHA-256，避免在内存拼装全部媒体。

运维面由 `gl-backup` 生成 PostgreSQL dump、对象清单、私有对象二进制归档和校验材料。恢复是经过隔离 PostgreSQL / MinIO namespace 演练的人工流程，永不由部署脚本隐式执行。`/health` 仅返回 V1 版本和 CI 构建 revision，不包含 author、配置或 secret。

## 16. Phase 10 reusable course layer

```text
versioned CatalogRelease ──> canonical KnowledgePoint
                                  ▲
Course ──> Unit ──> Activity ─────┘
                        │
ChildCourseEnrollment ──> ActivityProgress ──> canonical evidence session
                                                    │
                                                    └──> ChildKnowledgeState
```

课程是 knowledge/evidence 上方的编排层，不是第二套学习真相。Review V1 先计算新字容量；
`review_planning` 只在容量大于零时依照 priority、active enrollment path/order、catalog fallback
选择候选。家庭、老师和系统 ownership 在数据库约束与 API authorization 两层强制执行。

Catalog importer 以原 character/canonical key upsert，并在建立 release membership 前比较既有
UUID。历史 literacy sampling frame、StoryVersion 和 science links 都不参与重算。部署在数据库
migration 后、应用容器替换前运行幂等 importer，因此失败会阻止新应用切换但不会停止旧服务。

## 17. Phase 11 child experience projection

```text
canonical evidence + Daily Plan + Teacher Assignment
  ├──> unified child Today (presentation only)
  ├──> growth-tree-v1 summary (course progress != mastery)
  └──> achievement-v1 rules ──> immutable unlock ──> positive stars-v1 ledger
```

Parent and Child modes are route/navigation boundaries, not alternate authorization systems. Child mode keeps
one household-authorized active child and removes adult settings and private archive surfaces. API guards stay
authoritative. Achievement rebuild reads evidence without rewriting it; reward balance is derived from a
positive-only ledger with source idempotency. See [Phase 11 experience policy](CHILD_EXPERIENCE.md).

## 18. Unified character learning read models

```text
current CatalogRelease -> CharacterCatalogEntry.order_index
                              └──> system path index/group/previous/next

LearningSession -> LearningRecord -> KnowledgePoint -> ChineseCharacter
                              └──> paged learning-history timeline

AssessmentSession -> AssessmentItem -> ChildKnowledgeState
                              └──> test history/mastery (not learning history)
```

Character entry URLs carry only the sequence type and one optional plan/session/activity ID. The
server reconstructs deterministic neighbors after refresh. Mastery remains the complete 1,200-point
projection, while the learning-history read model starts at `LearningRecord`; this prevents an
assessment-only state from being mislabeled as something the child formally learned.

## 19. V1 release boundary

V1 固定为 `1.0.0`，Alembic head 为 `20260823_0013`。Release SHA 同时绑定 CI、前后端镜像 label、后端健康响应、生产部署、E2E 和恢复演练。角色边界见 [V1 角色与隐私矩阵](ROLE_PRIVACY_MATRIX.md)，发布/回滚门禁见 [V1 发布清单](RELEASE_CHECKLIST.md)。后续功能不增加第二套 mastery、课程或成长事实；未来工作进入 V2 backlog 或普通维护 release。
