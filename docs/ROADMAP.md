# Growth Learning 路线图 — V1 Complete

Growth Learning V1 的 Phase 1–12 已收敛到 `1.0.0`。每阶段都以迁移、测试、权限、生产验收和恢复能力为退出条件，不以页面数量衡量完成度。

## Phase 1：工程基础（已完成）

目标：形成专业、干净、可运行、可测试、可长期演进的单体工程基础。

- 产品、架构、数据和 API 文档
- FastAPI 配置、健康检查、数据库迁移、Redis/MinIO/AI 接口基础
- Next.js App Shell、首页、开发状态页和 API client
- PostgreSQL、Redis、MinIO、前后端 Docker Compose
- Windows/Linux 开发脚本、CI 和完整启动说明

退出条件：本地检查通过；Compose 配置可复现；新电脑按 README 能启动；Git 历史为逻辑提交。

## Phase 2：家庭、身份与权限（已完成）

目标：让一个家庭安全地创建儿童档案并管理协作者。

- User、Family、FamilyMember、Child 的首批正式迁移
- 身份会话与家庭上下文
- 家长/陪伴者权限矩阵和服务层授权
- Teacher 与 TeacherChildRelation 保留为家庭外部授权边界，暂不实现
- 注册、登录、Onboarding、家长首页和多孩子上下文基础

退出条件：真实注册到家长首页闭环与跨家庭权限测试通过。

## Phase 3：系统管理与汉字知识目录（已完成）

目标：建立独立平台管理员权限和可维护、可扩展的系统知识目录。

- `User.system_role` 与统一系统管理员 Guard
- 管理员安全 CLI、概览和汉字管理界面
- `KnowledgePoint`、`ChineseCharacter`、`KnowledgeRelation`
- 项目自有约 200 字 Starter 数据集与幂等导入
- 普通用户只读 enabled 知识 API

退出条件：管理员创建、迁移、生产导入、权限边界、搜索编辑归档和公网管理流程全部通过。

## Phase 4：孩子汉字学习与掌握状态（已完成）

目标：在系统知识目录之上建立第一个孩子学习闭环。

- `LearningSession` / 追加式 `LearningRecord`
- `AssessmentSession` / 四类结果 `AssessmentItem`
- 五级 `ChildKnowledgeState` 与确定性 Mastery V1
- 统一 active child 的新字、快速认读、记录、时间线与优先级界面
- 家长首页真实识字进度、批量写入与重算 CLI

退出条件：完成“活动 → 原始记录 → 状态计算 → 家长解释”的端到端闭环。

## Phase 5：自适应复习、每日计划与识字估算（已完成）

目标：把 Phase 4 原始证据扩展为完整、确定、可解释且可恢复的识字学习闭环。

- `review-v1` 的 1/3/7/14/30/60/90 天复习日程与安全重算 CLI
- 容量受控、积压不丢失、按本地日期幂等生成的今日任务
- 根据最近保留情况和复习积压动态降低新字数量
- 可恢复的每日复习、本周小挑战和月度识字检测
- 月测受控抽取系统未教过的启用字，并保留抽样分层与版本
- 只针对当前字库、样本不足时明确拒绝估算的 `literacy-v1`
- 家长首页、测试历史、学习设置和 active child 移动端流程

退出条件：原始证据、掌握度、复习日程和计划进度事务一致；派生数据可重算；跨家庭及系统管理员隐私边界不变；不显示超出当前字库支持范围的识字量。

## Phase 6：掌握度约束故事与阅读理解（已实现，生产 AI 配置待启用）

目标：真正使用具体孩子认识的字生成可解释、可校验、可长期回看的阅读内容。

- Beginner/Normal/Challenge 目标覆盖策略与程序实际 Han occurrence/unique 分析
- 保存字符级 Mastery Snapshot、有限 repair/retry 和不可变 StoryVersion
- OpenAI-compatible Provider、Fake CI Provider、儿童安全主题与最小 PII
- 大字移动阅读、点字释义、默认关闭拼音和轻量目标字高亮
- 可恢复 ReadingSession、2–3 道理解题和孩子独立故事书
- 只追加 `story_exposure`，不伪造识字 correct 证据
- 今日阅读任务、首页真实周阅读/陪读/理解题数据

退出条件：后端/前端/迁移/权限全部通过；生产真实 Provider 配置后完成真实生成验收并关闭 Issue #6。

## Phase 7：科学实验与成长记录（已实现，生产 AI 联动验收待 Phase 6 配置）

目标：把家庭线下探索和长期成长证据纳入同一平台。

- 项目自有 Starter 实验目录、不可变模板版本和管理员归档
- 家庭材料清单与年龄/材料/历史/进阶的确定性推荐
- 可恢复实验会话、孩子原话、观察、提问和非评分行为标签
- 私有照片/视频/语音与家庭鉴权读取
- 完成实验只创建 exposure，不伪造认字 correct
- 成长卡与 Phase 6 识字覆盖分析的实验故事联动

退出条件：安全规则强制执行；媒体归属明确；生产 AI 可用后完成真实实验故事生成并关闭 Issue #6，再关闭 Issue #7。

## Phase 8：统一成长档案、真实报告与家庭数据可携带性（已实现）

目标：把既有学习、阅读、科学实验和家长原文证据组织为可长期回看、可打印、可导出的孩子私有成长档案。

- 版本化、幂等且可安全重建的 GrowthEvent 统一时间线
- 家庭成员追加原文记录和私有媒体，首页显示最近真实事件
- 月度、年度和自定义区间的确定性真实报告；样本不足明确说明
- 不可变 GrowthReportVersion 和家长选择的 GrowthBookVersion
- `growth-learning-export-v1` JSON/CSV/media ZIP、manifest、校验和与短期下载
- `gl-backup`、对象存储备份边界和隔离恢复演练文档
- 跨家庭、companion 写权限和 system-admin 隐私边界测试

退出条件：迁移保留既有证据；重建不修改手工记录；AI 未配置不阻塞报告；导出不含 secret；备份命令和公网端到端流程通过。

## Phase 9：家长授权的老师协作（已实现）

目标：让老师在家长对单一孩子明确授权后，以最小必要权限布置任务、保留逐项教学 evidence，并把原文观察反馈给家庭。

- 独立 `TeacherProfile`、不可预测 Teacher Code 与实时可撤销的 `TeacherChildRelation`
- 家长确认加入的轻量 Classroom 和不可预测 Class Code
- 识字学习、复习、认字检测、阅读与线下说明任务；支持中断恢复
- 复用 `LearningRecord`、`AssessmentItem`、`ReadingSession` 和统一 mastery 算法
- 老师原文观察单向进入 Growth Timeline
- 仅限自身范围的完成统计、四类结果与常见错误字，禁止排行榜
- 兄弟姐妹、跨家庭、跨老师、System Admin 和家庭私人数据专项隔离

退出条件：迁移与 CI 通过；Family Admin 授权/撤销、任务 evidence、观察投影和生产公网闭环验收；Issue #9 关闭。

## Phase 10：可复用课程与扩展汉字 Catalog（已实现）

- Generic Course / Unit / LearningActivity 与 canonical KnowledgePoint mapping
- 系统汉字路径：起步 100、基础 300、进阶 500、扩展 1000+
- 1,200 字 versioned catalog、Unicode-3.0 provenance 与幂等导入
- 原 200 UUID、旧 `/200` literacy estimate、Story/Science 历史兼容
- 自适应复习先决定容量，课程只决定新字顺序
- 家庭/教材参考课程、家长授权后的老师课程、兄弟路径安全复制
- 家庭端、教师端与 System Admin 端的移动可用课程页面

退出条件：additive migration、PostgreSQL/权限/历史兼容测试与 CI 通过；生产导入、系统课程、
今日计划和真实 evidence 验收；Issue #10 关闭。

## Phase 11：家长/孩子双模式与正向成长体验（已实现）

- 清晰分离的 Parent / Child 导航，孩子模式固定 active child 且不暴露成人设置
- 基于既有 Daily Plan、阅读、科学、老师任务的统一 Today 与可恢复入口
- 课程进度和 canonical mastery 分离的 Chinese / Reading / Science 成长树
- `achievement-v1` 确定性、可解释、证据绑定且幂等的成长成就
- `stars-v1` 正向-only 家庭鼓励账本与可选线下家庭目标；无扣星、排名或按题奖励
- 390 / 768 / 1280 响应式导航、44px 触控目标、键盘焦点与 reduced-motion 支持
- 兄弟、跨家庭、Teacher、Companion 管理权与 System Admin 隐私专项测试

退出条件：additive migration、后端/前端/CI 全绿，公网双模式、刷新恢复、真实成就和权限边界验收；Issue #11 关闭。

## Phase 12：V1 发布加固（V1 Complete）

- 功能冻结，只处理发布阻塞、安全、性能、文档和恢复能力
- 同一 Release SHA 的全量 CI、生产 E2E、角色/隐私审计和秘密扫描
- `growth-learning-export-v1` 完整性与隐私门禁
- PostgreSQL + MinIO 对象的生产备份和隔离恢复演练
- 390/768/1280 响应式与内部 accessibility sanity
- `v1.0.0` 不可移动标签、GitHub Release 与最终生产烟测

退出条件：Issue #12 包含真实发布证据并关闭；V1 发布基线保持可回滚。

## Phase 13：学习体验与实验档案完善

- 完成态实验档案可继续查看并维护私有媒体、观察、孩子回答与家长备注，状态和完成时间不可回退
- 五类识字总览进入具体汉字列表，支持学习时间、最近复习和汉字排序
- 儿童大字号汉字详情页与可点击课程路径，返回保持原位置
- 已完成今日任务仍可查看、朗读和自由练习，不重复完成或创建学习证据
- 人工维护汉字解释、词语、例句和家长提示，并复用现有 Provider 提供非权威 AI 辅助内容
- AI 失败不阻塞学习，且不能直接修改 mastery、测试或学习记录

## Phase 14：账号准入与管理员用户系统

- 生产关闭公开注册，使用可过期、可撤销、限次并可绑定邮箱的平台邀请码
- `active / suspended / disabled` 用户生命周期与已有账号 `legacy` 平滑迁移
- `session_version` 使暂停、改密和退出所有设备立即作废旧会话
- 管理员用户搜索/分页、状态管理和邀请码管理；服务器 CLI 保留恢复通道
- Redis 登录/注册限流与不含 secret 的平台审计日志
- System Admin 只能读取账号元数据和家庭数量，仍不能读取家庭私有内容

退出条件：邀请制注册、已有账号兼容、账号暂停/恢复、会话失效、账号安全、管理员 UI/CLI、迁移、权限测试与生产烟测全部通过。

## V2 Backlog

- 更完整的可访问性、性能预算、外部安全评估与可观测性
- 任务队列、可观测性和依赖就绪探针
- 掌握/复习算法评估指标与受控实验
- 多设备同步、离线容错和数据冲突策略
- 完整数学、英语、拼音与写字课程
- 更大的合法课程体系、孩子独立账号、通知与受控的更复杂 AI
