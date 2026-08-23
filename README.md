# Growth Learning

Growth Learning `1.0.0` 是一个面向儿童长期学习与成长记录的家庭中心平台。V1 把家庭、识字学习与复习、课程、掌握度约束阅读、科学实验、老师协作、成长档案和孩子体验建立在同一套可追溯 evidence 上；不以虚构分数、排名或第二套 mastery 取代真实记录。

## 当前用户流程

```text
注册 → 登录 → 创建家庭 → 添加孩子 → 今日识字/复习 → 适读故事 → 周末科学实验 → 长期成长证据
                                                    ↘ 家长授权老师 → 老师任务/观察
```

再次登录后，应用通过 HttpOnly Cookie 获取当前用户，从 PostgreSQL 加载家庭和孩子。家长首页的识字数字来自真实 LearningRecord、AssessmentItem 与 ChildKnowledgeState，不展示虚构统计。

## Windows 开发

Windows 使用本地 Node.js 和 Python venv，不需要 Docker、Docker Desktop 或重型虚拟化环境。

要求：Node.js 24、pnpm 11.16.0、Python 3.12 或 3.13。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".\backend[dev]"
Set-Location frontend
pnpm install --frozen-lockfile
Set-Location ..
.\scripts\dev.ps1
```

本地地址：

| 服务 | 地址 |
| --- | --- |
| Frontend | <http://localhost:3000> |
| Register | <http://localhost:3000/register> |
| Login | <http://localhost:3000/login> |
| Admin | <http://localhost:3000/admin> |
| Character Learning | <http://localhost:3000/learn/characters> |
| My Storybook | <http://localhost:3000/read> |
| Weekend Science Lab | <http://localhost:3000/science> |
| Teacher Workspace | <http://localhost:3000/teacher> |
| Parent Teacher Collaboration | <http://localhost:3000/teacher-collaboration> |
| Backend health | <http://localhost:8000/health> |
| Backend OpenAPI | <http://localhost:8000/docs> |

本地开发可使用 SQLite 测试数据库；完整集成与 PostgreSQL migration 在 Linux 服务器执行。

## 检查

```powershell
.\scripts\check.ps1
```

检查内容：

- Backend：Ruff、格式检查、pytest、Alembic。
- Frontend：ESLint、TypeScript、Next.js production build。
- CI：在空 PostgreSQL 18 数据库执行 `alembic upgrade head` 并验证正式表。
- CI 还会先停在 Phase 2 migration 插入旧用户，再升级并验证旧用户仍为普通 `user`。

## 系统管理员与 Starter 数据

系统管理员与家庭管理员完全独立。管理员密码不接受命令行明文参数；交互执行时由隐藏输入读取，非交互部署可通过标准输入注入运行时 secret。

```bash
docker compose exec backend python -m app.cli.admin create-admin \
  --email admin@example.com --display-name "System Admin"
docker compose exec backend python -m app.cli.admin promote-admin \
  --email existing@example.com
docker compose exec backend python -m app.cli.admin set-password \
  --email admin@example.com
docker compose exec backend python -m app.cli.characters import-starter
docker compose exec backend python -m app.cli.science import-starter
docker compose exec backend python -m app.cli.mastery
docker compose exec backend python -m app.cli.mastery --child-id CHILD_UUID
docker compose exec backend python -m app.cli.review
docker compose exec backend python -m app.cli.review --child-id CHILD_UUID
```

`create-admin` 可重复执行且不会重复创建账户；已有普通账户必须显式执行 `promote-admin`。项目自有 Starter 数据位于 `backend/data/chinese_characters_v1.json` 和 `backend/data/science_experiments_v1.json`；科学数据是项目自编的家庭实验起始集，不复制商业课程，也不宣称官方标准。

## 老师协作

登录用户可在 `/teacher` 主动开启独立教师模式并获得不可预测的 Teacher Code。该动作不授予任何孩子权限；Family Admin 必须在 `/teacher-collaboration` 查看最少必要教师/班级信息，并对当前孩子明确确认。Companion 只能陪孩子完成任务，System Admin 也没有隐式家庭或教师权限。

识字学习与复习任务复用 `LearningRecord`，认字检测复用逐项 `AssessmentItem`，阅读任务复用 `ReadingSession`；不存在教师专属掌握度或排行榜。撤销后下一次教师请求立即拒绝，历史 evidence 和老师原文观察仍保留给家庭。完整权限与数据边界见 [家长授权的老师协作](docs/TEACHER_COLLABORATION.md)。

## AI 学习助手运行时配置

AI 默认禁用。启用时只在服务器 `.env` 配置 OpenAI-compatible Provider，不把 key 写入 Git、CI、前端、数据库或 Issue。故事生成、汉字儿童讲解和实验家长建议复用同一个 Provider：

```dotenv
AI_PROVIDER=openai_compatible
AI_BASE_URL=https://provider.example/v1
AI_API_KEY=运行时密钥
AI_MODEL=provider-model-name
AI_TIMEOUT_SECONDS=60
AI_STORY_MAX_ATTEMPTS=3
```

CI 始终使用确定性 Fake Provider，不调用真实外部 AI。未配置时 `/read` 正确显示“AI 服务尚未配置”，现有故事、阅读历史和本地证据仍可读取。

## 服务器部署

完整环境固定部署到 `/opt/apps/growth-learning`，由 Docker Compose 运行 PostgreSQL、Redis、MinIO、FastAPI 和 Next.js。数据库、Redis、MinIO 不映射公网端口，Web/API 仅绑定宿主机回环地址并由 Nginx 代理。

首次配置：

```bash
GROWTH_LEARNING_PUBLIC_FRONTEND_ORIGIN=http://8.130.97.14 \
GROWTH_LEARNING_PUBLIC_API_BASE_URL=/growth/api \
GROWTH_LEARNING_PUBLIC_APP_BASE_PATH=/growth \
GROWTH_LEARNING_API_ROOT_PATH=/growth/api \
GROWTH_LEARNING_AUTH_COOKIE_PATH=/growth/api \
GROWTH_LEARNING_AUTH_COOKIE_SECURE=false \
GROWTH_LEARNING_BIND_ADDRESS=127.0.0.1 \
  bash scripts/server-bootstrap.sh
```

常用运维命令：

```bash
gl-start
gl-stop
gl-restart
gl-status
gl-logs backend
gl-update
gl-backup
```

所有命令只操作 `growth-learning` Compose project。`gl-stop`/`gl-restart` 保留 named volumes；生产更新不需要 stop。`gl-backup` 生成 PostgreSQL custom dump、私有对象清单与二进制归档、服务状态、manifest 和 SHA-256 校验材料。恢复前必须按 [备份恢复手册](docs/BACKUP_RESTORE.md) 在隔离数据库与 bucket 演练。

`gl-update` 只允许 clean working tree，并执行 fast-forward pull。部署脚本下载 CI 为当前 commit 构建的前后端镜像，然后按以下顺序更新：

```text
加载并校验镜像 revision
→ 启动/确认 PostgreSQL、Redis、MinIO healthy
→ alembic upgrade head
→ alembic current
→ 幂等导入 1,200 字 versioned Chinese Catalog 与系统课程
→ 幂等导入 Starter 科学实验
→ 从原始证据重算 Review V1 日程
→ 幂等补齐 GrowthEvent V1 投影并清理过期导出
→ 幂等补齐 achievement-v1 成就与 stars-v1 正向账本
→ 更新 backend/frontend
→ 容器与 HTTP health check
```

流程不执行 `docker compose down`，不删除 named volumes，也不运行任何 Docker prune 命令。

回滚应用时先备份，再切换到已验证 commit 与同 revision 镜像；不要在生产盲目执行 `alembic downgrade`。完整发布门禁和回滚规则见 [V1 发布清单](docs/RELEASE_CHECKLIST.md)。

公网地址：

- Web：<http://8.130.97.14/growth>
- API health：<http://8.130.97.14/growth/api/health>
- OpenAPI：<http://8.130.97.14/growth/api/docs>

## 核心设计文档

- [数据模型](docs/DATA_MODEL.md)
- [API 设计](docs/API_DESIGN.md)
- [系统架构](docs/ARCHITECTURE.md)
- [产品需求](docs/PRODUCT_REQUIREMENTS.md)
- [路线图](docs/ROADMAP.md)
- [Phase 5 复习与识字估算算法](docs/REVIEW_AND_LITERACY_ALGORITHMS.md)
- [Phase 6 AI 故事与汉字覆盖策略](docs/AI_STORY_POLICY.md)
- [Phase 7 科学实验数据与隐私边界](docs/DATA_MODEL.md#phase-7-周末科学实验室)
- [Phase 8 成长档案与报告](docs/GROWTH_ARCHIVE.md)
- [Phase 9 家长授权的老师协作](docs/TEACHER_COLLABORATION.md)
- [Phase 10 可复用课程与 Catalog 来源](docs/COURSE_ARCHITECTURE.md)
- [Phase 11 家长/孩子双模式与正向成长体验](docs/CHILD_EXPERIENCE.md)
- [家庭导出格式 V1](docs/EXPORT_FORMAT.md)
- [生产备份与恢复演练](docs/BACKUP_RESTORE.md)
- [V1 角色与隐私矩阵](docs/ROLE_PRIVACY_MATRIX.md)
- [V1 发布清单](docs/RELEASE_CHECKLIST.md)
- [V1 已知限制](docs/KNOWN_LIMITATIONS.md)
- [1.0.0 变更日志](CHANGELOG.md)

## 安全边界

- 密码只保存 Argon2 哈希，API 不返回 `password_hash`。
- 浏览器会话使用 HttpOnly Cookie；Cookie Path 按本地 `/` 与线上 `/growth/api` 分别配置。
- 家庭与孩子权限由后端集中校验，跨家庭资源返回 `404`。
- `admin` 可以修改家庭/孩子核心配置；`companion` 对这些核心配置只读。
- 家庭 `admin` 与 `companion` 都能陪孩子学习/测评；只有家庭 `admin` 能修改优先学习标记。
- 学习与测评事实只追加；Mastery V1 可重算且不会删除原始证据。
- 读完故事只追加 `story_exposure`，绝不伪造认字 `correct` 测评证据。
- 完成科学实验只追加 `science_experiment_exposure`；孩子原话不可覆盖，行为标签不生成数值分数。
- 实验媒体存于私有 MinIO，并由家庭鉴权 API 流式读取；对象键不含儿童姓名。
- 成长档案自动投影可幂等重建，手工原文、旧报告版本和旧成长书版本不被覆盖。
- 家庭导出仅限家庭管理员、短期私有下载，并排除密码、token、API key 和基础设施 secret。
- 发给 AI 的数据仅限年龄段、主题、难度、允许字和目标字；不发送姓名、生日、家庭、邮箱、照片或成长笔记。
- `system_role=admin` 只授予平台知识管理权限，不自动取得任何家庭或孩子资料。
- 所有 `/api/v1/admin/*` 在后端统一校验系统管理员角色；普通/家庭管理员均返回 `403`。
- 所有正式业务外键使用 `ON DELETE RESTRICT`；当前不提供孩子物理删除。
- Teacher 只能通过 Family Admin 对单一孩子建立的 active 外部授权关系访问有限教学 DTO，不能自动成为 `FamilyMember`；撤销实时生效。
- 课程只引用 canonical `KnowledgePoint`；课程完成不等于掌握，兄弟复制不复制任何 mastery 或 evidence。

## V1 范围与限制

V1 的汉字目录/课程阶段为项目定义；AI 辅助内容需要可选运行时 Provider；没有孩子独立账号、完整数学/英语课程、学校级 LMS、排行榜或开放聊天。Growth Book PDF 使用浏览器打印。详情见 [V1 已知限制](docs/KNOWN_LIMITATIONS.md)。AI 不直接修改掌握度、测试成绩或学习证据。
