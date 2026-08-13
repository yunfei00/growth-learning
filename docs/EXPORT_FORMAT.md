# 家庭数据导出格式

Phase 8 导出是家庭管理员主动发起的私有、短期可下载 ZIP。当前格式版本为 `growth-learning-export-v1`。导出以数据库事实为准，不包含应用 secret，也不提供公开对象 URL。

## ZIP 结构

```text
manifest.json
family.json
children.json
learning.json
reading.json
science.json
growth_archive.json
csv/
  children.csv
  growth_events.csv
  learning_records.csv
  assessment_items.csv
  reading_sessions.csv
  experiment_sessions.csv
media/
  <opaque object id and safe extension>
```

JSON 保存完整结构化关系；CSV 提供面向家长的常用表格视图；`media/` 只包含请求范围内、数据库仍有归属记录的私有附件。实现逐对象读取/写入，不把完整家庭媒体集一次装入内存。

## Manifest

`manifest.json` 至少记录：

- `schema_version=growth-learning-export-v1`；
- 导出时间、家庭范围和可选孩子范围；
- 每类记录数量；
- 每个文件的路径、字节数和 SHA-256；
- 请求/写入/缺失媒体数量；
- 导出服务版本。

生成完成前会重新打开 ZIP，校验必需文件、版本、文件大小、SHA-256、孩子数量与媒体数量。校验失败的任务不会变成可下载状态。

## 明确排除

导出不得出现密码哈希、会话 token、认证 secret、AI API key、MinIO/PostgreSQL 密码或其他运行时密钥。用户、家庭成员记录仅包含恢复归属所需的安全字段。测试会扫描结构化内容和归档字节中的高风险字段标记。

## 下载和过期

`ExportJob` 保存请求人、范围、状态、私有对象键、校验快照和过期时间。只有发起导出的家庭管理员可下载；`companion`、其他家庭成员和仅有平台管理员身份的用户均无权访问。下载响应禁止缓存。默认 1 小时过期，清理命令为：

```bash
docker compose exec backend python -m app.cli.growth cleanup-exports
```

## 将来导入

V1 的 manifest、稳定 UUID 和分域 JSON 是将来受控恢复/迁移工具的基础，但 Phase 8 不开放一键导入 API。导入必须先完成版本兼容、冲突、成员身份和媒体校验，不能直接把 ZIP 解压覆盖生产数据库。
