# 生产备份与恢复演练

`gl-backup` 为 PostgreSQL 和私有对象存储生成可审计、可恢复的备份材料，不停止现有服务，不删除 volume，也不执行 Docker prune。

## 创建备份

在部署目录运行：

```bash
gl-backup
```

默认写入 `/opt/backups/growth-learning/<UTC timestamp>/`：

- PostgreSQL custom-format dump；
- MinIO bucket 的对象清单（键、大小、ETag、时间）；
- MinIO 私有对象二进制归档 `object-storage-objects.tar`；
- Compose 服务状态；
- SHA-256 校验文件和备份 manifest。

保留天数由 `GROWTH_LEARNING_BACKUP_RETENTION_DAYS` 控制，默认 7 天。清理只允许发生在已验证的 `/opt/backups/growth-learning` 子目录中。

备份目录权限为 `0700`、文件为 `0600`。目录同时包含对象清单和二进制归档；正式异地容灾仍应将整个备份目录复制到独立、受访问控制且加密的存储。不要把归档或对象键发布到 Issue、Release 或 Web。

## 恢复前检查

1. 记录目标环境 commit、Alembic revision 和 Compose 状态。
2. 先对目标环境做一次新的可恢复备份。
3. 在隔离目录执行 `sha256sum --check checksums.sha256`。
4. 检查 dump 的对象列表，不要把不可信 ZIP/SQL 直接导入生产。
5. 使用 `tar -tf object-storage-objects.tar` 检查归档，只允许 `objects/` 下的相对路径；确认对象副本与 manifest 的键和大小一致。
6. 先在隔离 PostgreSQL/MinIO 环境演练，再安排生产维护窗口。

## PostgreSQL 恢复演练

恢复操作是显式的人工运维流程，不由 Web API 或 `gl-update` 自动执行：

```bash
pg_restore --list postgres.dump > restore.list
createdb growth_learning_restore_drill
pg_restore --exit-on-error --no-owner --no-privileges \
  --dbname growth_learning_restore_drill postgres.dump
```

随后在隔离实例验证 `alembic_version`、核心表数量、外键、应用健康检查和随机抽样家庭边界。只有演练通过并有维护窗口时，才按照 PostgreSQL 官方流程切换生产数据库；禁止在运行中的生产库直接使用清库参数。

## MinIO 恢复演练

创建一个随机、隔离且保持 private 的临时 bucket。通过 MinIO SDK 逐条读取归档，只接受 `objects/` 下且不含 `..` 的路径，将对象写入临时 bucket；按 manifest 校验对象数量与大小，并逐字节比较至少一个代表对象。演练后只删除临时 bucket 和临时容器文件，绝不操作生产 bucket。不要把 MinIO 端口或 bucket 设置为公网公开。

恢复脚本不得使用不受控的 `tar -xf` 写入任意主机路径，也不得把生产 bucket 名作为目标。若对象清单为空，仍需验证归档 checksum 和空 bucket 恢复流程。

## 恢复后的验收

- `alembic current` 与部署代码一致；
- PostgreSQL、Redis、MinIO、backend、frontend 全部 healthy；
- `/growth/api/health` 正常；
- 家庭、孩子、学习证据、成长档案与媒体数量符合 manifest；
- 跨家庭和系统管理员隐私测试仍然拒绝；
- 记录演练时间、操作者、备份 ID、结果和差异。

## 应用回滚

应用故障优先回滚到已验证的旧 commit 与同 revision 镜像。回滚前先执行 `gl-backup`，确认旧应用能读取当前 schema；不要在生产盲目执行 `alembic downgrade`。若数据库或对象数据已损坏，停止写入并在隔离环境先验证备份，再制定显式恢复窗口；禁止删除 named volume 作为“回滚”。

## V1 真实恢复演练记录

2026-08-20 的 V1 Release Candidate 使用上述 `growth-learning-backup-v1` 格式执行隔离 PostgreSQL 和隔离 MinIO bucket 恢复。精确候选 SHA、备份目录、checksum、行数/对象 sanity 与最终结果记录在 GitHub Issue #12 的发布证据中；仓库文档不保存生产 secret、对象键或家庭数据。
