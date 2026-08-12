# Growth Learning

Growth Learning 是一个面向儿童长期学习与成长记录的家庭中心平台。项目从汉字学习切入，逐步覆盖可重算掌握度、自适应复习、识字量测评、受控 AI 阅读、周末科学实验、家庭与老师协作以及长期成长档案。

当前为 **Phase 1：工程基础**。仓库提供可运行的 Next.js + FastAPI 模块化单体，以及 PostgreSQL、Redis、MinIO 服务器集成环境；尚未实现正式业务账户和学习数据。

## Windows development

Windows 只承担代码开发和轻量前后端调试，**不需要也不建议安装 Docker、Docker Desktop 或 WSL Docker**。完整数据服务和 Compose 验收统一在 Linux 服务器进行。

### 工具版本

- Node.js 24（仓库 `.nvmrc`；当前基线验证版本 24.14.0）
- pnpm 11.16.0（由 `packageManager` 固定）
- Python 3.12 或 3.13（仓库开发基线 `.python-version` 为 3.13）

首次安装：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".\backend[dev]"
Set-Location frontend
pnpm install --frozen-lockfile
Set-Location ..
```

同时启动前后端：

```powershell
.\scripts\dev.ps1
```

也可以在两个终端分别运行：

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload

# 另一个终端
Set-Location frontend
pnpm dev
```

轻量 `/health` 和单元测试不会在导入时连接 PostgreSQL、Redis 或 MinIO；涉及数据迁移和跨服务联调时使用服务器环境。前端默认通过 `http://localhost:8000` 访问后端，不要把任何密钥放入 `NEXT_PUBLIC_*` 变量。

本地地址：

| 服务 | 地址 |
| --- | --- |
| Frontend | <http://localhost:3000> |
| 开发状态页 | <http://localhost:3000/status> |
| Backend health | <http://localhost:8000/health> |
| Backend OpenAPI | <http://localhost:8000/docs> |

## Server integration / deployment

Linux 服务器使用 Docker Engine 与 Docker Compose Plugin 运行完整五服务集成栈，固定部署目录为：

```text
/opt/apps/growth-learning
```

首次部署：

```bash
mkdir -p /opt/apps
git clone https://github.com/yunfei00/growth-learning.git /opt/apps/growth-learning
cd /opt/apps/growth-learning

GROWTH_LEARNING_PUBLIC_FRONTEND_ORIGIN=http://<server-ip>:3000 \
GROWTH_LEARNING_PUBLIC_API_BASE_URL=http://<server-ip>:8000 \
  bash scripts/server-bootstrap.sh

source /root/.bashrc
bash scripts/server-deploy.sh
```

`server-bootstrap.sh` 可重复执行：已有 `.env` 会被保留；首次运行会生成随机 PostgreSQL/MinIO 密码，并以 managed block 方式安装快捷命令。服务器 `.env` 不得提交到 Git。

部署后可使用：

```text
gl-start     启动已有镜像
gl-stop      停止本项目并保留命名卷
gl-restart   重启本项目
gl-status    查看五个服务状态
gl-logs      跟踪日志（可追加服务名）
gl-update    fast-forward 拉取 main、顺序重建并启动
```

PostgreSQL、Redis、MinIO 只在私有 Compose 网络中通信，不映射宿主机端口。只有 Frontend 和 Backend 通过 `.env` 中的绑定地址与端口发布；若默认端口冲突，修改 `FRONTEND_PORT` / `BACKEND_PORT`，不要停止无关项目抢占端口。

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

服务器 Compose 配置与运行态检查：

```bash
docker compose --env-file .env config --quiet
docker compose --env-file .env ps
curl http://127.0.0.1:${BACKEND_PORT:-8000}/health
curl -I http://127.0.0.1:${FRONTEND_PORT:-3000}/status
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
| `BACKEND_BIND_ADDRESS` / `BACKEND_PORT` | Backend 宿主机监听 | `0.0.0.0:8000` |
| `FRONTEND_BIND_ADDRESS` / `FRONTEND_PORT` | Frontend 宿主机监听 | `0.0.0.0:3000` |
| `PUBLIC_API_BASE_URL` | 构建进浏览器端代码的 API 地址 | `http://localhost:8000` |
| `AI_PROVIDER` | `disabled` 或 `openai_compatible` | `disabled` |
| `AI_BASE_URL` / `AI_API_KEY` / `AI_MODEL` | OpenAI-compatible 供应商配置 | Phase 1 不调用真实模型 |
| `NEXT_PUBLIC_API_BASE_URL` | 浏览器访问的 API 地址 | `http://localhost:8000` |

同一个 OpenAI-compatible 适配器可通过 base URL 和模型配置连接 OpenAI、DeepSeek、Qwen/DashScope 或本地兼容 API，业务服务只依赖统一 `AIProvider` 契约。

## 仓库结构

```text
frontend/            Next.js App Router、页面与 API client
backend/             FastAPI、SQLAlchemy、Alembic 与外部适配器
docs/                产品、架构、数据模型、API 与路线图
infra/               Linux 服务器集成环境说明
scripts/             Windows 开发、Linux 部署与验证脚本
tests/               跨服务测试入口（后续阶段扩展）
.github/workflows/   持续集成
docker-compose.yml   Linux 服务器五服务集成栈
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

- **Windows 没有 `docker`**：这是预期状态；Windows 使用原生 Node.js/Python 开发流程。
- **服务器 `docker` 命令不存在**：仅在 Linux 服务器安装官方 Docker Engine 与 Compose Plugin。
- **端口占用**：在 `.env` 修改对应的主机端口，不需要改 Compose 文件。
- **前端显示后端离线**：先检查 <http://localhost:8000/health>，再确认浏览器使用的 `NEXT_PUBLIC_API_BASE_URL`。
- **数据库密码包含特殊字符**：Compose 直接组成连接 URL，请在本地开发密码中使用 URL-safe 字符，或将完整编码后的 `DATABASE_URL` 直接提供给本机后端。
- **依赖状态异常**：后端删除并重建 `.venv`；前端运行 `pnpm install --frozen-lockfile`，不要提交生成目录。

项目任务来源：[GitHub Issue #1](https://github.com/yunfei00/growth-learning/issues/1)。
