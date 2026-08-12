# Growth Learning

Growth Learning 是一个面向儿童长期学习与成长记录的家庭中心平台。Phase 4 已在通用汉字知识目录之上建立孩子学习证据、快速认读和可重算五级掌握状态；复习调度与 AI 故事仍不在本阶段范围内。

## 当前用户流程

```text
注册 → 登录 → 创建家庭 → 添加第一个孩子 → 家长首页 → 识字学习/快速认读
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
docker compose exec backend python -m app.cli.mastery
docker compose exec backend python -m app.cli.mastery --child-id CHILD_UUID
```

`create-admin` 可重复执行且不会重复创建账户；已有普通账户必须显式执行 `promote-admin`。项目自有 Starter 数据位于 `backend/data/chinese_characters_v1.json`，不宣称官方标准、教材清单或精确字频。

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

更新命令：

```bash
gl-update
```

`gl-update` 只允许 clean working tree，并执行 fast-forward pull。部署脚本下载 CI 为当前 commit 构建的前后端镜像，然后按以下顺序更新：

```text
加载并校验镜像 revision
→ 启动/确认 PostgreSQL、Redis、MinIO healthy
→ alembic upgrade head
→ alembic current
→ 更新 backend/frontend
→ 容器与 HTTP health check
```

流程不执行 `docker compose down`，不删除 named volumes，也不运行任何 Docker prune 命令。

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

## 安全边界

- 密码只保存 Argon2 哈希，API 不返回 `password_hash`。
- 浏览器会话使用 HttpOnly Cookie；Cookie Path 按本地 `/` 与线上 `/growth/api` 分别配置。
- 家庭与孩子权限由后端集中校验，跨家庭资源返回 `404`。
- `admin` 可以修改家庭/孩子核心配置；`companion` 对这些核心配置只读。
- 家庭 `admin` 与 `companion` 都能陪孩子学习/测评；只有家庭 `admin` 能修改优先学习标记。
- 学习与测评事实只追加；Mastery V1 可重算且不会删除原始证据。
- `system_role=admin` 只授予平台知识管理权限，不自动取得任何家庭或孩子资料。
- 所有 `/api/v1/admin/*` 在后端统一校验系统管理员角色；普通/家庭管理员均返回 `403`。
- 所有正式业务外键使用 `ON DELETE RESTRICT`；当前不提供孩子物理删除。
- Teacher 将通过家庭外部授权关系访问指定孩子，不能自动成为 `FamilyMember`。
