# Growth Learning API 设计

## 1. 范围与约定

Phase 1 只实现健康检查与 `/api/v1` 路由骨架。本文定义后续业务 API 的一致约定，端点清单是方向而不是首阶段实现承诺。

- 协议：HTTPS + JSON（本地开发可使用 HTTP）
- 业务前缀：`/api/v1`
- 时间：ISO 8601 UTC，例如 `2026-08-12T08:30:00Z`
- 标识符：UUID 字符串
- 字段命名：`snake_case`
- OpenAPI：FastAPI 生成 `/docs` 与 `/openapi.json`，生产环境可按安全策略限制

## 2. Phase 1 端点

### `GET /health`

进程存活探针，不依赖外部服务。

```json
{
  "status": "ok"
}
```

### `GET /api/v1`

版本路由发现信息。

```json
{
  "name": "Growth Learning API",
  "version": "v1"
}
```

未来增加 `/ready` 检查 PostgreSQL、Redis 和对象存储；不得改变 `/health` 的轻量语义。

## 3. 请求约定

- 身份凭证使用 `Authorization: Bearer <token>`，不通过查询字符串传递。
- 修改操作支持 `Idempotency-Key`；相同主体和键必须返回相同业务结果或明确冲突。
- 每个响应携带或回显 `X-Request-ID`，日志使用同一标识符关联。
- 家庭上下文优先由资源路径和授权推导，不信任客户端自报角色。
- 大列表使用基于稳定排序键的 cursor 分页：`?limit=50&after=<opaque_cursor>`。

列表响应示例：

```json
{
  "items": [],
  "page": {
    "next_cursor": null,
    "has_more": false
  }
}
```

## 4. 错误结构

```json
{
  "error": {
    "code": "teacher_scope_denied",
    "message": "The requested child data is outside this authorization.",
    "request_id": "req_01...",
    "details": {}
  }
}
```

| HTTP | 使用场景 |
| --- | --- |
| 400 | 请求语义错误或无法处理的组合 |
| 401 | 未认证或凭证无效 |
| 403 | 已认证但不在权限/授权范围 |
| 404 | 资源不存在，或为防止枚举而隐藏越权资源 |
| 409 | 幂等冲突、版本冲突或唯一约束冲突 |
| 422 | 字段校验失败 |
| 429 | 限流 |
| 500/503 | 内部错误或必需依赖暂不可用 |

错误 `code` 是稳定机器契约，`message` 可本地化且不泄露内部堆栈。

## 5. 规划资源

### 家庭与授权

```text
POST   /api/v1/families
GET    /api/v1/families/{family_id}
GET    /api/v1/families/{family_id}/members
POST   /api/v1/families/{family_id}/children
GET    /api/v1/children/{child_id}
POST   /api/v1/children/{child_id}/teacher-authorizations
PATCH  /api/v1/teacher-authorizations/{authorization_id}
DELETE /api/v1/teacher-authorizations/{authorization_id}
```

### 课程与学习

```text
GET  /api/v1/subjects
GET  /api/v1/knowledge-points/{knowledge_point_id}
GET  /api/v1/children/{child_id}/activities/next
POST /api/v1/children/{child_id}/learning-records
GET  /api/v1/children/{child_id}/knowledge-state
GET  /api/v1/children/{child_id}/reviews/due
POST /api/v1/children/{child_id}/review-records
```

创建原始记录必须携带幂等键和 `occurred_at`；服务端写入 `received_at`，并校验客户端时间偏差。掌握状态响应包含算法版本、置信度和证据摘要，不只返回单一分数。

### 测评

```text
POST /api/v1/children/{child_id}/assessments
POST /api/v1/assessments/{assessment_id}/items
POST /api/v1/assessments/{assessment_id}/complete
GET  /api/v1/assessments/{assessment_id}
```

完成操作必须幂等；测评结果保留题目/评分规则版本和置信区间。

### 阅读与实验

```text
POST /api/v1/children/{child_id}/stories
GET  /api/v1/stories/{story_id}
POST /api/v1/stories/{story_id}/reading-sessions
POST /api/v1/children/{child_id}/experiment-sessions
GET  /api/v1/science-experiments/{experiment_id}
```

AI 生成故事可返回 `202 Accepted` 与任务资源。只有通过规则校验且状态为 `ready` 的版本可以进入儿童阅读会话。

### 成长与导出

```text
GET  /api/v1/children/{child_id}/growth-events
POST /api/v1/children/{child_id}/growth-events
GET  /api/v1/children/{child_id}/growth-reports
POST /api/v1/families/{family_id}/exports
GET  /api/v1/exports/{export_id}
```

导出为异步资源，完成后返回短期下载地址；只有家庭管理员可以创建完整家庭导出。

## 6. 并发与版本

- 可修改资源使用 `version` 或 `updated_at` 作为乐观并发条件；冲突返回 409。
- API 版本代表外部契约，不等同于课程、提示模板或掌握算法版本。
- 新增可选字段属于兼容变更；删除/改义字段需新 API 版本或明确迁移窗口。
- 枚举新增值可能发生，客户端必须对未知值安全降级。

## 7. 安全与隐私

- 服务层在查询前验证家庭归属和授权 scope，不能先加载越权数据再由响应层过滤。
- 老师端只返回授权字段；批量接口逐项应用同一权限边界。
- 上传采用允许的 MIME/大小、哈希与恶意内容扫描策略；下载通过短期签名 URL。
- 日志不记录完整儿童答案、故事正文、访问令牌、签名 URL 或供应商密钥。
- OpenAPI 示例使用虚构数据，不包含真实儿童信息。

## 8. API 测试策略

- 契约测试覆盖成功响应、校验错误和稳定错误码。
- 权限矩阵覆盖家长、孩子、老师、陪伴者以及过期/撤销授权。
- 记录创建覆盖幂等重试、时钟偏差和并发写入。
- AI provider 使用假实现，不在常规测试或 CI 中访问真实模型。
- 集成测试使用隔离数据库；单元测试不得依赖开发者本机正在运行的服务。

