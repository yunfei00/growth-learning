# Growth Learning

Growth Learning 是一个面向儿童长期学习与成长记录的家庭中心平台。项目从汉字学习切入，逐步覆盖可重算掌握度、自适应复习、识字量测评、受控 AI 阅读、周末科学实验、家庭与老师协作以及长期成长档案。

当前为 **Phase 1：工程基础**。仓库提供可运行的 Next.js + FastAPI 模块化单体，以及 PostgreSQL、Redis、MinIO 本地开发环境；尚未实现正式业务账户和学习数据。

## 快速开始（Docker，推荐）

要求：Git、Docker Desktop（Windows/macOS）或 Docker Engine（Linux），并启用 Docker Compose v2。

```powershell
git clone git@github.com:yunfei00/growth-learning.git
cd growth-learning
Copy-Item .env.example .env
# 打开 .env，替换两个 local-only 密码
.\scripts\dev.ps1
```

Linux/macOS：

```sh
git clone git@github.com:yunfei00/growth-learning.git
cd growth-learning
cp .env.example .env
# 打开 .env，替换两个 local-only 密码
./scripts/dev.sh
```

首次启动会构建镜像和下载基础服务。所有健康检查通过后可访问：

| 服务 | 地址 |
| --- | --- |
| Frontend | <http://localhost:3000> |
| 开发状态页 | <http://localhost:3000/status> |
| Backend health | <http://localhost:8000/health> |
| Backend OpenAPI | <http://localhost:8000/docs> |
| MinIO Console | <http://localhost:9001> |

停止服务使用 `docker compose down`。本地数据保存在命名卷中；`docker compose down --volumes` 会永久删除本项目的本地数据库、缓存和对象存储数据，请谨慎使用。

## 本机开发

### 工具版本

- Node.js 24（仓库 `.nvmrc`；当前基线验证版本 24.14.0）
- pnpm 11.16.0（由 `packageManager` 固定）
- Python 3.12 或 3.13（仓库开发基线 `.python-version` 为 3.13）
- Docker Compose v2

### Backend

PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".\backend[dev]"
Set-Location backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Linux/macOS：

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e './backend[dev]'
cd backend
../.venv/bin/python -m uvicorn app.main:app --reload
```

本机运行后端时仍需 PostgreSQL/Redis/MinIO 的连接配置；轻量 `/health` 和单元测试不会在导入时连接这些服务。迁移命令在 `backend` 目录运行：

```powershell
..\.venv\Scripts\python.exe -m alembic upgrade head
```

### Frontend

```powershell
Set-Location frontend
pnpm install --frozen-lockfile
pnpm dev
```

前端读取 `NEXT_PUBLIC_API_BASE_URL`，未设置时使用 `http://localhost:8000`。不要把任何密钥放入 `NEXT_PUBLIC_*` 变量。

## 验证

Windows 可运行：

```powershell
.\scripts\check.ps1
```

Linux/macOS 可运行：

```sh
./scripts/check.sh
```

脚本与 CI 使用相同的核心命令：

```text
Backend:  ruff check, ruff format --check, pytest
Frontend: eslint, tsc --noEmit, next build
```

Compose 配置检查与运行态检查：

```powershell
docker compose --env-file .env config --quiet
docker compose --env-file .env ps
Invoke-RestMethod http://localhost:8000/health
```

## 配置

所有运行配置来自环境变量。只提交 [.env.example](.env.example)，真实 `.env`、API Key、密码和 token 已被忽略。

| 变量 | 用途 | 默认/示例 |
| --- | --- | --- |
| `DATABASE_URL` | 后端异步 PostgreSQL URL | Compose 从 `POSTGRES_*` 组成 |
| `REDIS_URL` | Redis 连接 | `redis://redis:6379/0`（Compose） |
| `MINIO_ENDPOINT` | MinIO API 端点 | `minio:9000`（Compose） |
| `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` | 对象存储凭据 | 从 `.env` 注入 |
| `MINIO_BUCKET` | 私有媒体 bucket 名 | `growth-learning` |
| `CORS_ORIGINS` | 逗号分隔的 Web origins | `http://localhost:3000` |
| `AI_PROVIDER` | `disabled` 或 `openai_compatible` | `disabled` |
| `AI_BASE_URL` / `AI_API_KEY` / `AI_MODEL` | OpenAI-compatible 供应商配置 | Phase 1 不调用真实模型 |
| `NEXT_PUBLIC_API_BASE_URL` | 浏览器访问的 API 地址 | `http://localhost:8000` |

同一个 OpenAI-compatible 适配器可通过 base URL 和模型配置连接 OpenAI、DeepSeek、Qwen/DashScope 或本地兼容 API，业务服务只依赖统一 `AIProvider` 契约。

## 仓库结构

```text
frontend/            Next.js App Router、页面与 API client
backend/             FastAPI、SQLAlchemy、Alembic 与外部适配器
docs/                产品、架构、数据模型、API 与路线图
infra/               本地基础设施说明
scripts/             Windows/Linux 启动与验证脚本
tests/               跨服务测试入口（后续阶段扩展）
.github/workflows/   持续集成
docker-compose.yml   本地五服务开发栈
```

核心设计文档：

- [产品需求](docs/PRODUCT_REQUIREMENTS.md)
- [系统架构](docs/ARCHITECTURE.md)
- [数据模型](docs/DATA_MODEL.md)
- [API 设计](docs/API_DESIGN.md)
- [路线图](docs/ROADMAP.md)

## 工程原则

- 原始 `LearningRecord`、`AssessmentItem`、`ReviewRecord` 长期保存；`ChildKnowledgeState` 是带算法版本、可重算的派生状态。
- 家庭是权限与数据边界；老师只能访问家长显式授权的孩子、范围和有效期。
- PostgreSQL 是事实来源；Redis 内容必须可重建；MinIO 对象默认私有。
- AI 输出受确定性规则和家长控制，不把权限、安全或最终学习判断交给模型。
- 保持模块化单体，在真实扩缩容或隔离需求出现前不拆微服务。

## 常见问题

- **`docker` 命令不存在**：安装/启动 Docker Desktop 或 Docker Engine，确认 `docker compose version` 可用。
- **端口占用**：在 `.env` 修改对应的主机端口，不需要改 Compose 文件。
- **前端显示后端离线**：先检查 <http://localhost:8000/health>，再确认浏览器使用的 `NEXT_PUBLIC_API_BASE_URL`。
- **数据库密码包含特殊字符**：Compose 直接组成连接 URL，请在本地开发密码中使用 URL-safe 字符，或将完整编码后的 `DATABASE_URL` 直接提供给本机后端。
- **依赖状态异常**：后端删除并重建 `.venv`；前端运行 `pnpm install --frozen-lockfile`，不要提交生成目录。

项目任务来源：[GitHub Issue #1](https://github.com/yunfei00/growth-learning/issues/1)。

